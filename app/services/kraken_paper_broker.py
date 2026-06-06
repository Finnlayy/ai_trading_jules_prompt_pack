"""Kraken Paper Trading Broker — simulates trades against live Kraken prices.

Uses the public Kraken API for real-time prices and SQLite for virtual
balance, positions, and trade history. No real money, no API credentials
required for trading (only for balance sync if desired).

Fee model: 0.26% taker fee (Kraken Starter tier default).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.db.models import PaperBalance, PaperPosition, PaperTrade
from app.services.broker_interface import BaseBroker
from app.services.kraken_broker import KrakenBroker

logger = logging.getLogger(__name__)

KRAKEN_PAPER_FEE_PCT = Decimal("0.0026")  # 0.26% taker fee
DEFAULT_PAPER_BALANCE = 50.0  # $50 USD default


@dataclass(frozen=True)
class KrakenPaperConfig:
    """Runtime settings for Kraken paper trading."""

    enabled: bool = True
    initial_balance_usd: float = DEFAULT_PAPER_BALANCE
    fee_pct: float = float(KRAKEN_PAPER_FEE_PCT)
    spot_only: bool = True
    max_order_usd: float = 100.0
    min_order_usd: float = 0.5


class KrakenPaperBroker(BaseBroker):
    """Paper trading broker that simulates execution against live Kraken prices.

    No real orders are sent. All fills use the current bid/ask from Kraken's
    public ticker API. P&L, positions, and balance are persisted in SQLite.
    """

    def __init__(self, config: Optional[KrakenPaperConfig] = None) -> None:
        self.config = config or KrakenPaperConfig()
        self._kraken = KrakenBroker()  # For live prices only (no auth needed)
        self._init_balance()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _db(self) -> Session:
        return SessionLocal()

    def _init_balance(self) -> None:
        """Seed the paper balance if none exists."""
        Base.metadata.create_all(bind=engine)
        with self._db() as db:
            bal = db.query(PaperBalance).filter(PaperBalance.currency == "USD").first()
            if bal is None:
                bal = PaperBalance(
                    currency="USD",
                    balance=self.config.initial_balance_usd,
                    equity=self.config.initial_balance_usd,
                )
                db.add(bal)
                db.commit()

    def _get_balance(self, db: Session) -> PaperBalance:
        bal = db.query(PaperBalance).filter(PaperBalance.currency == "USD").first()
        if bal is None:
            bal = PaperBalance(
                currency="USD",
                balance=self.config.initial_balance_usd,
                equity=self.config.initial_balance_usd,
            )
            db.add(bal)
            db.commit()
        return bal

    def _get_live_price(self, pair: str) -> tuple[float, float]:
        """Return (bid, ask) for a Kraken pair using public API."""
        normalized = self._kraken.normalize_pair(pair)
        result = self._kraken.get_ticker(normalized)
        # Kraken returns keyed by actual pair name
        key = list(result.keys())[0]
        ticker = result[key]
        bid = float(ticker["b"][0])
        ask = float(ticker["a"][0])
        return bid, ask

    def _calculate_fee(self, notional: float) -> float:
        """Calculate taker fee for a given notional value."""
        return round(notional * float(self.config.fee_pct), 8)

    # ------------------------------------------------------------------
    # BaseBroker interface
    # ------------------------------------------------------------------

    def is_live_capable(self) -> bool:
        return False  # Paper broker never executes real trades

    def is_ready(self) -> bool:
        return self.config.enabled

    def get_broker_name(self) -> str:
        return "KrakenPaperBroker"

    def get_broker_type(self) -> str:
        return "kraken_paper"

    def get_broker_mode(self) -> str:
        return "paper"

    def reconcile_ledger(self) -> dict[str, Any]:
        """Reconcile paper balance against trade history to detect drift."""
        with self._db() as db:
            bal = self._get_balance(db)
            trades = db.query(PaperTrade).all()

            # Compute expected balance from initial balance and trade history
            expected = self.config.initial_balance_usd
            for t in trades:
                if t.status == "open" and t.direction == "LONG":
                    expected -= (t.entry_price * t.volume + t.fee)
                elif t.status == "closed":
                    if t.direction == "LONG":
                        expected -= t.fee
                        if t.pnl:
                            expected += t.pnl
                    elif t.direction == "SHORT":
                        expected -= t.fee
                        if t.pnl:
                            expected += t.pnl

            drift = round(bal.balance - expected, 8)
            drift_detected = abs(drift) > 0.0001

            if drift_detected:
                bal.balance = round(expected, 8)
                bal.equity = round(expected, 8)
                db.commit()

            return {
                "checked": True,
                "drift_detected": drift_detected,
                "drift_amount": drift,
                "corrected": drift_detected,
                "expected_balance": round(expected, 8),
                "actual_balance": round(bal.balance, 8),
                "trade_count": len(trades),
            }

    def health(self) -> dict[str, Any]:
        h = super().health()
        h["initial_balance"] = self.config.initial_balance_usd
        h["fee_pct"] = float(self.config.fee_pct)
        h["spot_only"] = self.config.spot_only
        return h

    def execute_trade(self, payload, decision, reject_reason=None, ai_decision=None):
        """BaseBroker interface — not used directly for paper trading.

        Paper trading uses place_paper_order() instead.
        """
        raise NotImplementedError("Use place_paper_order() for paper trading")

    def get_positions(self) -> dict[str, Any]:
        """Return all open paper positions."""
        with self._db() as db:
            positions = (
                db.query(PaperPosition)
                .filter(PaperPosition.status == "open")
                .all()
            )
            # Update unrealized P&L with live prices
            result = []
            for pos in positions:
                try:
                    bid, ask = self._get_live_price(pos.symbol)
                    current = ask if pos.direction == "LONG" else bid
                    if pos.direction == "LONG":
                        pos.unrealized_pnl = round(
                            (current - pos.avg_entry_price) * pos.volume, 8
                        )
                    else:
                        pos.unrealized_pnl = round(
                            (pos.avg_entry_price - current) * pos.volume, 8
                        )
                    db.commit()
                except Exception as exc:
                    logger.warning("Could not update live P&L for %s: %s", pos.symbol, exc)

                result.append({
                    "symbol": pos.symbol,
                    "direction": pos.direction,
                    "volume": pos.volume,
                    "avg_entry_price": pos.avg_entry_price,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "realized_pnl": pos.realized_pnl,
                    "fee_paid": pos.fee_paid,
                    "stop_loss": pos.stop_loss,
                    "take_profit": pos.take_profit,
                    "created_at": pos.created_at.isoformat() if pos.created_at else None,
                })

            return {
                "status": "ok",
                "positions": result,
                "count": len(result),
            }

    def get_wallet_balances(self, account_mode: str = "PAPER") -> dict[str, Any]:
        """Return paper balance and equity."""
        with self._db() as db:
            bal = self._get_balance(db)
            # Recalculate equity: balance + unrealized P&L from open positions
            open_positions = (
                db.query(PaperPosition)
                .filter(PaperPosition.status == "open")
                .all()
            )
            total_unrealized = 0.0
            for pos in open_positions:
                try:
                    bid, ask = self._get_live_price(pos.symbol)
                    current = ask if pos.direction == "LONG" else bid
                    if pos.direction == "LONG":
                        total_unrealized += (current - pos.avg_entry_price) * pos.volume
                    else:
                        total_unrealized += (pos.avg_entry_price - current) * pos.volume
                except Exception:
                    total_unrealized += pos.unrealized_pnl or 0.0

            bal.equity = round(bal.balance + total_unrealized, 8)
            bal.total_pnl = round(bal.total_pnl, 8)
            db.commit()

            return {
                "status": "ok",
                "account_mode": account_mode,
                "currency": bal.currency,
                "balance": bal.balance,
                "reserved": bal.reserved,
                "equity": bal.equity,
                "total_pnl": bal.total_pnl,
                "unrealized_pnl": round(total_unrealized, 8),
                "open_positions": len(open_positions),
            }

    # ------------------------------------------------------------------
    # Paper trading operations
    # ------------------------------------------------------------------

    def place_paper_order(
        self,
        symbol: str,
        direction: str,
        volume: float,
        order_type: str = "market",
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        candidate_id: Optional[str] = None,
        signal_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        timeframe: Optional[str] = None,
        ai_trace_json: Optional[str] = None,
        risk_decision: Optional[str] = None,
        risk_reason: Optional[str] = None,
        opened_by_loop: bool = False,
        outcome_source: str = "live_paper",
    ) -> dict[str, Any]:
        """Place a paper order and simulate immediate fill at live price.

        Args:
            symbol: Trading pair (e.g. "SOLUSD", "BTCUSD")
            direction: "BUY" / "LONG" or "SELL" / "SHORT"
            volume: Order volume in base currency
            order_type: "market" or "limit"
            price: Limit price (ignored for market orders)

        Returns:
            Dict with fill details, fees, and updated balance.
        """
        if not self.config.enabled:
            return {"status": "error", "error": "Paper trading is disabled"}

        if self.config.spot_only and direction.upper() in {"SELL", "SHORT"}:
            # For spot paper, SELL means closing/reducing a long position
            pass  # Allowed — we'll check position below

        # Normalize direction
        dir_norm = "LONG" if direction.upper() in {"BUY", "LONG"} else "SHORT"
        pair = self._kraken.normalize_pair(symbol)

        # Get live price
        try:
            bid, ask = self._get_live_price(pair)
        except Exception as exc:
            return {"status": "error", "error": f"Could not fetch live price: {exc}"}

        # Determine fill price
        if order_type.lower() == "market":
            fill_price = ask if dir_norm == "LONG" else bid
        else:
            fill_price = price or (ask if dir_norm == "LONG" else bid)

        notional = fill_price * volume
        fee = self._calculate_fee(notional)
        total_cost = notional + fee

        with self._db() as db:
            bal = self._get_balance(db)

            # Check balance for LONG (need USD)
            if dir_norm == "LONG" and bal.balance < total_cost:
                return {
                    "status": "error",
                    "error": f"Insufficient paper balance: ${bal.balance:.2f} < ${total_cost:.2f}",
                }

            # For SHORT in spot paper, check if we have the asset
            # Allow flip (larger counter-trade) if an opposite position exists
            if dir_norm == "SHORT":
                pos = (
                    db.query(PaperPosition)
                    .filter(PaperPosition.symbol == pair, PaperPosition.status == "open")
                    .first()
                )
                if pos is None:
                    return {
                        "status": "error",
                        "error": f"Insufficient {pair} to sell: no open position",
                    }
                # Allow flip even if volume > position (net position will flip)
                if pos.direction == "SHORT" and pos.volume < volume:
                    return {
                        "status": "error",
                        "error": f"Insufficient {pair} to sell: {pos.volume:.6f} < {volume:.6f}",
                    }

            # Create trade record
            trade_id = f"paper_{uuid.uuid4().hex[:12]}"
            trade = PaperTrade(
                trade_id=trade_id,
                candidate_id=candidate_id,
                signal_id=signal_id,
                symbol=pair,
                direction=dir_norm,
                strategy_id=strategy_id,
                timeframe=timeframe,
                order_type=order_type.lower(),
                volume=volume,
                entry_price=fill_price,
                fee=fee,
                ai_trace_json=ai_trace_json,
                risk_decision=risk_decision,
                risk_reason=risk_reason,
                outcome_source=outcome_source,
                status="open",
            )
            db.add(trade)

            # Update balance
            if dir_norm == "LONG":
                bal.balance -= total_cost
            else:
                # SHORT: receive USD from sale
                bal.balance += notional - fee

            bal.total_pnl -= fee  # Fees reduce P&L
            db.commit()

            # Update or create position
            position = (
                db.query(PaperPosition)
                .filter(PaperPosition.symbol == pair, PaperPosition.status == "open")
                .first()
            )

            if position is None:
                position = PaperPosition(
                    candidate_id=candidate_id,
                    signal_id=signal_id,
                    symbol=pair,
                    direction=dir_norm,
                    strategy_id=strategy_id,
                    timeframe=timeframe,
                    volume=volume,
                    avg_entry_price=fill_price,
                    fee_paid=fee,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    ai_trace_json=ai_trace_json,
                    risk_decision=risk_decision,
                    opened_by_loop=opened_by_loop,
                    status="open",
                )
                db.add(position)
            else:
                if position.direction == dir_norm:
                    # Adding to existing position
                    total_vol = position.volume + volume
                    position.avg_entry_price = round(
                        (position.avg_entry_price * position.volume + fill_price * volume)
                        / total_vol,
                        8,
                    )
                    position.volume = total_vol
                    position.fee_paid += fee
                    position.candidate_id = candidate_id or position.candidate_id
                    position.signal_id = signal_id or position.signal_id
                    position.strategy_id = strategy_id or position.strategy_id
                    position.timeframe = timeframe or position.timeframe
                    position.stop_loss = stop_loss if stop_loss is not None else position.stop_loss
                    position.take_profit = take_profit if take_profit is not None else position.take_profit
                    position.ai_trace_json = ai_trace_json or position.ai_trace_json
                    position.risk_decision = risk_decision or position.risk_decision
                    position.opened_by_loop = opened_by_loop or position.opened_by_loop
                else:
                    # Reducing / closing / flipping
                    if volume < position.volume:
                        # Partial close
                        pnl = (
                            (fill_price - position.avg_entry_price) * volume
                            if dir_norm == "SHORT"  # closing long
                            else (position.avg_entry_price - fill_price) * volume
                        )
                        position.volume -= volume
                        position.realized_pnl += pnl
                        position.fee_paid += fee
                        bal.total_pnl += pnl

                        trade.pnl = pnl
                        trade.status = "closed"
                        trade.exit_price = fill_price
                        trade.closed_at = datetime.now(timezone.utc)
                    elif volume == position.volume:
                        # Full close
                        pnl = (
                            (fill_price - position.avg_entry_price) * position.volume
                            if dir_norm == "SHORT"
                            else (position.avg_entry_price - fill_price) * position.volume
                        )
                        position.realized_pnl += pnl
                        position.fee_paid += fee
                        position.volume = 0.0
                        position.status = "closed"
                        position.closed_at = datetime.now(timezone.utc)
                        bal.total_pnl += pnl

                        trade.pnl = pnl
                        trade.status = "closed"
                        trade.exit_price = fill_price
                        trade.closed_at = datetime.now(timezone.utc)
                    else:
                        # Flip direction
                        close_pnl = (
                            (fill_price - position.avg_entry_price) * position.volume
                            if dir_norm == "SHORT"
                            else (position.avg_entry_price - fill_price) * position.volume
                        )
                        remaining = volume - position.volume
                        position.realized_pnl += close_pnl
                        position.fee_paid += fee
                        bal.total_pnl += close_pnl

                        # Close old position
                        old_dir = position.direction
                        position.volume = 0.0
                        position.status = "closed"
                        position.closed_at = datetime.now(timezone.utc)

                        # Open new position in opposite direction
                        new_pos = PaperPosition(
                            candidate_id=candidate_id,
                            signal_id=signal_id,
                            symbol=pair,
                            direction=dir_norm,
                            strategy_id=strategy_id,
                            timeframe=timeframe,
                            volume=remaining,
                            avg_entry_price=fill_price,
                            fee_paid=fee,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            ai_trace_json=ai_trace_json,
                            risk_decision=risk_decision,
                            opened_by_loop=opened_by_loop,
                            status="open",
                        )
                        db.add(new_pos)

                        trade.pnl = close_pnl
                        trade.status = "closed"
                        trade.exit_price = fill_price
                        trade.closed_at = datetime.now(timezone.utc)

                        # Create a new trade for the flipped portion
                        new_trade = PaperTrade(
                            trade_id=f"paper_{uuid.uuid4().hex[:12]}",
                            candidate_id=candidate_id,
                            signal_id=signal_id,
                            symbol=pair,
                            direction=dir_norm,
                            strategy_id=strategy_id,
                            timeframe=timeframe,
                            order_type=order_type.lower(),
                            volume=remaining,
                            entry_price=fill_price,
                            fee=0.0,
                            ai_trace_json=ai_trace_json,
                            risk_decision=risk_decision,
                            risk_reason=risk_reason,
                            outcome_source=outcome_source,
                            status="open",
                        )
                        db.add(new_trade)

            db.commit()

            return {
                "status": "ok",
                "trade_id": trade_id,
                "symbol": pair,
                "direction": dir_norm,
                "order_type": order_type.lower(),
                "volume": volume,
                "fill_price": fill_price,
                "notional": round(notional, 8),
                "fee": fee,
                "total_cost": round(total_cost, 8),
                "balance_after": round(bal.balance, 8),
                "equity": round(bal.equity, 8),
                "mode": "paper",
            }

    def close_paper_position(
        self,
        symbol: str,
        volume: Optional[float] = None,
        order_type: str = "market",
        close_reason: Optional[str] = None,
    ) -> dict[str, Any]:
        """Close (part of) an open paper position.

        Args:
            symbol: Trading pair to close
            volume: Amount to close (None = full position)
            order_type: "market" or "limit"
        """
        pair = self._kraken.normalize_pair(symbol)

        with self._db() as db:
            position = (
                db.query(PaperPosition)
                .filter(PaperPosition.symbol == pair, PaperPosition.status == "open")
                .first()
            )
            if position is None:
                return {"status": "error", "error": f"No open position for {pair}"}

            close_vol = volume if volume is not None else position.volume
            if close_vol > position.volume:
                close_vol = position.volume

            # Get live price
            try:
                bid, ask = self._get_live_price(pair)
            except Exception as exc:
                return {"status": "error", "error": f"Could not fetch live price: {exc}"}

            # Closing direction is opposite of position
            close_dir = "SHORT" if position.direction == "LONG" else "LONG"
            fill_price = ask if close_dir == "LONG" else bid

            notional = fill_price * close_vol
            fee = self._calculate_fee(notional)

            # Calculate P&L
            if position.direction == "LONG":
                pnl = (fill_price - position.avg_entry_price) * close_vol
            else:
                pnl = (position.avg_entry_price - fill_price) * close_vol

            bal = self._get_balance(db)

            # Update balance
            if position.direction == "LONG":
                # Sell the asset, receive USD
                bal.balance += notional - fee
            else:
                # Cover short, pay USD
                bal.balance -= notional + fee

            bal.total_pnl += pnl - fee

            # Update position
            position.volume -= close_vol
            position.realized_pnl += pnl
            position.fee_paid += fee

            if position.volume <= 0:
                position.status = "closed"
                position.closed_at = datetime.now(timezone.utc)

            # Create closing trade
            close_trade_id = f"paper_{uuid.uuid4().hex[:12]}"
            trade = PaperTrade(
                trade_id=close_trade_id,
                candidate_id=position.candidate_id,
                signal_id=position.signal_id,
                symbol=pair,
                direction=close_dir,
                strategy_id=position.strategy_id,
                timeframe=position.timeframe,
                order_type=order_type.lower(),
                volume=close_vol,
                entry_price=fill_price,
                exit_price=fill_price,
                fee=fee,
                pnl=pnl,
                ai_trace_json=position.ai_trace_json,
                risk_decision=position.risk_decision,
                close_reason=close_reason,
                outcome_source="live_paper",
                status="closed",
                closed_at=datetime.now(timezone.utc),
            )
            db.add(trade)
            db.commit()

            return {
                "status": "ok",
                "trade_id": close_trade_id,
                "candidate_id": position.candidate_id,
                "signal_id": position.signal_id,
                "symbol": pair,
                "direction": close_dir,
                "volume": close_vol,
                "fill_price": fill_price,
                "pnl": round(pnl, 8),
                "fee": fee,
                "close_reason": close_reason,
                "balance_after": round(bal.balance, 8),
                "position_remaining": position.volume if position.status == "open" else 0.0,
                "mode": "paper",
            }

    def reset_paper_account(self, new_balance: Optional[float] = None) -> dict[str, Any]:
        """Reset all paper trades, positions, and balance to initial state."""
        with self._db() as db:
            db.query(PaperTrade).delete()
            db.query(PaperPosition).delete()
            db.query(PaperBalance).delete()

            balance = new_balance if new_balance is not None else self.config.initial_balance_usd
            bal = PaperBalance(
                currency="USD",
                balance=balance,
                equity=balance,
                total_pnl=0.0,
            )
            db.add(bal)
            db.commit()

            return {
                "status": "ok",
                "balance": balance,
                "message": "Paper account reset",
            }

    def get_paper_history(self, limit: int = 100) -> dict[str, Any]:
        """Return paper trade history."""
        with self._db() as db:
            trades = (
                db.query(PaperTrade)
                .order_by(PaperTrade.created_at.desc())
                .limit(limit)
                .all()
            )
            return {
                "status": "ok",
                "trades": [
                    {
                        "trade_id": t.trade_id,
                        "symbol": t.symbol,
                        "direction": t.direction,
                        "order_type": t.order_type,
                        "volume": t.volume,
                        "entry_price": t.entry_price,
                        "exit_price": t.exit_price,
                        "fee": t.fee,
                        "pnl": t.pnl,
                        "status": t.status,
                        "created_at": t.created_at.isoformat() if t.created_at else None,
                        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
                    }
                    for t in trades
                ],
                "count": len(trades),
            }
