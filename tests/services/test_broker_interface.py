import pytest
import uuid
from typing import Any, Optional

from app.services.broker_interface import BaseBroker
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum
from app.schemas.journal import DecisionEnum, TradeJournalEntry, FinalDecisionEnum, DirectionEnum
from app.schemas.m8_payload import M8Payload

def test_base_broker_cannot_be_instantiated():
    """Verify that the abstract base class cannot be instantiated directly."""
    with pytest.raises(TypeError) as exc_info:
        BaseBroker()
    assert "Can't instantiate abstract class BaseBroker" in str(exc_info.value)

class DummyBroker(BaseBroker):
    """A minimal implementation of BaseBroker for testing concrete methods."""

    def execute_trade(
        self,
        payload: M8Payload,
        decision: DecisionEnum,
        reject_reason: Optional[str] = None,
        ai_decision: AIDecisionEnum = AIDecisionEnum.PROCEED_TO_SIMULATION,
    ) -> TradeJournalEntry:
        return TradeJournalEntry(
            trade_id=str(uuid.uuid4()),
            timestamp=payload.timestamp,
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            direction=DirectionEnum(payload.direction),
            entry_price=payload.entry_price,
            stop_price=payload.stop_price,
            target_price=payload.target_price,
            risk_reward=2.0, # dummy value
            m8_score=payload.confluence_score,
            ai_decision=ai_decision,
            final_decision=FinalDecisionEnum.EXECUTED_SIM,
            simulated_fill={"fill_price": payload.entry_price, "fee": 0.0},
            result={"status": "DUMMY_EXECUTED"}
        )

    def get_positions(self) -> dict[str, Any]:
        return {"dummy_pos": True}

    def get_wallet_balances(self, account_mode: str = "SPOT") -> dict[str, Any]:
        return {"USDT": 1000.0}

    def is_live_capable(self) -> bool:
        return False

    def is_ready(self) -> bool:
        return True

@pytest.fixture
def dummy_broker() -> DummyBroker:
    return DummyBroker()

def test_get_broker_name(dummy_broker):
    """Test the default get_broker_name implementation."""
    assert dummy_broker.get_broker_name() == "DummyBroker"

def test_get_broker_type(dummy_broker):
    """Test the default get_broker_type implementation."""
    assert dummy_broker.get_broker_type() == "unknown"

def test_get_broker_mode(dummy_broker):
    """Test the default get_broker_mode implementation."""
    assert dummy_broker.get_broker_mode() == "simulation"

def test_reconcile_ledger(dummy_broker):
    """Test the default reconcile_ledger implementation."""
    result = dummy_broker.reconcile_ledger()
    assert result == {"checked": False, "reason": "not_supported"}

def test_health(dummy_broker):
    """Test the default health implementation."""
    health_data = dummy_broker.health()
    assert health_data == {
        "name": "DummyBroker",
        "type": "unknown",
        "mode": "simulation",
        "ready": True,
        "live_capable": False,
    }

def test_execute_trade_typing(dummy_broker):
    """Verify that execute_trade signature passes static typing tests implicitly."""
    payload = M8Payload(
        signal_id="dummy-sig-01",
        symbol="BTCUSD",
        timeframe="1h",
        direction="LONG",
        timestamp="2024-01-01T00:00:00Z",
        entry_price=50000.0,
        stop_price=48000.0,
        target_price=54000.0,
        confluence_score=90.0,
        crisis_score=5.0,
        mc_dispersion=1.5,
        spread=2.0
    )

    entry = dummy_broker.execute_trade(payload, DecisionEnum.PROCEED_TO_SIMULATION)

    assert isinstance(entry, TradeJournalEntry)
    assert entry.symbol == "BTCUSD"
    assert entry.result["status"] == "DUMMY_EXECUTED"
