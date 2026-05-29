"""Kraken REST API broker adapter.

Uses the official krakenex library for HMAC-SHA512 authentication and
private endpoint access. Public market data works without credentials.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import krakenex

from app.core.config import (
    KRAKEN_API_KEY,
    KRAKEN_API_SECRET,
    KRAKEN_ENABLED,
    KRAKEN_LIVE_TRADING_ENABLED,
    KRAKEN_TIMEOUT_SECONDS,
    KRAKEN_DEMO_MODE,
    KRAKEN_SPOT_ONLY,
    KRAKEN_MAX_ORDER_USD,
    KRAKEN_MIN_ORDER_USD,
)
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum
from app.schemas.journal import DecisionEnum, DirectionEnum, FinalDecisionEnum, TradeJournalEntry
from app.schemas.m8_payload import M8Payload
from app.services.broker_interface import BaseBroker

logger = logging.getLogger(__name__)

KRAKEN_DEFAULT_PAIR = "XXBTZUSD"  # BTC/USD on Kraken


class KrakenBrokerError(RuntimeError):
    """Raised when the Kraken API returns an error or the call fails."""


@dataclass(frozen=True)
class KrakenConfig:
    """Runtime settings for Kraken REST API access."""

    enabled: bool = KRAKEN_ENABLED
    live_trading_enabled: bool = KRAKEN_LIVE_TRADING_ENABLED
    api_key: str = KRAKEN_API_KEY
    api_secret: str = KRAKEN_API_SECRET
    timeout_seconds: float = KRAKEN_TIMEOUT_SECONDS
    demo_mode: bool = KRAKEN_DEMO_MODE
    spot_only: bool = KRAKEN_SPOT_ONLY
    max_order_usd: float = KRAKEN_MAX_ORDER_USD
    min_order_usd: float = KRAKEN_MIN_ORDER_USD

    def has_credentials(self) -> bool:
        """Return True when both API key and secret are configured."""
        return bool(self.api_key and self.api_secret)


class KrakenBroker(BaseBroker):
    """Broker for Kraken spot and margin trading via REST API."""

    def __init__(
        self,
        config: Optional[KrakenConfig] = None,
        journal_path: str = "trade_journal.jsonl",
    ) -> None:
        self.config = config or KrakenConfig()
        self.journal_path = journal_path
        self.journal: list[TradeJournalEntry] = []
        self._client: Optional[krakenex.API] = None
        self._last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> krakenex.API:
        """Lazy-initialize the krakenex API client."""
        if self._client is None:
            self._client = krakenex.API(
                key=self.config.api_key or None,
                secret=self.config.api_secret or None,
            )
        return self._client

    def _public(self, method: str, data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Call a Kraken public API endpoint."""
        try:
            result = self._get_client().query_public(method, data or {})
            if result.get("error"):
                errs = ", ".join(result["error"])
                self._last_error = errs
                raise KrakenBrokerError(f"Kraken public error [{method}]: {errs}")
            return result.get("result", {})
        except Exception as exc:
            self._last_error = str(exc)
            raise KrakenBrokerError(f"Kraken public call failed [{method}]: {exc}") from exc

    def _private(self, method: str, data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Call a Kraken private API endpoint."""
        if not self.config.has_credentials():
            raise KrakenBrokerError("Kraken private call requires API key + secret")
        try:
            result = self._get_client().query_private(method, data or {})
            if result.get("error"):
                errs = ", ".join(result["error"])
                self._last_error = errs
                raise KrakenBrokerError(f"Kraken private error [{method}]: {errs}")
            return result.get("result", {})
        except Exception as exc:
            self._last_error = str(exc)
            raise KrakenBrokerError(f"Kraken private call failed [{method}]: {exc}") from exc

    @staticmethod
    def normalize_pair(symbol: str) -> str:
        """Convert common symbol format to Kraken pair notation.

        Examples:
            BTCUSD  → XXBTZUSD
            BTC/USD → XXBTZUSD
            ETHUSD  → XETHZUSD
            SOLUSD  → SOLUSD  (already Kraken format for newer assets)
        """
        mapping = {
            "BTCUSD": "XXBTZUSD",
            "BTC/USD": "XXBTZUSD",
            "BTCUSDT": "XXBTZUSD",
            "ETHUSD": "XETHZUSD",
            "ETH/USD": "XETHZUSD",
            "ETHUSDT": "XETHZUSD",
            "SOLUSD": "SOLUSD",
            "SOL/USD": "SOLUSD",
            "SOLUSDT": "SOLUSD",
            "XRPUSD": "XRPUSD",
            "XRP/USD": "XRPUSD",
            "XRPUSDT": "XRPUSD",
        }
        key = symbol.upper().replace("-", "").replace("/", "")
        # Try direct mapping first
        if key in mapping:
            return mapping[key]
        # If symbol already looks like Kraken pair, return as-is
        if len(symbol) >= 6 and symbol.upper() == symbol:
            return symbol
        # Fallback: return original uppercased
        return symbol.upper()

    # ------------------------------------------------------------------
    # BaseBroker interface
    # ------------------------------------------------------------------

    def is_live_capable(self) -> bool:
        return bool(
            self.config.enabled
            and self.config.live_trading_enabled
            and self.config.has_credentials()
        )

    def is_ready(self) -> bool:
        return bool(self.config.enabled and self.config.has_credentials())

    def get_broker_name(self) -> str:
        return "KrakenBroker"

    def get_broker_type(self) -> str:
        return "kraken"

    def get_broker_mode(self) -> str:
        if self.config.demo_mode:
            return "demo"
        if self.is_live_capable():
            return "live"
        if self.is_ready():
            return "dry-run"
        return "simulation"

    def health(self) -> dict[str, Any]:
        """Return broker health status for monitoring."""
        h = super().health()
        h["credentials_present"] = self.config.has_credentials()
        h["live_trading_enabled"] = self.config.live_trading_enabled
        h["demo_mode"] = self.config.demo_mode
        h["spot_only"] = self.config.spot_only
        h["last_error"] = self._last_error
        return h

    def execute_trade(
        self,
        payload: M8Payload,
        decision: DecisionEnum,
        reject_reason: Optional[str] = None,
        ai_decision: AIDecisionEnum = AIDecisionEnum.PROCEED_TO_SIMULATION,
    ) -> TradeJournalEntry:
        """Execute or simulate a trade based on the signal payload and decision."""
        now = datetime.now(timezone.utc)
        entry = TradeJournalEntry(
            timestamp=now,
            symbol=payload.symbol,
            direction=payload.direction or DirectionEnum.LONG,
            entry_price=payload.price or 0.0,
            exit_price=None,
            volume=0.0,
            pnl=0.0,
            final_decision=FinalDecisionEnum.SKIPPED,
            broker=self.get_broker_name(),
            decision_reason=reject_reason or "",
            confidence=0.0,
            ai_decision=ai_decision,
            human_decision=None,
            strategy_id=payload.strategy_id,
            confluence_score=payload.confluence_score,
            rr_ratio=payload.rr_ratio,
            timeframe=payload.timeframe,
            model_version="",
        )

        if reject_reason:
            entry.final_decision = FinalDecisionEnum.REJECTED
            entry.decision_reason = reject_reason
            self._append_journal(entry)
            return entry

        if not self.is_live_capable():
            entry.final_decision = FinalDecisionEnum.SKIPPED
            entry.decision_reason = "Kraken not live-capable (check credentials + live_trading_enabled)"
            self._append_journal(entry)
            return entry

        # Map direction
        direction = payload.direction or DirectionEnum.LONG
        side = "buy" if direction == DirectionEnum.LONG else "sell"
        pair = self.normalize_pair(payload.symbol)

        # Default order size — placeholder until proper sizing is wired
        order_usd = self.config.min_order_usd
        if payload.price:
            volume = round(order_usd / payload.price, 8)
        else:
            volume = round(order_usd / 30_000, 8)  # rough BTC fallback

        order_type = "market"

        try:
            result = self.place_order(
                pair=pair,
                side=side,
                volume=volume,
                order_type=order_type,
            )
            entry.final_decision = FinalDecisionEnum.APPROVED
            entry.volume = volume
            if result.get("txid"):
                entry.decision_reason = f"Kraken order placed: {result['txid']}"
            else:
                entry.decision_reason = f"Kraken order result: {json.dumps(result)}"
        except Exception as exc:
            entry.final_decision = FinalDecisionEnum.REJECTED
            entry.decision_reason = f"Kraken order failed: {exc}"
            logger.error("Kraken execute_trade failed: %s", exc)

        self._append_journal(entry)
        return entry

    def get_positions(self) -> dict[str, Any]:
        """Return current open positions via Kraken OpenPositions endpoint."""
        try:
            result = self._private("OpenPositions")
            return {
                "status": "ok",
                "positions": result,
                "count": len(result),
            }
        except KrakenBrokerError as exc:
            return {
                "status": "error",
                "error": str(exc),
                "positions": {},
                "count": 0,
            }

    def get_wallet_balances(self, account_mode: str = "SPOT") -> dict[str, Any]:
        """Return wallet balances via Kraken Balance endpoint."""
        try:
            result = self._private("Balance")
            # Also fetch trade balance for USD equivalent
            trade_balance = {}
            try:
                trade_balance = self._private("TradeBalance")
            except KrakenBrokerError:
                pass

            return {
                "status": "ok",
                "account_mode": account_mode,
                "balances": result,
                "trade_balance": trade_balance,
                "raw": {"balance": result, "trade_balance": trade_balance},
            }
        except KrakenBrokerError as exc:
            return {
                "status": "error",
                "error": str(exc),
                "balances": {},
                "trade_balance": {},
                "raw": None,
            }

    def reconcile_ledger(self) -> dict[str, Any]:
        """Reconcile local ledger with exchange closed orders."""
        try:
            result = self._private("ClosedOrders")
            return {
                "checked": True,
                "count": len(result.get("closed", {})),
                "raw": result,
            }
        except KrakenBrokerError as exc:
            return {
                "checked": False,
                "reason": str(exc),
                "count": 0,
            }

    # ------------------------------------------------------------------
    # Public market data (no auth required)
    # ------------------------------------------------------------------

    def get_server_time(self) -> dict[str, Any]:
        """Get Kraken server time — useful for connectivity checks."""
        return self._public("Time")

    def get_ticker(self, pair: str) -> dict[str, Any]:
        """Get ticker data for a given pair."""
        normalized = self.normalize_pair(pair)
        result = self._public("Ticker", {"pair": normalized})
        # Kraken returns keyed by actual pair name
        return result

    def get_asset_pairs(self) -> dict[str, Any]:
        """Get available asset pairs."""
        return self._public("AssetPairs")

    def get_ohlc(self, pair: str, interval: int = 60, since: int | None = None) -> list[list[float]]:
        """Get OHLCV data for a given pair.

        Args:
            pair: Trading pair (e.g. SOLUSD)
            interval: Candle interval in minutes (1, 5, 15, 30, 60, 240, 1440, 10080, 21600)
            since: Return committed OHLC data since given ID

        Returns:
            List of [time, open, high, low, close, vwap, volume, count] bars.
            For simplicity we return [time, open, high, low, close, volume].
        """
        normalized = self.normalize_pair(pair)
        params: dict[str, Any] = {"pair": normalized, "interval": interval}
        if since is not None:
            params["since"] = since

        result = self._public("OHLC", params)
        key = list(result.keys())[0]
        raw_bars = result[key]

        # Kraken returns: [time, open, high, low, close, vwap, volume, count]
        # We normalize to [time, open, high, low, close, volume]
        bars: list[list[float]] = []
        for bar in raw_bars:
            bars.append([
                float(bar[0]),   # time
                float(bar[1]),   # open
                float(bar[2]),   # high
                float(bar[3]),   # low
                float(bar[4]),   # close
                float(bar[6]),   # volume
            ])
        return bars

    # ------------------------------------------------------------------
    # Order placement
    # ------------------------------------------------------------------

    def place_order(
        self,
        pair: str,
        side: str,
        volume: float,
        order_type: str = "market",
        price: Optional[float] = None,
        leverage: Optional[str] = None,
        validate: bool = False,
        oflags: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Place an order on Kraken.

        Args:
            pair: Trading pair (e.g. XXBTZUSD)
            side: "buy" or "sell"
            volume: Order volume in base currency
            order_type: "market", "limit", "stop-loss", etc.
            price: Limit price (required for limit orders)
            leverage: Leverage amount (e.g. "2:1"). None = no margin.
            validate: If True, only validate the order without placing it.
            oflags: Order flags like ["post"], ["fcib"], ["fciq"]
        """
        if not self.config.has_credentials():
            raise KrakenBrokerError("Cannot place order: missing API credentials")

        if self.config.spot_only and leverage:
            raise KrakenBrokerError("Spot-only mode: leverage orders are blocked")

        data: dict[str, Any] = {
            "pair": self.normalize_pair(pair),
            "type": side.lower(),
            "ordertype": order_type.lower(),
            "volume": str(volume),
        }
        if price is not None:
            data["price"] = str(price)
        if leverage is not None:
            data["leverage"] = leverage
        if validate:
            data["validate"] = "true"
        if oflags:
            data["oflags"] = ",".join(oflags)

        # If not live-capable, force validate mode (dry-run)
        if not self.is_live_capable():
            data["validate"] = "true"
            logger.info("Kraken order forced to validate mode (dry-run): %s", data)

        result = self._private("AddOrder", data)
        return result

    def cancel_order(self, txid: str) -> dict[str, Any]:
        """Cancel an open order by transaction ID."""
        return self._private("CancelOrder", {"txid": txid})

    def get_open_orders(self) -> dict[str, Any]:
        """Get all open orders."""
        return self._private("OpenOrders")

    def get_closed_orders(self) -> dict[str, Any]:
        """Get closed orders."""
        return self._private("ClosedOrders")

    def query_orders(self, txids: list[str]) -> dict[str, Any]:
        """Query specific orders by transaction IDs."""
        return self._private("QueryOrders", {"txid": ",".join(txids)})

    # ------------------------------------------------------------------
    # Journal persistence
    # ------------------------------------------------------------------

    def _append_journal(self, entry: TradeJournalEntry) -> None:
        """Append a trade journal entry to the NDJSON file."""
        path = Path(self.journal_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(entry.model_dump_json() + "\n")
        self.journal.append(entry)
