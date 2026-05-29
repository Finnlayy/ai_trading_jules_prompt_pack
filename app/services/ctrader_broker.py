"""cTrader Open API broker adapter.

The official cTrader Open API Python SDK is Twisted-based. This module keeps
that runtime isolated behind a synchronous bridge so the FastAPI/asyncio app can
call the broker without importing or driving Twisted directly.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from app.core.config import (
    CTRADER_ACCESS_TOKEN,
    CTRADER_ACCOUNT_ID,
    CTRADER_CLIENT_ID,
    CTRADER_CLIENT_SECRET,
    CTRADER_ENABLED,
    CTRADER_HOST,
    CTRADER_LIVE_TRADING_ENABLED,
    CTRADER_PORT,
    CTRADER_SYMBOL_MAP_PATH,
)
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum
from app.schemas.journal import DecisionEnum, DirectionEnum, FinalDecisionEnum, TradeJournalEntry
from app.schemas.m8_payload import M8Payload
from app.services.broker_interface import BaseBroker

logger = logging.getLogger(__name__)

CTRADER_DEMO_HOST = "demo.ctraderapi.com"
CTRADER_LIVE_HOST = "live.ctraderapi.com"
DEFAULT_LOTS = 0.01
LOTS_TO_UNITS = 100_000
CTRADER_VOLUME_CENTS = 100


class CTraderBridgeError(RuntimeError):
    """Raised when the cTrader bridge cannot complete a request."""


@dataclass(frozen=True)
class CTraderConfig:
    """Runtime settings for cTrader Open API access."""

    enabled: bool = CTRADER_ENABLED
    live_trading_enabled: bool = CTRADER_LIVE_TRADING_ENABLED
    client_id: str = CTRADER_CLIENT_ID
    client_secret: str = CTRADER_CLIENT_SECRET
    access_token: str = CTRADER_ACCESS_TOKEN
    account_id: int = CTRADER_ACCOUNT_ID
    host: str = CTRADER_HOST
    port: int = CTRADER_PORT
    symbol_map_path: str = CTRADER_SYMBOL_MAP_PATH
    request_timeout_seconds: float = 10.0
    max_retries: int = 5

    @property
    def effective_host(self) -> str:
        """Return the host used for network requests."""
        if self.live_trading_enabled:
            return CTRADER_LIVE_HOST
        return (self.host or CTRADER_DEMO_HOST).strip()

    def has_credentials(self) -> bool:
        """Return True when all cTrader auth fields are configured."""
        return bool(
            self.client_id
            and self.client_secret
            and self.access_token
            and self.account_id > 0
        )


class CTraderClientBridge:
    """Synchronous facade over the Twisted cTrader Open API SDK."""

    _reactor_lock = threading.Lock()
    _reactor_started = False
    _reactor_thread: threading.Thread | None = None

    def __init__(
        self,
        config: CTraderConfig,
        event_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.config = config
        self.event_callback = event_callback
        self.client: Any | None = None
        self.connected = False
        self.app_authenticated = False
        self.account_authenticated = False
        self.last_error: str | None = None
        self.last_connected_at: str | None = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Public bridge operations
    # ------------------------------------------------------------------

    def is_authenticated(self) -> bool:
        """Return True when the socket and both auth layers are active."""
        return bool(self.connected and self.app_authenticated and self.account_authenticated)

    def status(self) -> dict[str, Any]:
        """Return bridge connection and auth state."""
        return {
            "connected": self.connected,
            "app_authenticated": self.app_authenticated,
            "account_authenticated": self.account_authenticated,
            "host": self.config.effective_host,
            "port": self.config.port,
            "last_error": self.last_error,
            "last_connected_at": self.last_connected_at,
        }

    def connect(self) -> dict[str, Any]:
        """Start the Twisted client and complete app/account authentication."""
        if not self.config.enabled:
            raise CTraderBridgeError("CTRADER_DISABLED")
        if not self.config.has_credentials():
            raise CTraderBridgeError("CTRADER_CREDENTIALS_MISSING")

        with self._lock:
            if self.is_authenticated():
                return self.status()

            delay = 0.5
            for attempt in range(1, self.config.max_retries + 1):
                try:
                    self._connect_once()
                    self.last_error = None
                    return self.status()
                except Exception as exc:  # pragma: no cover - real network path
                    self.last_error = str(exc)
                    logger.warning("cTrader connect attempt %s failed: %s", attempt, exc)
                    if attempt == self.config.max_retries:
                        raise CTraderBridgeError(str(exc)) from exc
                    time.sleep(delay)
                    delay = min(delay * 2, 8.0)

        return self.status()

    def disconnect(self) -> dict[str, Any]:
        """Stop the client service without stopping the process-wide reactor."""
        with self._lock:
            if self.client is not None:
                try:
                    sdk = self._load_sdk()
                    sdk["reactor"].callFromThread(self.client.stopService)
                except Exception as exc:  # pragma: no cover - defensive cleanup
                    self.last_error = str(exc)
                    logger.warning("cTrader disconnect failed: %s", exc)
            self.connected = False
            self.app_authenticated = False
            self.account_authenticated = False
        return self.status()

    def refresh_symbols(self) -> dict[str, int]:
        """Fetch enabled symbols from cTrader and return name to symbolId map."""
        self.connect()
        sdk = self._load_sdk()
        req = sdk["ProtoOASymbolsListReq"]()
        req.ctidTraderAccountId = self.config.account_id
        req.includeArchivedSymbols = False
        response = self._send_and_extract(req)

        mapping: dict[str, int] = {}
        for symbol in getattr(response, "symbol", []):
            name = str(getattr(symbol, "symbolName", "")).upper()
            symbol_id = int(getattr(symbol, "symbolId", 0))
            if not name or symbol_id <= 0:
                continue
            mapping[name] = symbol_id
            mapping[_compact_symbol(name)] = symbol_id
        return mapping

    def send_market_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """Send a market order request to cTrader."""
        self.connect()
        sdk = self._load_sdk()
        req = sdk["ProtoOANewOrderReq"]()
        req.ctidTraderAccountId = self.config.account_id
        req.symbolId = int(order["symbol_id"])
        req.orderType = sdk["ProtoOAOrderType"].MARKET
        req.tradeSide = sdk["ProtoOATradeSide"].BUY if order["trade_side"] == "BUY" else sdk["ProtoOATradeSide"].SELL
        req.volume = int(order["volume"])
        req.label = str(order["label"])[:50]
        req.clientOrderId = str(order["client_order_id"])[:50]
        req.comment = str(order.get("comment") or "MetricFlow cTrader")

        if order.get("relative_stop_loss") is not None:
            req.relativeStopLoss = int(order["relative_stop_loss"])
        if order.get("relative_take_profit") is not None:
            req.relativeTakeProfit = int(order["relative_take_profit"])

        response = self._send_and_extract(req)
        return self._message_to_dict(response)

    def close_position(self, position_id: int, volume: int) -> dict[str, Any]:
        """Close the requested position volume."""
        self.connect()
        sdk = self._load_sdk()
        req = sdk["ProtoOAClosePositionReq"]()
        req.ctidTraderAccountId = self.config.account_id
        req.positionId = int(position_id)
        req.volume = int(volume)
        response = self._send_and_extract(req)
        return self._message_to_dict(response)

    def reconcile(self) -> dict[str, Any]:
        """Fetch current open positions and pending orders from cTrader."""
        self.connect()
        sdk = self._load_sdk()
        req = sdk["ProtoOAReconcileReq"]()
        req.ctidTraderAccountId = self.config.account_id
        response = self._send_and_extract(req)
        return {
            "positions": list(getattr(response, "position", [])),
            "orders": [self._message_to_dict(o) for o in getattr(response, "order", [])],
            "raw": self._message_to_dict(response),
        }

    def get_trader(self) -> dict[str, Any]:
        """Fetch trader account information."""
        self.connect()
        sdk = self._load_sdk()
        req = sdk["ProtoOATraderReq"]()
        req.ctidTraderAccountId = self.config.account_id
        response = self._send_and_extract(req)
        trader = getattr(response, "trader", response)
        return self._message_to_dict(trader)

    # ------------------------------------------------------------------
    # Twisted internals
    # ------------------------------------------------------------------

    def _connect_once(self) -> None:
        sdk = self._load_sdk()
        self._ensure_reactor_running(sdk["reactor"])

        self.connected = False
        self.app_authenticated = False
        self.account_authenticated = False

        self.client = sdk["Client"](
            self.config.effective_host,
            self.config.port,
            sdk["TcpProtocol"],
        )
        self.client.setConnectedCallback(self._on_connected)
        self.client.setDisconnectedCallback(self._on_disconnected)
        self.client.setMessageReceivedCallback(self._on_message)

        sdk["reactor"].callFromThread(self.client.startService)
        self._wait_until(lambda: self.connected, "CTRADER_CONNECT_TIMEOUT")

        app_req = sdk["ProtoOAApplicationAuthReq"]()
        app_req.clientId = self.config.client_id
        app_req.clientSecret = self.config.client_secret
        self._send_and_extract(app_req)
        self.app_authenticated = True

        account_req = sdk["ProtoOAAccountAuthReq"]()
        account_req.ctidTraderAccountId = self.config.account_id
        account_req.accessToken = self.config.access_token
        self._send_and_extract(account_req)
        self.account_authenticated = True

    def _send_and_extract(self, message: Any) -> Any:
        sdk = self._load_sdk()
        response = self._send_and_wait(message)
        extracted = sdk["Protobuf"].extract(response)
        error_code = getattr(extracted, "errorCode", "")
        if error_code:
            description = getattr(extracted, "description", "")
            raise CTraderBridgeError(f"{error_code}:{description}")
        return extracted

    def _send_and_wait(self, message: Any) -> Any:
        sdk = self._load_sdk()
        if self.client is None:
            raise CTraderBridgeError("CTRADER_CLIENT_NOT_STARTED")

        done = threading.Event()
        box: dict[str, Any] = {}

        def _send() -> None:
            try:
                deferred = self.client.send(
                    message,
                    responseTimeoutInSeconds=self.config.request_timeout_seconds,
                )
                deferred.addCallbacks(
                    lambda result: self._complete_deferred(box, done, result=result),
                    lambda failure: self._complete_deferred(box, done, error=failure),
                )
            except Exception as exc:  # pragma: no cover - real Twisted path
                self._complete_deferred(box, done, error=exc)

        sdk["reactor"].callFromThread(_send)
        timeout = self.config.request_timeout_seconds + 2.0
        if not done.wait(timeout):
            raise CTraderBridgeError("CTRADER_RESPONSE_TIMEOUT")
        if "error" in box:
            raise CTraderBridgeError(str(box["error"]))
        return box["result"]

    @staticmethod
    def _complete_deferred(
        box: dict[str, Any],
        done: threading.Event,
        result: Any = None,
        error: Any = None,
    ) -> Any:
        if error is not None:
            box["error"] = error
        else:
            box["result"] = result
        done.set()
        return result if error is None else error

    def _on_connected(self, _client: Any) -> None:
        self.connected = True
        self.last_connected_at = datetime.now(timezone.utc).isoformat()

    def _on_disconnected(self, _client: Any, reason: Any) -> None:
        self.connected = False
        self.app_authenticated = False
        self.account_authenticated = False
        self.last_error = str(reason)

    def _on_message(self, _client: Any, message: Any) -> None:
        if self.event_callback is None:
            return
        try:
            sdk = self._load_sdk()
            event = sdk["Protobuf"].extract(message)
            payload_type = int(getattr(event, "payloadType", 0))
            event_payload = self._message_to_dict(event)
            execution_type = sdk["ProtoOAExecutionEvent"]().payloadType
            trader_type = sdk["ProtoOATraderUpdatedEvent"]().payloadType
            if payload_type == execution_type:
                self.event_callback("execution", event_payload)
            elif payload_type == trader_type:
                self.event_callback("trader", event_payload)
        except Exception as exc:  # pragma: no cover - event path is best-effort
            logger.warning("cTrader event handling failed: %s", exc)

    def _wait_until(self, predicate: Callable[[], bool], timeout_reason: str) -> None:
        deadline = time.monotonic() + self.config.request_timeout_seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.05)
        raise CTraderBridgeError(timeout_reason)

    @classmethod
    def _ensure_reactor_running(cls, reactor: Any) -> None:
        with cls._reactor_lock:
            if getattr(reactor, "running", False):
                cls._reactor_started = True
                return
            if cls._reactor_started:
                return

            def _run() -> None:
                reactor.run(installSignalHandlers=False)

            cls._reactor_thread = threading.Thread(
                target=_run,
                name="ctrader-twisted-reactor",
                daemon=True,
            )
            cls._reactor_thread.start()
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if getattr(reactor, "running", False):
                    cls._reactor_started = True
                    return
                time.sleep(0.05)
            raise CTraderBridgeError("CTRADER_REACTOR_START_TIMEOUT")

    @staticmethod
    def _load_sdk() -> dict[str, Any]:
        try:
            from ctrader_open_api import Client, Protobuf, TcpProtocol
            from ctrader_open_api.messages.OpenApiMessages_pb2 import (
                ProtoOAAccountAuthReq,
                ProtoOAApplicationAuthReq,
                ProtoOAClosePositionReq,
                ProtoOAExecutionEvent,
                ProtoOANewOrderReq,
                ProtoOAReconcileReq,
                ProtoOASymbolsListReq,
                ProtoOATraderReq,
                ProtoOATraderUpdatedEvent,
            )
            from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
                ProtoOAOrderType,
                ProtoOATradeSide,
            )
            from google.protobuf.json_format import MessageToDict
            from twisted.internet import reactor
        except Exception as exc:  # pragma: no cover - depends on optional package
            raise CTraderBridgeError("CTRADER_OPEN_API_SDK_MISSING") from exc

        return {
            "Client": Client,
            "TcpProtocol": TcpProtocol,
            "Protobuf": Protobuf,
            "reactor": reactor,
            "MessageToDict": MessageToDict,
            "ProtoOAAccountAuthReq": ProtoOAAccountAuthReq,
            "ProtoOAApplicationAuthReq": ProtoOAApplicationAuthReq,
            "ProtoOAClosePositionReq": ProtoOAClosePositionReq,
            "ProtoOAExecutionEvent": ProtoOAExecutionEvent,
            "ProtoOANewOrderReq": ProtoOANewOrderReq,
            "ProtoOAOrderType": ProtoOAOrderType,
            "ProtoOAReconcileReq": ProtoOAReconcileReq,
            "ProtoOASymbolsListReq": ProtoOASymbolsListReq,
            "ProtoOATradeSide": ProtoOATradeSide,
            "ProtoOATraderReq": ProtoOATraderReq,
            "ProtoOATraderUpdatedEvent": ProtoOATraderUpdatedEvent,
        }

    def _message_to_dict(self, message: Any) -> dict[str, Any]:
        if isinstance(message, dict):
            return message
        try:
            sdk = self._load_sdk()
            return sdk["MessageToDict"](
                message,
                preserving_proto_field_name=True,
                always_print_fields_with_no_presence=False,
            )
        except TypeError:
            sdk = self._load_sdk()
            return sdk["MessageToDict"](message, preserving_proto_field_name=True)
        except Exception:
            return {"raw": str(message)}


class CTraderBroker(BaseBroker):
    """Broker implementation for cTrader Open API."""

    def __init__(
        self,
        config: CTraderConfig | None = None,
        bridge: CTraderClientBridge | None = None,
        journal_path: str = "trade_journal.jsonl",
    ) -> None:
        self.config = config or CTraderConfig()
        self.journal_path = journal_path
        self.journal: list[TradeJournalEntry] = []
        self.bridge = bridge or CTraderClientBridge(self.config, self._handle_bridge_event)
        self.symbol_map: dict[str, int] = self._load_symbol_map()
        self._positions_cache: list[dict[str, Any]] = []
        self._trader_cache: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # BaseBroker interface
    # ------------------------------------------------------------------

    def execute_trade(
        self,
        payload: M8Payload,
        decision: DecisionEnum,
        reject_reason: Optional[str] = None,
        ai_decision: AIDecisionEnum = AIDecisionEnum.PROCEED_TO_SIMULATION,
    ) -> TradeJournalEntry:
        """Execute, close, reject, or dry-run a cTrader order."""
        if decision != DecisionEnum.PROCEED_TO_SIMULATION:
            return self._build_entry(
                payload,
                ai_decision,
                FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={"status": "REJECTED", "reject_reason": reject_reason},
            )

        if not self.config.enabled:
            return self._build_entry(
                payload,
                ai_decision,
                FinalDecisionEnum.EXECUTED_SIM,
                simulated_fill={"mode": "CTRADER_DISABLED"},
                result={"status": "DRY_RUN_CTRADER_DISABLED", "reject_reason": None},
            )

        if payload.intent == "CLOSE":
            return self._close_position(payload, ai_decision)
        return self._open_position(payload, ai_decision)

    def get_positions(self) -> dict[str, Any]:
        """Return open cTrader positions in the live API position shape."""
        if not self.config.enabled:
            return {"status": "disabled", "positions": [], "error": "CTRADER_DISABLED"}

        if self.config.has_credentials():
            try:
                snapshot = self.bridge.reconcile()
                self._positions_cache = [
                    self._normalize_position(p)
                    for p in snapshot.get("positions", [])
                ]
            except Exception as exc:
                logger.warning("cTrader reconcile failed: %s", exc)
                return {
                    "status": "error",
                    "positions": self._positions_cache,
                    "error": str(exc),
                }

        return {
            "status": "ok",
            "positions": self._positions_cache,
            "queried_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_wallet_balances(self, account_mode: str = "SPOT") -> dict[str, Any]:
        """Return cTrader trader balance data."""
        if not self.config.enabled:
            return {"status": "disabled", "balances": [], "error": "CTRADER_DISABLED"}

        try:
            trader = self.bridge.get_trader()
            self._trader_cache = trader
        except Exception as exc:
            logger.warning("cTrader trader query failed: %s", exc)
            if not self._trader_cache:
                return {"status": "error", "balances": [], "error": str(exc)}
            trader = self._trader_cache

        money_digits = int(trader.get("money_digits") or trader.get("moneyDigits") or 2)
        balance = self._money_value(trader.get("balance"), money_digits)
        used_margin = self._cached_used_margin()
        equity = balance
        free_margin = equity - used_margin
        return {
            "status": "ok",
            "account_mode": account_mode.upper(),
            "account_id": self.config.account_id,
            "currency": "ACCOUNT",
            "balance": balance,
            "equity": equity,
            "used_margin": used_margin,
            "free_margin": free_margin,
            "raw": trader,
        }

    def is_live_capable(self) -> bool:
        """Return True only when enabled, live, credentialed, live-hosted, and authenticated."""
        return bool(
            self.config.enabled
            and self.config.live_trading_enabled
            and self.config.has_credentials()
            and self.config.effective_host == CTRADER_LIVE_HOST
            and self.bridge.is_authenticated()
        )

    def is_ready(self) -> bool:
        """Return True when the broker has enough config to operate."""
        return bool(self.config.enabled and self.config.has_credentials())

    def get_broker_name(self) -> str:
        """Human-readable broker name."""
        return "CTrader"

    def get_broker_type(self) -> str:
        """Short type identifier for UI/API."""
        return "ctrader"

    def get_broker_mode(self) -> str:
        """Return live, dry-run, or simulation for this adapter."""
        if self.is_live_capable():
            return "live"
        if self.config.enabled:
            return "dry-run"
        return "simulation"

    def place_direct_order(
        self,
        symbol: str,
        direction: str,
        volume_lots: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        label: str | None = None,
        comment: str = "MetricFlow cTrader",
    ) -> dict[str, Any]:
        """
        Place a market order directly via cTrader Open API.
        Performs margin pre-check, builds the order, and sends it.
        Returns a dict compatible with CTraderOrderResponse.
        """
        if not self.config.enabled:
            return {
                "status": "ERROR",
                "error": "CTRADER_DISABLED",
                "symbol": symbol,
                "direction": direction,
                "volume_lots": volume_lots,
                "margin_checked": False,
            }

        symbol_name = _compact_symbol(symbol)
        symbol_id = self._resolve_symbol_id(symbol_name, refresh=self.config.live_trading_enabled)
        if symbol_id is None:
            return {
                "status": "REJECTED",
                "error": f"CTRADER_SYMBOL_NOT_FOUND:{symbol_name}",
                "symbol": symbol,
                "direction": direction,
                "volume_lots": volume_lots,
                "margin_checked": False,
            }

        # Margin pre-check
        margin_check = self._check_margin(symbol_id, volume_lots)
        if not margin_check["sufficient"]:
            return {
                "status": "REJECTED",
                "error": f"INSUFFICIENT_MARGIN: need ~{margin_check['estimated']:.2f}, have {margin_check['free']:.2f}",
                "symbol": symbol,
                "direction": direction,
                "volume_lots": volume_lots,
                "margin_checked": True,
                "free_margin_before": margin_check["free"],
                "estimated_margin_required": margin_check["estimated"],
            }

        volume = self._lots_to_protocol_volume(volume_lots)
        trade_side = "BUY" if direction.upper() in {"BUY", "LONG"} else "SELL"
        order_label = (label or f"metricflow-direct-{datetime.now(timezone.utc).strftime('%H%M%S')}")[:50]

        order = {
            "symbol": symbol_name,
            "symbol_id": symbol_id,
            "trade_side": trade_side,
            "volume": volume,
            "lots": volume_lots,
            "base_units": volume_lots * LOTS_TO_UNITS,
            "label": order_label,
            "client_order_id": order_label,
            "comment": comment,
        }

        if stop_loss is not None:
            # Relative distance in cents for cTrader protocol
            # We'll use a placeholder; real SL calculation needs current price
            order["relative_stop_loss"] = int(round(abs(stop_loss) * 100_000))
        if take_profit is not None:
            order["relative_take_profit"] = int(round(abs(take_profit) * 100_000))

        if self.config.live_trading_enabled:
            try:
                self.bridge.connect()
                response = self.bridge.send_market_order(order)
                return {
                    "status": "SENT_TO_CTRADER",
                    "order_id": str(response.get("orderId", "") or response.get("order_id", "")),
                    "position_id": str(response.get("positionId", "") or response.get("position_id", "")),
                    "symbol": symbol,
                    "direction": trade_side,
                    "volume_lots": volume_lots,
                    "fill_price": None,
                    "margin_checked": True,
                    "free_margin_before": margin_check["free"],
                    "estimated_margin_required": margin_check["estimated"],
                    "error": None,
                }
            except Exception as exc:
                return {
                    "status": "CTRADER_API_ERROR",
                    "error": str(exc),
                    "symbol": symbol,
                    "direction": trade_side,
                    "volume_lots": volume_lots,
                    "margin_checked": True,
                    "free_margin_before": margin_check["free"],
                    "estimated_margin_required": margin_check["estimated"],
                }

        # Dry-run path
        return {
            "status": "DRY_RUN",
            "order_id": None,
            "position_id": None,
            "symbol": symbol,
            "direction": trade_side,
            "volume_lots": volume_lots,
            "fill_price": None,
            "margin_checked": True,
            "free_margin_before": margin_check["free"],
            "estimated_margin_required": margin_check["estimated"],
            "error": None,
            "preview": order,
        }

    def _check_margin(self, symbol_id: int, volume_lots: float) -> dict[str, Any]:
        """
        Estimate required margin and compare against free margin.
        Returns dict with 'sufficient', 'free', 'estimated'.
        """
        try:
            wallet = self.get_wallet_balances()
            free_margin = float(wallet.get("free_margin") or wallet.get("freeMargin") or 0.0)
        except Exception:
            free_margin = 0.0

        # Very rough margin estimate: 1 lot ≈ 1000 units margin for major FX pairs at 1:30 leverage
        # This is a conservative placeholder; real margin depends on leverage, symbol, and price
        estimated_margin = volume_lots * 1000.0

        # If we can't determine free margin, allow the order (defer to broker)
        if free_margin <= 0:
            return {"sufficient": True, "free": 0.0, "estimated": estimated_margin}

        return {
            "sufficient": free_margin >= estimated_margin,
            "free": free_margin,
            "estimated": estimated_margin,
        }

    def health(self) -> dict[str, Any]:
        """Return cTrader broker health details."""
        bridge_status = self.bridge.status()
        return {
            "name": self.get_broker_name(),
            "type": self.get_broker_type(),
            "mode": self.get_broker_mode(),
            "ready": self.is_ready(),
            "live_capable": self.is_live_capable(),
            "enabled": self.config.enabled,
            "live_trading_enabled": self.config.live_trading_enabled,
            "account_id": self.config.account_id if self.config.account_id else None,
            "host": self.config.effective_host,
            "port": self.config.port,
            "symbols_cached": len(self.symbol_map),
            "connection": bridge_status,
        }

    # ------------------------------------------------------------------
    # Public cTrader-specific methods used by the API router
    # ------------------------------------------------------------------

    def connect(self) -> dict[str, Any]:
        """Manually establish cTrader connection and authentication."""
        self.bridge.connect()
        return self.health()

    def disconnect(self) -> dict[str, Any]:
        """Manually close the cTrader client service."""
        self.bridge.disconnect()
        return self.health()

    def refresh_symbols(self) -> dict[str, int]:
        """Fetch, cache, and return the cTrader symbol map."""
        self.symbol_map = self.bridge.refresh_symbols()
        self._save_symbol_map()
        return self.symbol_map

    def get_symbols(self) -> dict[str, int]:
        """Return the cached symbol map."""
        return dict(self.symbol_map)

    # ------------------------------------------------------------------
    # Trade execution helpers
    # ------------------------------------------------------------------

    def _open_position(self, payload: M8Payload, ai_decision: AIDecisionEnum) -> TradeJournalEntry:
        symbol_name = _compact_symbol(payload.symbol)
        symbol_id = self._resolve_symbol_id(symbol_name, refresh=self.config.live_trading_enabled)
        if symbol_id is None and self.config.live_trading_enabled:
            reason = f"CTRADER_SYMBOL_NOT_FOUND:{symbol_name}"
            return self._build_entry(
                payload,
                ai_decision,
                FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={"status": "REJECTED", "reject_reason": reason},
            )

        lots = self._payload_lots(payload)
        volume = self._lots_to_protocol_volume(lots)
        base_units = lots * LOTS_TO_UNITS
        trade_side = "BUY" if payload.direction == "LONG" else "SELL"
        label = self._label(payload)
        order = {
            "symbol": symbol_name,
            "symbol_id": symbol_id,
            "trade_side": trade_side,
            "volume": volume,
            "lots": lots,
            "base_units": base_units,
            "label": label,
            "client_order_id": label,
            "relative_stop_loss": self._relative_distance(payload.entry_price, payload.stop_price),
            "relative_take_profit": self._relative_distance(payload.entry_price, payload.target_price),
            "comment": "MetricFlow cTrader",
        }

        simulated_fill = {
            "mode": "CTRADER",
            "live_mode": self.config.live_trading_enabled,
            "symbol": symbol_name,
            "symbol_id": symbol_id,
            "trade_side": trade_side,
            "lots": lots,
            "volume": volume,
            "size": base_units,
            "fill_price": payload.entry_price,
            "label": label,
        }
        result: dict[str, Any] = {
            "status": "DRY_RUN_CTRADER",
            "reject_reason": None,
            "order": order,
            "would_execute": True,
        }

        if self.config.live_trading_enabled:
            try:
                result["order_response"] = self.bridge.send_market_order(order)
                result["status"] = "SENT_TO_CTRADER"
            except Exception as exc:
                return self._build_entry(
                    payload,
                    ai_decision,
                    FinalDecisionEnum.REJECTED,
                    simulated_fill=simulated_fill,
                    result={"status": "CTRADER_API_ERROR", "reject_reason": str(exc), "order": order},
                )

        return self._build_entry(
            payload,
            ai_decision,
            FinalDecisionEnum.EXECUTED_SIM,
            simulated_fill=simulated_fill,
            result=result,
        )

    def _close_position(self, payload: M8Payload, ai_decision: AIDecisionEnum) -> TradeJournalEntry:
        symbol_name = _compact_symbol(payload.symbol)
        label = self._label(payload)
        positions_result = self.get_positions()
        positions = positions_result.get("positions", [])
        match = self._find_close_match(positions, symbol_name, payload.direction, label)
        if not match:
            return self._build_entry(
                payload,
                ai_decision,
                FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={"status": "REJECTED", "reject_reason": "CTRADER_POSITION_NOT_FOUND"},
            )

        close_cmd = {
            "position_id": match["position_id"],
            "symbol": match["symbol"],
            "volume": match["volume"],
            "label": match.get("label"),
        }
        simulated_fill = {
            "mode": "CTRADER_CLOSE",
            "live_mode": self.config.live_trading_enabled,
            "size": match.get("size", 0.0),
            "fill_price": payload.entry_price,
            "position_id": match["position_id"],
        }
        result: dict[str, Any] = {
            "status": "DRY_RUN_CTRADER_CLOSE",
            "reject_reason": None,
            "close": close_cmd,
            "would_execute": True,
        }

        if self.config.live_trading_enabled:
            try:
                result["close_response"] = self.bridge.close_position(
                    int(match["position_id"]),
                    int(match["volume"]),
                )
                result["status"] = "SENT_TO_CTRADER_CLOSE"
            except Exception as exc:
                return self._build_entry(
                    payload,
                    ai_decision,
                    FinalDecisionEnum.REJECTED,
                    simulated_fill=simulated_fill,
                    result={"status": "CTRADER_API_ERROR", "reject_reason": str(exc), "close": close_cmd},
                )

        return self._build_entry(
            payload,
            ai_decision,
            FinalDecisionEnum.EXECUTED_SIM,
            simulated_fill=simulated_fill,
            result=result,
        )

    def _resolve_symbol_id(self, symbol: str, refresh: bool = False) -> int | None:
        symbol_id = self.symbol_map.get(symbol.upper())
        if symbol_id is not None:
            return symbol_id
        if not refresh:
            return None
        try:
            self.refresh_symbols()
        except Exception as exc:
            logger.warning("cTrader symbol refresh failed: %s", exc)
            return None
        return self.symbol_map.get(symbol.upper())

    @staticmethod
    def _payload_lots(payload: M8Payload) -> float:
        value = payload.execution_quantity if payload.execution_quantity is not None else DEFAULT_LOTS
        return max(float(value), 0.0)

    @staticmethod
    def _lots_to_protocol_volume(lots: float) -> int:
        return int(round(lots * LOTS_TO_UNITS * CTRADER_VOLUME_CENTS))

    @staticmethod
    def _relative_distance(price_a: float, price_b: float) -> int:
        return int(round(abs(price_a - price_b) * 100_000))

    @staticmethod
    def _label(payload: M8Payload) -> str:
        return f"metricflow-{payload.signal_id}"[:50]

    @staticmethod
    def _trade_rr(payload: M8Payload) -> float:
        if payload.direction == "LONG":
            risk = payload.entry_price - payload.stop_price
            reward = payload.target_price - payload.entry_price
        else:
            risk = payload.stop_price - payload.entry_price
            reward = payload.entry_price - payload.target_price
        return reward / risk if risk > 0 else 0.0

    def _build_entry(
        self,
        payload: M8Payload,
        ai_decision: AIDecisionEnum,
        final_decision: FinalDecisionEnum,
        simulated_fill: dict[str, Any],
        result: dict[str, Any],
    ) -> TradeJournalEntry:
        entry = TradeJournalEntry(
            trade_id=f"ctrader-{payload.signal_id}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            direction=DirectionEnum(payload.direction),
            entry_price=payload.entry_price,
            stop_price=payload.stop_price,
            target_price=payload.target_price,
            risk_reward=self._trade_rr(payload),
            m8_score=payload.confluence_score,
            ai_decision=DecisionEnum(ai_decision.value),
            final_decision=final_decision,
            simulated_fill=simulated_fill,
            result=result,
        )
        self.journal.append(entry)
        return entry

    # ------------------------------------------------------------------
    # Cache and normalization
    # ------------------------------------------------------------------

    def _load_symbol_map(self) -> dict[str, int]:
        path = Path(self.config.symbol_map_path)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read cTrader symbol map: %s", exc)
            return {}
        if not isinstance(data, dict):
            return {}
        return {
            _compact_symbol(str(key)): int(value)
            for key, value in data.items()
            if str(key).strip()
        }

    def _save_symbol_map(self) -> None:
        path = Path(self.config.symbol_map_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.symbol_map, sort_keys=True, separators=(",", ":"))
        path.write_text(payload, encoding="utf-8")

    def _normalize_position(self, position: Any) -> dict[str, Any]:
        if isinstance(position, dict):
            return self._normalize_position_dict(position)

        trade_data = getattr(position, "tradeData", None)
        symbol_id = int(getattr(trade_data, "symbolId", 0) or 0)
        volume = int(getattr(trade_data, "volume", 0) or 0)
        side = int(getattr(trade_data, "tradeSide", 0) or 0)
        price = float(getattr(position, "price", 0.0) or 0.0)
        label = str(getattr(trade_data, "label", "") or "")
        open_timestamp = int(getattr(trade_data, "openTimestamp", 0) or 0)
        symbol = self._symbol_name_from_id(symbol_id)
        size = volume / CTRADER_VOLUME_CENTS
        direction = "LONG" if side == 1 else "SHORT"
        return {
            "trade_id": f"ctrader-position-{getattr(position, 'positionId', '')}",
            "position_id": int(getattr(position, "positionId", 0) or 0),
            "symbol": symbol,
            "symbol_id": symbol_id,
            "direction": direction,
            "entry_price": price,
            "current_price": price,
            "size": size,
            "volume": volume,
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0,
            "open_time": self._datetime_from_millis(open_timestamp),
            "strategy_id": label,
            "label": label,
            "stop_price": float(getattr(position, "stopLoss", 0.0) or 0.0),
            "target_price": float(getattr(position, "takeProfit", 0.0) or 0.0),
            "time_in_trade_minutes": self._minutes_since(open_timestamp),
            "used_margin": self._money_value(
                getattr(position, "usedMargin", 0),
                int(getattr(position, "moneyDigits", 2) or 2),
            ),
        }

    def _normalize_position_dict(self, position: dict[str, Any]) -> dict[str, Any]:
        trade_data = position.get("tradeData") or position.get("trade_data") or {}
        symbol_id = int(position.get("symbol_id") or trade_data.get("symbolId") or trade_data.get("symbol_id") or 0)
        volume = int(position.get("volume") or trade_data.get("volume") or 0)
        raw_side = str(position.get("direction") or trade_data.get("tradeSide") or trade_data.get("trade_side") or "").upper()
        direction = "LONG" if raw_side in {"BUY", "LONG", "1"} else "SHORT"
        price = float(position.get("entry_price") or position.get("price") or 0.0)
        open_time = position.get("open_time")
        if open_time is None:
            open_time = self._datetime_from_millis(int(trade_data.get("openTimestamp") or 0))
        label = str(position.get("label") or trade_data.get("label") or position.get("strategy_id") or "")
        symbol = _compact_symbol(str(position.get("symbol") or self._symbol_name_from_id(symbol_id)))
        return {
            "trade_id": str(position.get("trade_id") or f"ctrader-position-{position.get('position_id') or position.get('positionId') or ''}"),
            "position_id": int(position.get("position_id") or position.get("positionId") or 0),
            "symbol": symbol,
            "symbol_id": symbol_id,
            "direction": direction,
            "entry_price": price,
            "current_price": float(position.get("current_price") or price),
            "size": float(position.get("size") or (volume / CTRADER_VOLUME_CENTS if volume else 0.0)),
            "volume": volume,
            "unrealized_pnl": float(position.get("unrealized_pnl") or 0.0),
            "unrealized_pnl_pct": float(position.get("unrealized_pnl_pct") or 0.0),
            "open_time": open_time,
            "strategy_id": position.get("strategy_id") or label or None,
            "label": label,
            "stop_price": float(position.get("stop_price") or position.get("stopLoss") or 0.0),
            "target_price": float(position.get("target_price") or position.get("takeProfit") or 0.0),
            "time_in_trade_minutes": float(position.get("time_in_trade_minutes") or 0.0),
            "used_margin": float(position.get("used_margin") or position.get("usedMargin") or 0.0),
        }

    def _find_close_match(
        self,
        positions: list[dict[str, Any]],
        symbol: str,
        direction: str,
        label: str,
    ) -> dict[str, Any] | None:
        for position in positions:
            if position.get("label") == label:
                return position
        for position in positions:
            if _compact_symbol(str(position.get("symbol"))) == symbol and str(position.get("direction")).upper() == direction.upper():
                return position
        return None

    def _symbol_name_from_id(self, symbol_id: int) -> str:
        for name, cached_id in self.symbol_map.items():
            if cached_id == symbol_id:
                return name
        return str(symbol_id)

    def _cached_used_margin(self) -> float:
        return sum(float(position.get("used_margin") or 0.0) for position in self._positions_cache)

    @staticmethod
    def _money_value(raw: Any, money_digits: int) -> float:
        try:
            value = float(raw or 0)
        except (TypeError, ValueError):
            return 0.0
        return value / (10 ** money_digits)

    @staticmethod
    def _datetime_from_millis(timestamp_ms: int) -> datetime:
        if timestamp_ms <= 0:
            return datetime.now(timezone.utc)
        return datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)

    @staticmethod
    def _minutes_since(timestamp_ms: int) -> float:
        if timestamp_ms <= 0:
            return 0.0
        started = CTraderBroker._datetime_from_millis(timestamp_ms)
        return round((datetime.now(timezone.utc) - started).total_seconds() / 60.0, 2)

    def _handle_bridge_event(self, event_type: str, payload: dict[str, Any]) -> None:
        try:
            from app.services.dashboard_sse import dashboard_sse_manager

            if event_type == "execution":
                dashboard_sse_manager.broadcast_alert("cTrader execution event received", level="info")
            elif event_type == "trader":
                dashboard_sse_manager.broadcast_alert("cTrader account update received", level="info")
        except Exception as exc:  # pragma: no cover - alerting best-effort
            logger.warning("Failed to broadcast cTrader event: %s", exc)


def _compact_symbol(symbol: str) -> str:
    return (
        symbol.strip()
        .upper()
        .replace("/", "")
        .replace("_", "")
        .replace("-", "")
        .replace(".P", "")
    )
