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
)
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum
from app.schemas.journal import DecisionEnum, DirectionEnum, FinalDecisionEnum, TradeJournalEntry
from app.schemas.m8_payload import M8Payload


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
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            direction=DirectionEnum(payload.direction),
            entry_price=payload.entry_price,
            stop_price=payload.stop_price,
            target_price=payload.target_price,
            risk_reward=rr_ratio,
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
