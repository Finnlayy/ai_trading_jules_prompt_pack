from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

from app.core.config import (
    PIONEX_RELAY_CONTRACTS,
    PIONEX_RELAY_ENABLED,
    PIONEX_RELAY_TIMEOUT_SECONDS,
    PIONEX_RELAY_URL,
    PIONEX_SIGNAL_BOT_UUID,
)
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum
from app.schemas.journal import DecisionEnum, DirectionEnum, FinalDecisionEnum, TradeJournalEntry
from app.schemas.m8_payload import M8Payload


@dataclass(frozen=True)
class PionexRelayConfig:
    relay_url: str = PIONEX_RELAY_URL
    signal_bot_uuid: str = PIONEX_SIGNAL_BOT_UUID
    contracts: str = PIONEX_RELAY_CONTRACTS
    enabled: bool = PIONEX_RELAY_ENABLED
    timeout_seconds: float = PIONEX_RELAY_TIMEOUT_SECONDS


class PionexRelayBroker:
    """
    Broker adapter for the external Pionex relay server.

    Safety defaults:
    - Does not send HTTP requests unless PIONEX_RELAY_ENABLED=true.
    - Requires relay URL and Signal Bot UUID before live forwarding.
    - Only forwards signals after the deterministic risk engine returns PROCEED_TO_SIMULATION.
    """

    def __init__(self, config: Optional[PionexRelayConfig] = None) -> None:
        self.config = config or PionexRelayConfig()
        self.journal: list[TradeJournalEntry] = []

    def is_ready(self) -> bool:
        return bool(
            self.config.enabled
            and self.config.relay_url
            and self.config.signal_bot_uuid
        )

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
            relay_payload = self._build_relay_payload(payload)
            simulated_fill = {
                "fill_price": payload.entry_price,
                "fee": 0.0,
                "slippage": 0.0,
                "mode": "PIONEX_RELAY",
                "relay_enabled": self.config.enabled,
            }

            if not self.config.enabled:
                final_decision = FinalDecisionEnum.EXECUTED_SIM
                result = {
                    "status": "DRY_RUN_RELAY",
                    "reject_reason": None,
                    "relay_url": self.config.relay_url,
                    "relay_payload": relay_payload,
                }
            elif not self.is_ready():
                final_decision = FinalDecisionEnum.REJECTED
                result = {
                    "status": "CONFIG_ERROR",
                    "reject_reason": "PIONEX_RELAY_NOT_CONFIGURED",
                }
            else:
                final_decision, result = self._send_to_relay(relay_payload)

        entry = TradeJournalEntry(
            trade_id=f"pionex-relay-{payload.signal_id}",
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

    def _build_relay_payload(self, payload: M8Payload) -> Dict[str, Any]:
        action = "buy" if payload.direction == "LONG" else "sell"
        position_size = self.config.contracts if action == "buy" else f"-{self.config.contracts}"

        return {
            "data": {
                "action": action,
                "contracts": self.config.contracts,
                "position_size": position_size,
            },
            "price": str(payload.entry_price),
            "signal_param": "{}",
            "signal_type": self.config.signal_bot_uuid,
            "symbol": payload.symbol,
            "time": payload.timestamp,
        }

    def _send_to_relay(self, relay_payload: Dict[str, Any]) -> tuple[FinalDecisionEnum, Dict[str, Any]]:
        try:
            response = requests.post(
                self.config.relay_url,
                json=relay_payload,
                timeout=self.config.timeout_seconds,
            )
        except requests.RequestException as exc:
            return FinalDecisionEnum.REJECTED, {
                "status": "RELAY_ERROR",
                "reject_reason": str(exc),
            }

        if 200 <= response.status_code < 300:
            return FinalDecisionEnum.EXECUTED_SIM, {
                "status": "SENT_TO_PIONEX_RELAY",
                "reject_reason": None,
                "relay_status_code": response.status_code,
                "relay_response": self._safe_response_body(response),
            }

        return FinalDecisionEnum.REJECTED, {
            "status": "RELAY_REJECTED",
            "reject_reason": f"Relay returned HTTP {response.status_code}",
            "relay_status_code": response.status_code,
            "relay_response": self._safe_response_body(response),
        }

    @staticmethod
    def _safe_response_body(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text[:500]
