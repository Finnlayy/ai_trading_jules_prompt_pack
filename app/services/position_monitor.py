"""
Position Monitor — checks open positions for stop-loss, take-profit, and time-exit conditions.
Called by PricePoller for live exits or directly by backtest/simulation loops.
Also includes PaperPositionMonitor for auto SL/TP on Kraken paper positions.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from app.services.live_fill_tracker import live_fill_tracker, OpenPosition
from app.core.config import POSITION_MAX_HOLD_MINUTES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Legacy ExitResult + PositionMonitor (used by live_fill_tracker / price_poller)
# ---------------------------------------------------------------------------

@dataclass
class ExitResult:
    trade_id: str
    symbol: str
    direction: str
    exit_price: float
    exit_reason: str  # STOP_LOSS, TAKE_PROFIT, TIME_EXIT
    pnl_estimate: float
    bars_held: int | None = None


class PositionMonitor:
    """
    Singleton monitor for open position exit conditions.
    Stateless logic — all position state lives in LiveFillTracker.
    """

    _instance: PositionMonitor | None = None

    def __new__(cls, *args, **kwargs) -> PositionMonitor:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, broker=None) -> None:
        if self._initialized:
            return
        self._initialized = True

    # -- Bar-based exits (for backtest / simulation) ------------------------

    def check_exits(self, bars: list) -> List[ExitResult]:
        """
        Check all open positions against a list of OHLCV bars.
        Used in backtest/simulation where we have full bar data.
        """
        exits: List[ExitResult] = []
        positions = live_fill_tracker.get_open_positions()
        if not positions or not bars:
            return exits

        for pos in positions:
            exit_result = self._check_position_bars(pos, bars)
            if exit_result:
                exits.append(exit_result)
        return exits

    def _check_position_bars(self, pos: OpenPosition, bars: list) -> ExitResult | None:
        """Check a single position against bar data. Stop takes precedence over target."""
        if not bars:
            return None
        latest = bars[-1]

        # Time exit
        max_hold_minutes = POSITION_MAX_HOLD_MINUTES
        time_in_trade = pos.time_in_trade_minutes
        if time_in_trade >= max_hold_minutes:
            return ExitResult(
                trade_id=pos.trade_id,
                symbol=pos.symbol,
                direction=pos.direction,
                exit_price=latest.c,
                exit_reason="TIME_EXIT",
                pnl_estimate=self._estimate_pnl(pos, latest.c),
            )

        if pos.direction == "LONG":
            if latest.l <= pos.stop_price:
                return ExitResult(
                    trade_id=pos.trade_id,
                    symbol=pos.symbol,
                    direction=pos.direction,
                    exit_price=pos.stop_price,
                    exit_reason="STOP_LOSS",
                    pnl_estimate=self._estimate_pnl(pos, pos.stop_price),
                )
            if latest.h >= pos.target_price:
                return ExitResult(
                    trade_id=pos.trade_id,
                    symbol=pos.symbol,
                    direction=pos.direction,
                    exit_price=pos.target_price,
                    exit_reason="TAKE_PROFIT",
                    pnl_estimate=self._estimate_pnl(pos, pos.target_price),
                )
        else:  # SHORT
            if latest.h >= pos.stop_price:
                return ExitResult(
                    trade_id=pos.trade_id,
                    symbol=pos.symbol,
                    direction=pos.direction,
                    exit_price=pos.stop_price,
                    exit_reason="STOP_LOSS",
                    pnl_estimate=self._estimate_pnl(pos, pos.stop_price),
                )
            if latest.l <= pos.target_price:
                return ExitResult(
                    trade_id=pos.trade_id,
                    symbol=pos.symbol,
                    direction=pos.direction,
                    exit_price=pos.target_price,
                    exit_reason="TAKE_PROFIT",
                    pnl_estimate=self._estimate_pnl(pos, pos.target_price),
                )
        return None

    # -- Price-based exits (for live polling) -------------------------------

    def check_price_based_exits(self, prices: dict[str, float]) -> List[ExitResult]:
        """
        Check all open positions against a dict of current prices {symbol: price}.
        Used by PricePoller for live market monitoring.
        """
        exits: List[ExitResult] = []
        positions = live_fill_tracker.get_open_positions()
        if not positions:
            return exits

        for pos in positions:
            current_price = prices.get(pos.symbol.upper())
            if current_price is None:
                continue
            exit_result = self._check_position_price(pos, current_price)
            if exit_result:
                exits.append(exit_result)
        return exits

    def _check_position_price(self, pos: OpenPosition, current_price: float) -> ExitResult | None:
        """Check a single position against a live price."""
        max_hold_minutes = getattr(self, '_max_hold_minutes', 240)
        if pos.time_in_trade_minutes >= max_hold_minutes:
            return ExitResult(
                trade_id=pos.trade_id,
                symbol=pos.symbol,
                direction=pos.direction,
                exit_price=current_price,
                exit_reason="TIME_EXIT",
                pnl_estimate=self._estimate_pnl(pos, current_price),
            )

        if pos.direction == "LONG":
            if current_price <= pos.stop_price:
                return ExitResult(
                    trade_id=pos.trade_id,
                    symbol=pos.symbol,
                    direction=pos.direction,
                    exit_price=current_price,
                    exit_reason="STOP_LOSS",
                    pnl_estimate=self._estimate_pnl(pos, current_price),
                )
            if current_price >= pos.target_price:
                return ExitResult(
                    trade_id=pos.trade_id,
                    symbol=pos.symbol,
                    direction=pos.direction,
                    exit_price=current_price,
                    exit_reason="TAKE_PROFIT",
                    pnl_estimate=self._estimate_pnl(pos, current_price),
                )
        else:  # SHORT
            if current_price >= pos.stop_price:
                return ExitResult(
                    trade_id=pos.trade_id,
                    symbol=pos.symbol,
                    direction=pos.direction,
                    exit_price=current_price,
                    exit_reason="STOP_LOSS",
                    pnl_estimate=self._estimate_pnl(pos, current_price),
                )
            if current_price <= pos.target_price:
                return ExitResult(
                    trade_id=pos.trade_id,
                    symbol=pos.symbol,
                    direction=pos.direction,
                    exit_price=current_price,
                    exit_reason="TAKE_PROFIT",
                    pnl_estimate=self._estimate_pnl(pos, current_price),
                )
        return None

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _estimate_pnl(pos: OpenPosition, exit_price: float) -> float:
        if pos.direction == "LONG":
            return (exit_price - pos.entry_price) * pos.size
        return (pos.entry_price - exit_price) * pos.size

    def execute_exits(self, exits: List[ExitResult]) -> List[dict]:
        """
        Execute exits via live_fill_tracker and return closed position summaries.
        Also broadcasts SSE events.
        """
        from app.services.dashboard_sse import dashboard_sse_manager

        closed = []
        for ex in exits:
            live_fill_tracker.record_exit(ex.trade_id, ex.exit_price)
            closed.append({
                "trade_id": ex.trade_id,
                "symbol": ex.symbol,
                "direction": ex.direction,
                "exit_price": ex.exit_price,
                "exit_reason": ex.exit_reason,
                "pnl_estimate": ex.pnl_estimate,
            })
            dashboard_sse_manager.broadcast_alert(
                f"Position {ex.trade_id} closed: {ex.exit_reason} @ {ex.exit_price}",
                level="info" if ex.exit_reason == "TAKE_PROFIT" else "warning",
            )

        if closed:
            positions = live_fill_tracker.get_open_positions()
            dashboard_sse_manager.broadcast_position_update(
                [{
                    "trade_id": p.trade_id,
                    "symbol": p.symbol,
                    "direction": p.direction,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "unrealized_pnl": p.unrealized_pnl,
                    "realized_pnl": p.realized_pnl,
                    "stop_price": p.stop_price,
                    "target_price": p.target_price,
                } for p in positions]
            )

        return closed


# Global singleton (legacy API)
position_monitor = PositionMonitor()


# ---------------------------------------------------------------------------
# PaperPositionMonitor — auto SL/TP for Kraken paper positions
# ---------------------------------------------------------------------------

from app.db import SessionLocal
from app.db.models import PaperPosition
from app.services.kraken_paper_broker import KrakenPaperBroker
from app.services.lifecycle_recorder import lifecycle_recorder


class PaperPositionMonitor:
    """Monitors open paper positions and triggers SL/TP closes."""

    def __init__(self, broker: KrakenPaperBroker | None = None) -> None:
        self.broker = broker or KrakenPaperBroker()
        self.is_running = False
        self._task: asyncio.Task | None = None
        self.check_interval_seconds = 5.0

    def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("PaperPositionMonitor started")

    def stop(self) -> None:
        self.is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("PaperPositionMonitor stopped")

    async def _monitor_loop(self) -> None:
        """Main loop: check all open positions every N seconds."""
        while self.is_running:
            try:
                await asyncio.to_thread(self._check_positions)
            except Exception as exc:
                logger.error("PaperPositionMonitor error: %s", exc)
            await asyncio.sleep(self.check_interval_seconds)

    def _check_positions(self) -> None:
        """Check each open position against current live price."""
        open_positions_data = []
        with SessionLocal() as db:
            positions = (
                db.query(PaperPosition)
                .filter(PaperPosition.status == "open")
                .all()
            )
            for pos in positions:
                open_positions_data.append({
                    "id": pos.id,
                    "symbol": pos.symbol,
                    "direction": pos.direction,
                    "volume": pos.volume,
                    "stop_loss": pos.stop_loss,
                    "take_profit": pos.take_profit,
                    "candidate_id": pos.candidate_id,
                    "signal_id": pos.signal_id,
                    "strategy_id": pos.strategy_id,
                    "timeframe": pos.timeframe,
                    "avg_entry_price": pos.avg_entry_price,
                    "created_at": pos.created_at,
                })

        for pos_data in open_positions_data:
            try:
                bid, ask = self.broker._get_live_price(pos_data["symbol"])
                current = ask if pos_data["direction"] == "LONG" else bid

                sl_hit = pos_data["stop_loss"] is not None and (
                    (pos_data["direction"] == "LONG" and current <= pos_data["stop_loss"]) or
                    (pos_data["direction"] == "SHORT" and current >= pos_data["stop_loss"])
                )

                tp_hit = pos_data["take_profit"] is not None and (
                    (pos_data["direction"] == "LONG" and current >= pos_data["take_profit"]) or
                    (pos_data["direction"] == "SHORT" and current <= pos_data["take_profit"])
                )

                if sl_hit:
                    logger.info(
                        "SL hit for %s: current=%.4f, sl=%.4f",
                        pos_data["symbol"], current, pos_data["stop_loss"]
                    )
                    snapshot = {
                        "candidate_id": pos_data["candidate_id"],
                        "signal_id": pos_data["signal_id"],
                        "symbol": pos_data["symbol"],
                        "direction": pos_data["direction"],
                        "strategy_id": pos_data["strategy_id"],
                        "timeframe": pos_data["timeframe"],
                        "volume": pos_data["volume"],
                        "avg_entry_price": pos_data["avg_entry_price"],
                        "stop_loss": pos_data["stop_loss"],
                        "take_profit": pos_data["take_profit"],
                        "created_at": pos_data["created_at"],
                    }
                    result = self.broker.close_paper_position(
                        pos_data["symbol"],
                        pos_data["volume"],
                        close_reason="STOP_LOSS",
                    )
                    lifecycle_recorder.record_paper_outcome(
                        position_snapshot=snapshot,
                        close_result=result,
                        close_reason="STOP_LOSS",
                    )

                elif tp_hit:
                    logger.info(
                        "TP hit for %s: current=%.4f, tp=%.4f",
                        pos_data["symbol"], current, pos_data["take_profit"]
                    )
                    snapshot = {
                        "candidate_id": pos_data["candidate_id"],
                        "signal_id": pos_data["signal_id"],
                        "symbol": pos_data["symbol"],
                        "direction": pos_data["direction"],
                        "strategy_id": pos_data["strategy_id"],
                        "timeframe": pos_data["timeframe"],
                        "volume": pos_data["volume"],
                        "avg_entry_price": pos_data["avg_entry_price"],
                        "stop_loss": pos_data["stop_loss"],
                        "take_profit": pos_data["take_profit"],
                        "created_at": pos_data["created_at"],
                    }
                    result = self.broker.close_paper_position(
                        pos_data["symbol"],
                        pos_data["volume"],
                        close_reason="TAKE_PROFIT",
                    )
                    lifecycle_recorder.record_paper_outcome(
                        position_snapshot=snapshot,
                        close_result=result,
                        close_reason="TAKE_PROFIT",
                    )

            except Exception as exc:
                logger.warning("Could not check SL/TP for %s: %s", pos_data["symbol"], exc)

    @staticmethod
    def _position_snapshot(pos: PaperPosition) -> dict:
        return {
            "candidate_id": pos.candidate_id,
            "signal_id": pos.signal_id,
            "symbol": pos.symbol,
            "direction": pos.direction,
            "strategy_id": pos.strategy_id,
            "timeframe": pos.timeframe,
            "volume": pos.volume,
            "avg_entry_price": pos.avg_entry_price,
            "stop_loss": pos.stop_loss,
            "take_profit": pos.take_profit,
            "created_at": pos.created_at,
        }


# Singleton instance for paper trading
paper_position_monitor_instance = PaperPositionMonitor()
