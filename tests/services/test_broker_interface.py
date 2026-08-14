import pytest
from typing import Any, Optional

from app.schemas.ai_review import DecisionEnum as AIDecisionEnum
from app.schemas.journal import DecisionEnum, TradeJournalEntry
from app.schemas.m8_payload import M8Payload
from app.services.broker_interface import BaseBroker


def test_base_broker_cannot_be_instantiated():
    """Ensure that BaseBroker cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseBroker()


class DummyBroker(BaseBroker):
    """A dummy implementation of BaseBroker for testing concrete methods."""

    def execute_trade(
        self,
        payload: M8Payload,
        decision: DecisionEnum,
        reject_reason: Optional[str] = None,
        ai_decision: AIDecisionEnum = AIDecisionEnum.PROCEED_TO_SIMULATION,
    ) -> TradeJournalEntry:
        return TradeJournalEntry(
            signal_id=payload.id,
            symbol=payload.symbol,
            decision=decision,
            ai_decision=ai_decision,
            reject_reason=reject_reason,
            position_size=0.0,
            entry_price=0.0,
            account_mode="SPOT"
        )

    def get_positions(self) -> dict[str, Any]:
        return {"positions": []}

    def get_wallet_balances(self, account_mode: str = "SPOT") -> dict[str, Any]:
        return {"balances": []}

    def is_live_capable(self) -> bool:
        return False

    def is_ready(self) -> bool:
        return True


def test_dummy_broker_can_be_instantiated():
    """Ensure that a fully implemented subclass can be instantiated."""
    broker = DummyBroker()
    assert isinstance(broker, BaseBroker)


def test_get_broker_name():
    broker = DummyBroker()
    assert broker.get_broker_name() == "DummyBroker"


def test_get_broker_type():
    broker = DummyBroker()
    assert broker.get_broker_type() == "unknown"


def test_get_broker_mode():
    broker = DummyBroker()
    assert broker.get_broker_mode() == "simulation"


def test_reconcile_ledger():
    broker = DummyBroker()
    assert broker.reconcile_ledger() == {"checked": False, "reason": "not_supported"}


def test_health():
    broker = DummyBroker()
    health_status = broker.health()
    assert health_status == {
        "name": "DummyBroker",
        "type": "unknown",
        "mode": "simulation",
        "ready": True,
        "live_capable": False,
    }
