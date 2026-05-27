import pytest
import os
import json
from app.services.journal_logger import JournalLogger
from app.schemas.journal import TradeJournalEntry, DecisionEnum

@pytest.fixture
def tmp_journal(tmp_path):
    filepath = tmp_path / "test_journal.jsonl"
    logger = JournalLogger(str(filepath))
    return logger, str(filepath)

@pytest.mark.asyncio
async def test_journal_logger_async_write(tmp_journal):
    logger, filepath = tmp_journal
    entry = TradeJournalEntry(
        trade_id="test_id_123",
        timestamp="2024-01-01T00:00:00Z",
        symbol="BTCUSDT",
        timeframe="1h",
        direction="LONG",
        entry_price=50000.0,
        stop_price=49000.0,
        target_price=52000.0,
        risk_reward=2.0,
        m8_score=85.0,
        ai_decision=DecisionEnum.PROCEED_TO_SIMULATION,
        decision=DecisionEnum.PROCEED_TO_SIMULATION,
        simulated_fill={},
        final_decision="EXECUTED_SIM",
        reject_reason=None,
        result={"test": "data"}
    )

    await logger.log(entry)

    assert os.path.exists(filepath)
    with open(filepath, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["trade_id"] == "test_id_123"
        assert data["symbol"] == "BTCUSDT"
        assert data["result"] == {"test": "data"}

@pytest.mark.asyncio
async def test_journal_logger_sync_write_helper(tmp_journal):
    logger, filepath = tmp_journal
    entry = TradeJournalEntry(
        trade_id="test_id_456",
        timestamp="2024-01-01T00:00:00Z",
        symbol="ETHUSDT",
        timeframe="1h",
        direction="SHORT",
        entry_price=3000.0,
        stop_price=3100.0,
        target_price=2700.0,
        risk_reward=3.0,
        m8_score=90.0,
        ai_decision=DecisionEnum.PROCEED_TO_SIMULATION,
        decision=DecisionEnum.PROCEED_TO_SIMULATION,
        simulated_fill={},
        final_decision="EXECUTED_SIM",
        reject_reason=None,
        result={}
    )

    # Should be able to call the helper synchronously if needed by other sync code
    logger._write_entry(entry)

    assert os.path.exists(filepath)
    with open(filepath, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["trade_id"] == "test_id_456"
        assert data["symbol"] == "ETHUSDT"
