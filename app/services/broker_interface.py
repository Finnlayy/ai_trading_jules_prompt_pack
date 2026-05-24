"""Base broker interface that all broker implementations must follow.

This enables clean single/multi-mode broker selection.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from app.schemas.ai_review import DecisionEnum as AIDecisionEnum
from app.schemas.journal import DecisionEnum, TradeJournalEntry
from app.schemas.m8_payload import M8Payload


class BaseBroker(ABC):
    """Abstract base class for all trading brokers.

    Implementations: SimulationBroker, PionexDirectBroker, GlintBroker, PaperBroker
    """

    @abstractmethod
    def execute_trade(
        self,
        payload: M8Payload,
        decision: DecisionEnum,
        reject_reason: Optional[str] = None,
        ai_decision: AIDecisionEnum = AIDecisionEnum.PROCEED_TO_SIMULATION,
    ) -> TradeJournalEntry:
        """Execute or simulate a trade based on the signal payload and decision."""

    @abstractmethod
    def get_positions(self) -> dict[str, Any]:
        """Return current open positions. Format is broker-specific."""

    @abstractmethod
    def get_wallet_balances(self, account_mode: str = "SPOT") -> dict[str, Any]:
        """Return wallet/balance information."""

    @abstractmethod
    def is_live_capable(self) -> bool:
        """Return True if this broker can execute real trades."""

    @abstractmethod
    def is_ready(self) -> bool:
        """Return True if broker is configured and ready to operate."""

    def get_broker_name(self) -> str:
        """Human-readable broker name."""
        return self.__class__.__name__

    def get_broker_type(self) -> str:
        """Short type identifier for UI/API."""
        return "unknown"

    def get_broker_mode(self) -> str:
        """Trading mode: simulation, paper, live, dry-run."""
        return "simulation"

    def reconcile_ledger(self) -> dict[str, Any]:
        """Optional: reconcile local ledger with exchange. Default no-op."""
        return {"checked": False, "reason": "not_supported"}

    def health(self) -> dict[str, Any]:
        """Return broker health status for monitoring."""
        return {
            "name": self.get_broker_name(),
            "type": self.get_broker_type(),
            "mode": self.get_broker_mode(),
            "ready": self.is_ready(),
            "live_capable": self.is_live_capable(),
        }
