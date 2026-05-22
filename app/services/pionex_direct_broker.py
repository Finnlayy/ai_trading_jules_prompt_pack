from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config import (
    PIONEX_DIRECT_ENABLED,
    PIONEX_DIRECT_LIVE_TRADING_ENABLED,
    PIONEX_API_KEY,
    PIONEX_API_SECRET,
    PIONEX_ALLOWED_SYMBOLS,
    KELLY_DEPLOY_MODE,
    KELLY_FIXED_RISK_PCT,
    KELLY_LOOKBACK_TRADES,
    KELLY_MAX_RISK_PCT,
    KELLY_MIN_RISK_PCT,
    KELLY_MIN_TRADES,
    KELLY_PAYOFF_BUFFER,
    PIONEX_ALLOWED_SYMBOLS,
    PIONEX_API_KEY,
    PIONEX_API_SECRET,
    PIONEX_DIRECT_ALLOW_PAYLOAD_LEVERAGE,
    PIONEX_DIRECT_BASE_URL,
    PIONEX_DIRECT_DEFAULT_FUTURES_SYMBOL,
    PIONEX_DIRECT_DEFAULT_SPOT_SYMBOL,
    PIONEX_DIRECT_ENABLED,
    PIONEX_DIRECT_FUTURES_ENABLED,
    PIONEX_DIRECT_FUTURES_MODE,
    PIONEX_DIRECT_LIVE_TRADING_ENABLED,
    PIONEX_DIRECT_MAX_BASE_SIZE,
    PIONEX_DIRECT_MAX_ORDER_USDT,
    PIONEX_DIRECT_MIN_BASE_SIZE,
    PIONEX_DIRECT_MIN_ORDER_USDT,
    PIONEX_DIRECT_TIMEOUT_SECONDS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_NOTIFICATIONS_ENABLED,
)
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum
from app.schemas.journal import DecisionEnum, DirectionEnum, FinalDecisionEnum, TradeJournalEntry
from app.schemas.m8_payload import M8Payload
from app.services.pionex_api import PionexAPIError, PionexClient, PionexCredentials
from app.services.pionex_kelly_sizer import KellyConfig, KellySizer
from app.services.pionex_position_ledger import PositionLedger
from app.services.telegram_notifier import TelegramConfig, TelegramNotifier
from app.services.war_room_rules import classify_order


@dataclass(frozen=True)
class PionexDirectConfig:
    enabled: bool = PIONEX_DIRECT_ENABLED
    live_trading_enabled: bool = PIONEX_DIRECT_LIVE_TRADING_ENABLED
    api_key: str = PIONEX_API_KEY
    api_secret: str = PIONEX_API_SECRET
    allowed_symbols: list[str] = None

    def __post_init__(self):
        if self.allowed_symbols is None:
            symbols = [s.strip() for s in PIONEX_ALLOWED_SYMBOLS.split(",") if s.strip()]
            object.__setattr__(self, 'allowed_symbols', symbols)


class PionexDirectBroker:
    """
    Broker adapter for the external Pionex Direct API.

    Safety defaults:
    - If PIONEX_DIRECT_LIVE_TRADING_ENABLED=false, operates in DRY-RUN mode.
    - Enforces a strict allowlist of symbols.
    - Only forwards signals after the deterministic risk engine returns PROCEED_TO_SIMULATION.
    """

    def __init__(self, config: Optional[PionexDirectConfig] = None) -> None:
        self.config = config or PionexDirectConfig()
        self.journal: list[TradeJournalEntry] = []

    def is_ready(self) -> bool:
        return bool(
            self.config.enabled
            and self.config.api_key
            and self.config.api_secret
        )

    def _map_symbol(self, symbol: str) -> Optional[str]:
        # Handle cases like XAGUSDT.P -> XAG_USDT_PERP
        mapping = {
            "XAGUSDT.P": "XAG_USDT_PERP",
            "BTCUSD": "BTC_USDT",
            "ETHUSD": "ETH_USDT",
        }
        mapped = mapping.get(symbol, symbol)
        if mapped in self.config.allowed_symbols:
            return mapped
        return None

    def execute_trade(
        self,
        payload: M8Payload,
        decision: DecisionEnum,
        reject_reason: Optional[str] = None,
        ai_decision: AIDecisionEnum = AIDecisionEnum.PROCEED_TO_SIMULATION,
    ) -> TradeJournalEntry:
        simulated_fill: Dict[str, Any] = {}
        result: Dict[str, Any]

    base_url: str = PIONEX_DIRECT_BASE_URL
    timeout_seconds: float = PIONEX_DIRECT_TIMEOUT_SECONDS
    allowed_symbols: tuple[str, ...] = tuple(PIONEX_ALLOWED_SYMBOLS)
    default_spot_symbol: str = PIONEX_DIRECT_DEFAULT_SPOT_SYMBOL
    default_futures_symbol: str = PIONEX_DIRECT_DEFAULT_FUTURES_SYMBOL
    futures_enabled: bool = PIONEX_DIRECT_FUTURES_ENABLED
    futures_mode: str = PIONEX_DIRECT_FUTURES_MODE
    allow_payload_leverage: bool = PIONEX_DIRECT_ALLOW_PAYLOAD_LEVERAGE


