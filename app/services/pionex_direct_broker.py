from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config import (
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
from app.services.broker_interface import BaseBroker
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
    allowed_symbols: Optional[tuple[str, ...]] = None
    base_url: str = PIONEX_DIRECT_BASE_URL
    timeout_seconds: float = PIONEX_DIRECT_TIMEOUT_SECONDS
    default_spot_symbol: str = PIONEX_DIRECT_DEFAULT_SPOT_SYMBOL
    default_futures_symbol: str = PIONEX_DIRECT_DEFAULT_FUTURES_SYMBOL
    futures_enabled: bool = PIONEX_DIRECT_FUTURES_ENABLED
    futures_mode: str = PIONEX_DIRECT_FUTURES_MODE
    allow_payload_leverage: bool = PIONEX_DIRECT_ALLOW_PAYLOAD_LEVERAGE

    def __post_init__(self):
        if self.allowed_symbols is None:
            raw = PIONEX_ALLOWED_SYMBOLS
            if isinstance(raw, list):
                symbols = tuple(s.strip() for s in raw if s.strip())
            else:
                symbols = tuple(s.strip() for s in str(raw).split(",") if s.strip())
            object.__setattr__(self, "allowed_symbols", symbols)


class PionexDirectBroker(BaseBroker):
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

    def get_broker_name(self) -> str:
        return "PionexDirectBroker"

    def get_broker_type(self) -> str:
        return "pionex_direct"

    def get_broker_mode(self) -> str:
        if self.is_live_capable():
            return "live"
        if self.config.enabled:
            return "dry-run"
        return "simulation"

    def _map_symbol(self, symbol: str) -> Optional[str]:
        mapping = {
            "XAGUSDT.P": "XAG_USDT_PERP",
            "BTCUSD": "BTC_USDT",
            "ETHUSD": "ETH_USDT",
        }
        mapped = mapping.get(symbol, symbol)
        if mapped in self.config.allowed_symbols:
            return mapped
        return None

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
    def _balance_value(item: dict[str, Any]) -> float:
        for key in ("free", "available", "balance", "total", "amount"):
            raw = item.get(key)
            if raw is None:
                continue
            try:
                return float(raw)
            except (TypeError, ValueError):
                continue
        return 0.0

    @staticmethod
    def _asset_value(item: dict[str, Any]) -> float | None:
        for key in ("value_usdt", "valueUsd", "usdValue", "usdtValue", "value", "equity"):
            raw = item.get(key)
            if raw is None:
                continue
            try:
                return float(raw)
            except (TypeError, ValueError):
                continue
        return None

    def _normalize_asset_balance(self, item: dict[str, Any]) -> dict[str, Any]:
        coin = str(item.get("coin") or item.get("asset") or item.get("currency") or "").upper()
        available = self._coerce_optional_float(item.get("available") or item.get("free"))
        locked = self._coerce_optional_float(item.get("locked") or item.get("frozen") or item.get("freeze"))
        explicit_balance = self._coerce_optional_float(item.get("balance") or item.get("total") or item.get("amount"))
        balance = explicit_balance if explicit_balance is not None else (available or 0.0) + (locked or 0.0)
        value_usdt = self._asset_value(item)
        if value_usdt is None and coin == "USDT":
            value_usdt = balance
        return {
            "coin": coin,
            "balance": balance,
            "available": available,
            "locked": locked,
            "value_usdt": value_usdt,
            "raw": item,
        }

    def _normalize_futures_position(self, item: dict[str, Any]) -> dict[str, Any]:
        symbol = str(item.get("symbol") or "").upper()
        side = str(item.get("positionSide") or item.get("side") or "").upper()
        initial_margin = self._coerce_optional_float(item.get("initialMargin"))
        maint_margin = self._coerce_optional_float(item.get("maintMargin"))
        unrealized_pnl = self._coerce_optional_float(item.get("unrealizedPnL") or item.get("unrealizedPnl"))
        net_size = self._coerce_optional_float(item.get("netSize"))
        size_long = self._coerce_optional_float(item.get("sizeLong"))
        size_short = self._coerce_optional_float(item.get("sizeShort"))
        return {
            "position_id": str(item.get("positionId") or ""),
            "symbol": symbol,
            "asset": symbol.split("_", 1)[0] if symbol else "",
            "is_zcash": symbol.startswith("ZEC_") or symbol.startswith("ZCASH_"),
            "account_mode": "FUTURES",
            "isolated_mode": item.get("isolatedMode"),
            "risk_state": item.get("riskState"),
            "position_side": side,
            "net_size": net_size,
            "avg_price": self._coerce_optional_float(item.get("avgPrice")),
            "mark_price": self._coerce_optional_float(item.get("markPrice")),
            "unrealized_pnl": unrealized_pnl,
            "initial_margin": initial_margin,
            "maint_margin": maint_margin,
            "liquidation_price": self._coerce_optional_float(item.get("liquidationPrice")),
            "leverage": self._coerce_optional_float(item.get("leverage")),
            "size_long": size_long,
            "size_short": size_short,
            "amount_long": self._coerce_optional_float(item.get("amountLong")),
            "amount_short": self._coerce_optional_float(item.get("amountShort")),
            "amount_settled": self._coerce_optional_float(item.get("amountSettled")),
            "updated_at": item.get("updateTime") or item.get("updatedTime"),
            "created_at": item.get("createTime") or item.get("createdTime"),
            "raw": item,
        }

    @staticmethod
    def _position_is_open(position: dict[str, Any]) -> bool:
        for key in ("net_size", "size_long", "size_short", "initial_margin", "amount_long", "amount_short"):
            value = position.get(key)
            if value is not None and abs(float(value)) > 0:
                return True
        return False

    def get_positions(self) -> dict[str, Any]:
        """BaseBroker interface — alias for get_open_positions."""
        return self.get_open_positions()

    def get_open_positions(self) -> dict[str, Any]:
        if not self.client:
            return {"account_mode": "FUTURES", "error": "PIONEX_CLIENT_NOT_CONFIGURED", "positions": []}
        try:
            raw_positions = self.client.get_futures_positions()
            positions = [
                position
                for position in (self._normalize_futures_position(item) for item in raw_positions)
                if self._position_is_open(position)
            ]
            return {
                "account_mode": "FUTURES",
                "open_count": len(positions),
                "positions": positions,
                "summary": {
                    "total_initial_margin": sum(position.get("initial_margin") or 0.0 for position in positions),
                    "total_maint_margin": sum(position.get("maint_margin") or 0.0 for position in positions),
                    "total_unrealized_pnl": sum(position.get("unrealized_pnl") or 0.0 for position in positions),
                    "zcash_open_count": sum(1 for position in positions if position.get("is_zcash")),
                    "zcash_initial_margin": sum(
                        position.get("initial_margin") or 0.0
                        for position in positions
                        if position.get("is_zcash")
                    ),
                    "zcash_unrealized_pnl": sum(
                        position.get("unrealized_pnl") or 0.0
                        for position in positions
                        if position.get("is_zcash")
                    ),
                },
            }
        except PionexAPIError as exc:
            return {
                "account_mode": "FUTURES",
                "error": exc.message,
                "retryable": exc.retryable,
                "positions": [],
            }

    def _normalize_bot_order(self, item: dict[str, Any]) -> dict[str, Any]:
        data = item.get("buOrderData") or {}
        base = str(item.get("base") or "").upper()
        quote = str(item.get("quote") or "").upper()
        symbol = f"{base}_{quote}" if base and quote else ""
        margin_balance = self._coerce_optional_float(data.get("marginBalance"))
        quote_investment = self._coerce_optional_float(data.get("quoteInvestment") or data.get("usdtInvestment"))
        extra_balance = self._coerce_optional_float(data.get("extraBalance"))
        return {
            "bot_order_id": str(item.get("buOrderId") or ""),
            "bot_type": item.get("buOrderType"),
            "bot_name": item.get("botName") or item.get("customizeName") or item.get("note") or "",
            "symbol": symbol,
            "base": base,
            "quote": quote,
            "status": item.get("status") or data.get("status"),
            "is_zcash": base in {"ZEC", "ZCASH"},
            "leverage": self._coerce_optional_float(data.get("leverage")),
            "trend": data.get("trend"),
            "grid_type": data.get("gridType"),
            "top": self._coerce_optional_float(data.get("top")),
            "bottom": self._coerce_optional_float(data.get("bottom")),
            "open_price": self._coerce_optional_float(data.get("openPrice")),
            "position": self._coerce_optional_float(data.get("position")),
            "position_open_price": self._coerce_optional_float(data.get("positionOpenPrice")),
            "margin_balance": margin_balance,
            "quote_investment": quote_investment,
            "extra_balance": extra_balance,
            "liquidation_price": self._coerce_optional_float(data.get("liquidationPrice")),
            "risk_status": data.get("riskStatus"),
            "margin_status": data.get("marginStatus"),
            "profit_withdrawn": self._coerce_optional_float(data.get("profitWithdrawn")),
            "created_at": item.get("createTime"),
            "raw": item,
        }

    def get_running_bots(self) -> dict[str, Any]:
        if not self.client:
            return {"status": "running", "error": "PIONEX_CLIENT_NOT_CONFIGURED", "bots": []}
        try:
            data = self.client.get_bot_orders(status="running")
            raw_orders = data.get("results", [])
            detailed_orders: list[dict[str, Any]] = []
            for order in raw_orders:
                if order.get("buOrderType") == "futures_grid" and order.get("buOrderId"):
                    try:
                        detailed_orders.append(self.client.get_futures_grid_order(str(order["buOrderId"])))
                    except PionexAPIError:
                        detailed_orders.append(order)
                else:
                    detailed_orders.append(order)

            bots = [self._normalize_bot_order(item) for item in detailed_orders]
            futures_grid = [bot for bot in bots if bot.get("bot_type") == "futures_grid"]
            zcash_bots = [bot for bot in bots if bot.get("is_zcash")]
            return {
                "status": "running",
                "open_count": len(bots),
                "bots": bots,
                "summary": {
                    "futures_grid_count": len(futures_grid),
                    "zcash_bot_count": len(zcash_bots),
                    "total_margin_balance": sum(bot.get("margin_balance") or 0.0 for bot in bots),
                    "total_quote_investment": sum(bot.get("quote_investment") or 0.0 for bot in bots),
                    "total_extra_balance": sum(bot.get("extra_balance") or 0.0 for bot in bots),
                    "zcash_margin_balance": sum(bot.get("margin_balance") or 0.0 for bot in zcash_bots),
                    "zcash_quote_investment": sum(bot.get("quote_investment") or 0.0 for bot in zcash_bots),
                    "zcash_extra_balance": sum(bot.get("extra_balance") or 0.0 for bot in zcash_bots),
                },
            }
        except PionexAPIError as exc:
            return {
                "status": "running",
                "error": exc.message,
                "retryable": exc.retryable,
                "bots": [],
            }

    @staticmethod
    def _coerce_optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def get_wallet_balances(self, account_mode: str = "SPOT") -> dict[str, Any]:
        if not self.client:
            return {"account_mode": account_mode.upper(), "error": "PIONEX_CLIENT_NOT_CONFIGURED", "assets": []}
        try:
            raw_balances = (
                self.client.get_spot_balances()
                if account_mode.upper() == "SPOT"
                else self.client.get_futures_balances()
            )
            assets = [self._normalize_asset_balance(item) for item in raw_balances]
            usdt_asset = next((asset for asset in assets if asset["coin"] == "USDT"), None)
            return {
                "coin": "USDT",
                "account_mode": account_mode.upper(),
                "balance": usdt_asset["balance"] if usdt_asset else 0.0,
                "asset_count": len(assets),
                "assets": assets,
            }
        except PionexAPIError as exc:
            return {
                "account_mode": account_mode.upper(),
                "error": exc.message,
                "retryable": exc.retryable,
                "assets": [],
            }

    @staticmethod
    def _is_perp_symbol(symbol: str) -> bool:
        value = (symbol or "").strip().upper()
        return value.endswith(".P") or value.endswith("_PERP")

    def _normalized_account_mode(self, payload: M8Payload) -> str:
        account_mode = payload.account_mode.upper()
        if account_mode == "SPOT" and self._is_perp_symbol(payload.symbol):
            return "FUTURES"
        return account_mode

    def _client_order_id(self, payload: M8Payload, symbol: str, account_mode: str, side: str) -> str:
        return f"{payload.signal_id}_{symbol}_{account_mode}_{side}_{payload.intent}"

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

        return reward / risk if risk > 0 else 0.0

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _build_entry(
        self,
        payload: M8Payload,
        ai_decision: AIDecisionEnum,
        final_decision: FinalDecisionEnum,
        simulated_fill: dict[str, Any],
        result: dict[str, Any],
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
            risk_reward=self._trade_rr(payload),
            m8_score=payload.confluence_score,
            ai_decision=DecisionEnum(ai_decision.value),
            final_decision=final_decision,
            simulated_fill=simulated_fill,
            result=result,
        )
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
                ai_decision=ai_decision,
                final_decision=FinalDecisionEnum.REJECTED,
                simulated_fill={},
                result={"status": "REJECTED", "reject_reason": reject_reason},
            )

        if not self.config.enabled:
            return self._build_entry(
                payload=payload,
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
        client_order_id = self._client_order_id(payload, symbol, account_mode, entry_side)
        trade_id = f"pionex-direct-{payload.signal_id}"

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
        stop_loss = payload.stop_price if payload.stop_price > 0 else None
        take_profit = payload.target_price if payload.target_price > 0 else None

        if account_mode == "SPOT":
            if payload.direction == "LONG":
                return self.client.place_spot_market_buy(
                    symbol=symbol,
                    amount_usdt=order_value_usdt,
                    client_order_id=client_order_id,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )
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
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def _close_position(self, payload: M8Payload, symbol: str, account_mode: str, ai_decision: AIDecisionEnum) -> TradeJournalEntry:
        trade_id = f"pionex-direct-{payload.signal_id}"
        position = self.ledger.get(symbol=symbol, account_mode=account_mode)
        if not position:
            reason = "NO_OPEN_POSITION"
            self.notifier.send_reject(symbol, reason, trade_id, payload.intent)
            return self._build_entry(
                payload=payload,
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
        client_order_id = self._client_order_id(payload, symbol, account_mode, close_side)
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

        # Record trade outcome in confidence registry (before potential rollback)
        if risk_amount and risk_amount > 0:
            rr_achieved = abs(realized_pnl / risk_amount)
            pnl_pct = (realized_pnl / risk_amount) * 100.0
        else:
            rr_achieved = 0.0
            pnl_pct = 0.0
        from app.services.confidence_registry import confidence_registry
        from app.services.portfolio_circuit_breaker import circuit_breaker_instance
        confidence_registry.record_trade_outcome(
            symbol=symbol,
            direction=direction,
            pnl_pct=pnl_pct,
            rr=rr_achieved,
            win=realized_pnl > 0,
        )
        circuit_breaker_instance.record_trade_pnl(realized_pnl)

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
                    client_order_id=client_order_id,
                    entry_price=entry_price,
                    risk_amount=risk_amount,
                )
                self.notifier.send_error("CLOSE", exc.message)
                return self._build_entry(
                    payload=payload,
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

    def _poll_fill_status(
        self,
        order_id: str,
        account_mode: str,
        expected_price: float,
        symbol: str,
        max_attempts: int = 5,
        delay_seconds: float = 2.0,
    ) -> dict[str, Any]:
        """
        Poll exchange for order fill status.
        Returns fill info or empty dict if not filled / error.
        """
        import time

        if not self.client or not order_id:
            return {}

        for attempt in range(max_attempts):
            try:
                if account_mode == "SPOT":
                    data = self.client.get_spot_order(order_id)
                else:
                    data = self.client.get_futures_order(order_id)

                status = str(data.get("status", "")).upper()
                if status in {"FILLED", "CLOSED", "COMPLETED"}:
                    fill_price = float(data.get("avgPrice", data.get("price", 0)) or 0)
                    if fill_price > 0 and expected_price > 0:
                        self.notifier.send_fill_alert(symbol, order_id, fill_price, expected_price)
                    return {
                        "filled": True,
                        "fill_price": fill_price,
                        "status": status,
                        "raw": data,
                    }
                if status in {"REJECTED", "CANCELED", "EXPIRED"}:
                    return {"filled": False, "status": status, "raw": data}
            except Exception as e:
                if attempt == max_attempts - 1:
                    return {"filled": False, "error": str(e)}

            time.sleep(delay_seconds)

        return {"filled": False, "status": "TIMEOUT"}

    def reconcile_ledger(self) -> dict[str, Any]:
        """
        Compare local PositionLedger with exchange positions.
        Returns divergences list and alert if found.
        """
        if not self.client:
            return {"checked": False, "reason": "no_client"}

        divergences: list[str] = []

        try:
            # Check futures positions
            futures_positions = self.client.get_futures_positions()
            exchange_futures: dict[str, float] = {}
            for pos in futures_positions:
                sym = str(pos.get("symbol", "")).upper()
                size = float(pos.get("size", 0) or pos.get("positionSize", 0) or 0)
                if sym and abs(size) > 0:
                    exchange_futures[sym] = size

            for key, local in self.ledger._positions.items():
                account_mode, symbol = key
                if account_mode != "FUTURES":
                    continue
                mapped_symbol = self._map_symbol(symbol) or symbol
                exchange_size = exchange_futures.get(mapped_symbol, 0.0)
                if abs(local.size_base - exchange_size) > 1e-8:
                    divergences.append(
                        f"FUTURES {mapped_symbol}: local={local.size_base:.6f} vs exchange={exchange_size:.6f}"
                    )

            # Check for exchange positions not in local ledger
            for sym, size in exchange_futures.items():
                key = ("FUTURES", sym)
                if key not in self.ledger._positions and abs(size) > 1e-8:
                    divergences.append(
                        f"FUTURES {sym}: local=NONE vs exchange={size:.6f}"
                    )

        except Exception as e:
            divergences.append(f"Reconciliation fetch error: {e}")

        if divergences:
            self.notifier.send_reconcile_alert(divergences)

        return {
            "checked": True,
            "divergences": divergences,
            "divergence_count": len(divergences),
        }
