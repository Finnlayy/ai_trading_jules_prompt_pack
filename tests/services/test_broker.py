import pytest
from app.services.broker import SimulationBroker
from app.schemas.m8_payload import M8Payload
from app.schemas.journal import DecisionEnum, FinalDecisionEnum

def create_valid_payload() -> M8Payload:
    return M8Payload(
        signal_id="sig-001",
        symbol="BTCUSD",
        timeframe="1h",
        direction="LONG",
        timestamp="2026-05-20T10:00:00Z",
        entry_price=50000.0,
        stop_price=48000.0,
        target_price=54000.0,
        confluence_score=85.0,
        crisis_score=10.0,
        mc_dispersion=2.0,
        spread=5.0
    )

def test_broker_execution_proceeds():
    broker = SimulationBroker(fee_bps=5.0, slippage_bps=2.0)
    payload = create_valid_payload()
    entry = broker.execute_trade(payload, DecisionEnum.PROCEED_TO_SIMULATION)

    assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert entry.result["status"] == "OPEN"
    
    # Check slippage simulation (2 bps on LONG increases price)
    expected_fill_price = 50000.0 * (1 + 2.0 / 10000.0)
    assert entry.simulated_fill["fill_price"] == expected_fill_price
    
    # Check fees
    expected_fee = expected_fill_price * (5.0 / 10000.0)
    assert entry.simulated_fill["fee"] == expected_fee

    assert len(broker.journal) == 1

def test_broker_execution_rejected():
    broker = SimulationBroker()
    payload = create_valid_payload()
    entry = broker.execute_trade(payload, DecisionEnum.REJECT, reject_reason="LOW_RR")

    assert entry.final_decision == FinalDecisionEnum.REJECTED
    assert entry.result["status"] == "REJECTED"
    assert entry.result["reject_reason"] == "LOW_RR"
    assert entry.simulated_fill == {}
    assert len(broker.journal) == 1