class PionexDirectBroker:
    def __init__(
        self,
        config: Optional[PionexDirectConfig] = None,
        journal_path: str = "trade_journal.jsonl",
    ) -> None:
        self.config = config or PionexDirectConfig()
        self.journal_path = journal_path
        self.journal: list[TradeJournalEntry] = []
        self.ledger = PositionLedger()
        self.ledger.restore_from_journal(journal_path)
        self.sizer = KellySizer(
            KellyConfig(
                deploy_mode=KELLY_DEPLOY_MODE,
                lookback_trades=KELLY_LOOKBACK_TRADES,
                min_trades=KELLY_MIN_TRADES,
                fixed_risk_pct=KELLY_FIXED_RISK_PCT,
                min_risk_pct=KELLY_MIN_RISK_PCT,
                max_risk_pct=KELLY_MAX_RISK_PCT,
                payoff_buffer=KELLY_PAYOFF_BUFFER,
                min_order_usdt=PIONEX_DIRECT_MIN_ORDER_USDT,
                max_order_usdt=PIONEX_DIRECT_MAX_ORDER_USDT,
                min_base_size=PIONEX_DIRECT_MIN_BASE_SIZE,
                max_base_size=PIONEX_DIRECT_MAX_BASE_SIZE,
            ),
            journal_path=journal_path,
        )
        self.notifier = TelegramNotifier(
            TelegramConfig(
                enabled=TELEGRAM_NOTIFICATIONS_ENABLED,
                bot_token=TELEGRAM_BOT_TOKEN,
                chat_id=TELEGRAM_CHAT_ID,
            )
        )
        self.client: Optional[PionexClient] = None
        if self._has_credentials():
            self.client = PionexClient(
                PionexCredentials(
                    api_key=self.config.api_key,
                    api_secret=self.config.api_secret,
                    base_url=self.config.base_url,
                    timeout_seconds=self.config.timeout_seconds,
                )
            )

    def _has_credentials(self) -> bool:
        return bool(self.config.api_key and self.config.api_secret)

    def is_live_capable(self) -> bool:
        return bool(
            self.config.enabled
            and self.config.live_trading_enabled
            and self._has_credentials()
        )

    def is_ready(self) -> bool:
        if not self.config.enabled:
            return False
        if not self.config.allowed_symbols:
            return False
        if self.config.live_trading_enabled and not self._has_credentials():
            return False
        return True

    def get_balance(self, account_mode: str = "SPOT") -> dict[str, Any]:
        if not self.client:
            return {"error": "PIONEX_CLIENT_NOT_CONFIGURED"}
        try:
            balance = self.client.get_balance(
                coin="USDT",
                account="spot" if account_mode.upper() == "SPOT" else "futures",
            )
            return {"coin": "USDT", "account_mode": account_mode.upper(), "balance": balance}
        except PionexAPIError as exc:
            return {"error": exc.message, "retryable": exc.retryable}

    @staticmethod
    def _is_perp_symbol(symbol: str) -> bool:
        value = (symbol or "").strip().upper()
        return value.endswith(".P") or value.endswith("_PERP")

    def _normalized_account_mode(self, payload: M8Payload) -> str:
        account_mode = payload.account_mode.upper()
        if account_mode == "SPOT" and self._is_perp_symbol(payload.symbol):
            return "FUTURES"
        return account_mode

    def _normalized_symbol(self, symbol: str, account_mode: str) -> str:
        value = (symbol or "").strip().upper()
        if not value:
            value = (
                self.config.default_futures_symbol
                if account_mode == "FUTURES"
                else self.config.default_spot_symbol
            )
        if value.endswith(".P"):
            value = value[:-2]
        if "_" not in value and value.endswith("USDT"):
            value = value.replace("USDT", "_USDT")
        if account_mode == "FUTURES" and not value.endswith("_PERP"):
            value = f"{value}_PERP"
        return value

    def _symbol_allowed(self, symbol: str) -> bool:
        if not self.config.allowed_symbols:
            return False
        return symbol.upper() in {s.upper() for s in self.config.allowed_symbols}

    @staticmethod
    def _trade_rr(payload: M8Payload) -> float:
        if payload.direction == "LONG":
            risk = payload.entry_price - payload.stop_price
            reward = payload.target_price - payload.entry_price
        else:
            risk = payload.stop_price - payload.entry_price
            reward = payload.entry_price - payload.target_price

        rr_ratio = reward / risk if risk > 0 else 0.0

        if decision != DecisionEnum.PROCEED_TO_SIMULATION:
            final_decision = FinalDecisionEnum.REJECTED
            result = {"status": "REJECTED", "reject_reason": reject_reason}
        else:
            mapped_symbol = self._map_symbol(payload.symbol)
            if not mapped_symbol:
                final_decision = FinalDecisionEnum.REJECTED
                result = {
                    "status": "REJECTED",
                    "reject_reason": f"SYMBOL_NOT_IN_ALLOWLIST: {payload.symbol} (mapped: {mapped_symbol})"
                }
            elif not self.config.enabled or not self.is_ready():
                final_decision = FinalDecisionEnum.REJECTED
                result = {
                    "status": "CONFIG_ERROR",
                    "reject_reason": "PIONEX_DIRECT_NOT_CONFIGURED"
                }
            else:
                simulated_fill = {
                    "fill_price": payload.entry_price,
                    "fee": 0.0,
                    "slippage": 0.0,
                    "mode": "PIONEX_DIRECT",
                    "live_trading_enabled": self.config.live_trading_enabled,
                }

                if not self.config.live_trading_enabled:
                    final_decision = FinalDecisionEnum.EXECUTED_SIM
                    result = {
                        "status": "DRY_RUN_DIRECT",
                        "reject_reason": None,
                        "mapped_symbol": mapped_symbol,
                    }
                else:
                    final_decision, result = self._send_to_direct_api(payload, mapped_symbol)

        entry = TradeJournalEntry(
            trade_id=f"pionex-direct-{payload.signal_id}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        return reward / risk if risk > 0 else 0.0

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _build_entry(
        self,
        payload: M8Payload,
        decision: DecisionEnum,
        reject_reason: Optional[str],
        ai_decision: AIDecisionEnum,
        final_decision: FinalDecisionEnum,
        simulated_fill: Dict[str, Any],
        result: Dict[str, Any],
    ) -> TradeJournalEntry:
        entry = TradeJournalEntry(
            trade_id=f"pionex-direct-{payload.signal_id}",
            timestamp=self._utc_now(),
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            direction=DirectionEnum(payload.direction),
            entry_price=payload.entry_price,
            stop_price=payload.stop_price,
            target_price=payload.target_price,
            risk_reward=rr_ratio,
            risk_reward=self._trade_rr(payload),
            m8_score=payload.confluence_score,
            ai_decision=DecisionEnum(ai_decision.value),
            final_decision=final_decision,
            simulated_fill=simulated_fill,
            result=result,
        )

        self.journal.append(entry)
        return entry

    def _send_to_direct_api(self, payload: M8Payload, mapped_symbol: str) -> tuple[FinalDecisionEnum, Dict[str, Any]]:
        # In a real implementation, this would construct the authenticated requests
        # to the actual Pionex Direct API and handle signatures.

        # Simulating successful API call for live trading MVP architecture
        return FinalDecisionEnum.EXECUTED_SIM, {
            "status": "SENT_TO_PIONEX_DIRECT",
            "reject_reason": None,
            "mapped_symbol": mapped_symbol,
            "mock_live_response": "ok"
        }
        self.journal.append(entry)
        return entry

    def execute_trade(
        self,
        payload: M8Payload,
        decision: DecisionEnum,
        reject_reason: Optional[str] = None,
        ai_decision: AIDecisionEnum = AIDecisionEnum.PROCEED_TO_SIMULATION,
    ) -> TradeJournalEntry:
        if decision != DecisionEnum.PROCEED_TO_SIMULATION:
            self.notifier.send_reject(payload.symbol, reject_reason or "REJECTED", f"pionex-direct-{payload.signal_id}", payload.intent)
            return self._build_entry(
                payload=payload,
                decision=decision,
                reject_reason=reject_reason,
                ai_decision=ai_decision,
                final_decision=FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={"status": "REJECTED", "reject_reason": reject_reason},
            )

        if not self.config.enabled:
            return self._build_entry(
                payload=payload,
                decision=decision,
                reject_reason=None,
                ai_decision=ai_decision,
                final_decision=FinalDecisionEnum.EXECUTED_SIM,
                simulated_fill={"mode": "PIONEX_DIRECT_DISABLED"},
                result={"status": "DRY_RUN_DIRECT_DISABLED", "reject_reason": None},
            )

        account_mode = self._normalized_account_mode(payload)
        if account_mode == "FUTURES" and not self.config.futures_enabled:
            self.notifier.send_reject(payload.symbol, "FUTURES_DISABLED", f"pionex-direct-{payload.signal_id}", payload.intent)
            return self._build_entry(
                payload=payload,
                decision=decision,
                reject_reason="FUTURES_DISABLED",
                ai_decision=ai_decision,
                final_decision=FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={"status": "REJECTED", "reject_reason": "FUTURES_DISABLED"},
            )

        symbol = self._normalized_symbol(payload.symbol, account_mode)
        if not self._symbol_allowed(symbol):
            reason = f"SYMBOL_NOT_ALLOWED:{symbol}"
            self.notifier.send_reject(symbol, reason, f"pionex-direct-{payload.signal_id}", payload.intent)
            return self._build_entry(
                payload=payload,
                decision=decision,
                reject_reason=reason,
                ai_decision=ai_decision,
                final_decision=FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={"status": "REJECTED", "reject_reason": reason},
            )

        if payload.intent == "CLOSE":
            return self._close_position(payload, symbol, account_mode, ai_decision)
        return self._open_position(payload, symbol, account_mode, ai_decision)

    def _open_position(self, payload: M8Payload, symbol: str, account_mode: str, ai_decision: AIDecisionEnum) -> TradeJournalEntry:
        war_room = classify_order(payload)
        if war_room.reject_reason:
            self.notifier.send_reject(symbol, war_room.reject_reason, f"pionex-direct-{payload.signal_id}", payload.intent)
            return self._build_entry(
                payload=payload,
                decision=DecisionEnum.PROCEED_TO_SIMULATION,
                reject_reason=war_room.reject_reason,
                ai_decision=ai_decision,
                final_decision=FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={
                    "status": "REJECTED",
                    "reject_reason": war_room.reject_reason,
                    "war_room": war_room.to_dict(),
                },
            )

        if account_mode == "SPOT" and payload.direction == "SHORT":
            reason = "SPOT_SHORT_NOT_SUPPORTED"
            self.notifier.send_reject(symbol, reason, f"pionex-direct-{payload.signal_id}", payload.intent)
            return self._build_entry(
                payload=payload,
                decision=DecisionEnum.PROCEED_TO_SIMULATION,
                reject_reason=reason,
                ai_decision=ai_decision,
                final_decision=FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={"status": "REJECTED", "reject_reason": reason},
            )

        if self.client is None:
            balance = 0.0
        else:
            try:
                balance = self.client.get_balance(coin="USDT", account="spot" if account_mode == "SPOT" else "futures")
            except PionexAPIError:
                balance = 0.0

        if balance <= 0:
            # Keep deterministic minimum sizing in dry/limited environments.
            balance = 100.0

        sizing = self.sizer.size_trade(
            payload,
            balance=balance,
            risk_cap_pct=war_room.risk_cap_pct,
        )
        entry_side = payload.direction.upper()
        live_mode = self.config.live_trading_enabled and self.client is not None
        trade_id = f"pionex-direct-{payload.signal_id}"
        client_order_id = f"{payload.signal_id}_{symbol}_{account_mode}_{entry_side}_{payload.intent}"

        simulated_fill: dict[str, Any] = {
            "mode": "PIONEX_DIRECT",
            "live_mode": live_mode,
            "symbol": symbol,
            "account_mode": account_mode,
            "entry_side": entry_side,
            "size_base": sizing.size_base,
            "order_value_usdt": sizing.order_value_usdt,
            "risk_pct": sizing.risk_pct,
            "kelly_fraction": sizing.kelly_fraction,
            "war_room": war_room.to_dict(),
            "client_order_id": client_order_id,
        }

        result: dict[str, Any] = {
            "status": "DRY_RUN_DIRECT",
            "reject_reason": None,
            "balance": balance,
            "risk_amount": sizing.risk_amount,
            "war_room": war_room.to_dict(),
            "ledger_delta": {
                "action": "ENTRY",
                "symbol": symbol,
                "account_mode": account_mode,
                "direction": entry_side,
                "size_base": sizing.size_base,
                "entry_price": payload.entry_price,
                "risk_amount": sizing.risk_amount,
                "client_order_id": client_order_id,
            },
        }

        if live_mode and self.client:
            try:
                order_data = self._send_live_entry(
                    payload=payload,
                    symbol=symbol,
                    account_mode=account_mode,
                    size_base=sizing.size_base,
                    order_value_usdt=sizing.order_value_usdt,
                    client_order_id=client_order_id,
                )
                result["status"] = "SENT_TO_PIONEX_DIRECT"
                result["order"] = order_data
            except PionexAPIError as exc:
                self.notifier.send_error("ENTRY", exc.message)
                return self._build_entry(
                    payload=payload,
                    decision=DecisionEnum.PROCEED_TO_SIMULATION,
                    reject_reason=exc.message,
                    ai_decision=ai_decision,
                    final_decision=FinalDecisionEnum.REJECTED,
                    simulated_fill=simulated_fill,
                    result={"status": "API_ERROR", "reject_reason": exc.message},
                )

        self.ledger.apply_entry(
            symbol=symbol,
            account_mode=account_mode,
            direction=entry_side,
            size_base=sizing.size_base,
            entry_price=payload.entry_price,
            risk_amount=sizing.risk_amount,
        )
        self.notifier.send_execution(
            symbol=symbol,
            account_mode=account_mode,
            intent=payload.intent,
            side=entry_side,
            size=sizing.size_base,
            price=payload.entry_price,
            trade_id=trade_id,
        )
        return self._build_entry(
            payload=payload,
            decision=DecisionEnum.PROCEED_TO_SIMULATION,
            reject_reason=None,
            ai_decision=ai_decision,
            final_decision=FinalDecisionEnum.EXECUTED_SIM,
            simulated_fill=simulated_fill,
            result=result,
        )

    def _send_live_entry(
        self,
        payload: M8Payload,
        symbol: str,
        account_mode: str,
        size_base: float,
        order_value_usdt: float,
        client_order_id: Optional[str] = None,
    ) -> dict[str, Any]:
        assert self.client is not None
        if account_mode == "SPOT":
            if payload.direction == "LONG":
                return self.client.place_spot_market_buy(symbol=symbol, amount_usdt=order_value_usdt, client_order_id=client_order_id)
            if payload.direction == "SHORT":
                raise PionexAPIError("SPOT_SHORT_NOT_SUPPORTED", retryable=False)
            raise PionexAPIError("UNKNOWN_DIRECTION", retryable=False)

        if self.config.futures_mode == "mode3" and self.config.allow_payload_leverage and payload.leverage:
            self.client.set_futures_leverage(symbol=symbol, leverage=payload.leverage)
        side = "BUY" if payload.direction == "LONG" else "SELL"
        return self.client.place_futures_market_order(
            symbol=symbol,
            side=side,
            size=size_base,
            reduce_only=False,
            position_side="BOTH",
            client_order_id=client_order_id,
        )

    def _close_position(self, payload: M8Payload, symbol: str, account_mode: str, ai_decision: AIDecisionEnum) -> TradeJournalEntry:
        trade_id = f"pionex-direct-{payload.signal_id}"
        position = self.ledger.get(symbol=symbol, account_mode=account_mode)
        if not position:
            reason = "NO_OPEN_POSITION"
            self.notifier.send_reject(symbol, reason, trade_id, payload.intent)
            return self._build_entry(
                payload=payload,
                decision=DecisionEnum.PROCEED_TO_SIMULATION,
                reject_reason=reason,
                ai_decision=ai_decision,
                final_decision=FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={"status": "REJECTED", "reject_reason": reason},
            )

        close_size = payload.execution_quantity if payload.execution_quantity and payload.execution_quantity > 0 else None
        close_info = self.ledger.apply_close(symbol=symbol, account_mode=account_mode, close_size_base=close_size)
        closed_size_base = float(close_info["closed_size_base"])
        entry_price = float(close_info["entry_price"])
        risk_amount = float(close_info["risk_amount"])
        direction = str(close_info["direction"])

        if closed_size_base <= 0:
            reason = "ZERO_CLOSE_SIZE"
            self.notifier.send_reject(symbol, reason, trade_id, payload.intent)
            return self._build_entry(
                payload=payload,
                decision=DecisionEnum.PROCEED_TO_SIMULATION,
                reject_reason=reason,
                ai_decision=ai_decision,
                final_decision=FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={"status": "REJECTED", "reject_reason": reason},
            )

        if direction == "LONG":
            realized_pnl = (payload.entry_price - entry_price) * closed_size_base
            close_side = "SELL"
        else:
            realized_pnl = (entry_price - payload.entry_price) * closed_size_base
            close_side = "BUY"

        live_mode = self.config.live_trading_enabled and self.client is not None
        client_order_id = f"{payload.signal_id}_{symbol}_{account_mode}_{close_side}_{payload.intent}"

        simulated_fill = {
            "mode": "PIONEX_DIRECT",
            "live_mode": live_mode,
            "symbol": symbol,
            "account_mode": account_mode,
            "close_side": close_side,
            "closed_size_base": closed_size_base,
            "entry_price": entry_price,
            "close_price": payload.entry_price,
            "client_order_id": client_order_id,
        }

        result: dict[str, Any] = {
            "status": "CLOSED_DRY_RUN",
            "reject_reason": None,
            "realized_pnl_quote": realized_pnl,
            "risk_amount": risk_amount,
            "ledger_delta": {
                "action": "CLOSE",
                "symbol": symbol,
                "account_mode": account_mode,
                "closed_size_base": closed_size_base,
                "client_order_id": client_order_id,
            },
        }

        if live_mode and self.client:
            try:
                order = self._send_live_close(
                    symbol=symbol,
                    account_mode=account_mode,
                    close_side=close_side,
                    size_base=closed_size_base,
                    client_order_id=client_order_id,
                )
                result["status"] = "CLOSED_LIVE"
                result["order"] = order
            except PionexAPIError as exc:
                # Rollback local ledger close when live close fails.
                self.ledger.apply_entry(
                    symbol=symbol,
                    account_mode=account_mode,
                    direction=direction,
                    size_base=closed_size_base,
                    entry_price=entry_price,
                    risk_amount=risk_amount,
                )
                self.notifier.send_error("CLOSE", exc.message)
                return self._build_entry(
                    payload=payload,
                    decision=DecisionEnum.PROCEED_TO_SIMULATION,
                    reject_reason=exc.message,
                    ai_decision=ai_decision,
                    final_decision=FinalDecisionEnum.REJECTED,
                    simulated_fill=simulated_fill,
                    result={"status": "API_ERROR", "reject_reason": exc.message},
                )

        self.notifier.send_execution(
            symbol=symbol,
            account_mode=account_mode,
            intent=payload.intent,
            side=close_side,
            size=closed_size_base,
            price=payload.entry_price,
            trade_id=trade_id,
        )
        return self._build_entry(
            payload=payload,
            decision=DecisionEnum.PROCEED_TO_SIMULATION,
            reject_reason=None,
            ai_decision=ai_decision,
            final_decision=FinalDecisionEnum.EXECUTED_SIM,
            simulated_fill=simulated_fill,
            result=result,
        )

    def _send_live_close(
        self,
        symbol: str,
        account_mode: str,
        close_side: str,
        size_base: float,
        client_order_id: Optional[str] = None,
    ) -> dict[str, Any]:
        assert self.client is not None
        if account_mode == "SPOT":
            return self.client.place_spot_market_sell(symbol=symbol, size=size_base, client_order_id=client_order_id)
        return self.client.place_futures_market_order(
            symbol=symbol,
            side=close_side,
            size=size_base,
            reduce_only=True,
            position_side="BOTH",
            client_order_id=client_order_id,
        )
