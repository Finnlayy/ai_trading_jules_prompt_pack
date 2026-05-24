import json
import os
import pytest
from app.services.journal_logger import JournalLogger
from app.schemas.journal import TradeJournalEntry, DirectionEnum, DecisionEnum, FinalDecisionEnum


@pytest.fixture
def logger(tmp_path):
    return JournalLogger(
        filepath=str(tmp_path / "journal.jsonl"),
        max_size_bytes=500,  # very small for testing
        max_backups=3,
    )


def _make_entry(trade_id: str) -> TradeJournalEntry:
    return TradeJournalEntry(
        trade_id=trade_id,
        timestamp="2026-05-20T10:00:00Z",
        symbol="BTCUSDT",
        timeframe="1h",
        direction=DirectionEnum.LONG,
        entry_price=50000.0,
        stop_price=48000.0,
        target_price=54000.0,
        risk_reward=2.0,
        m8_score=85.0,
        ai_decision=DecisionEnum.PROCEED_TO_SIMULATION,
        final_decision=FinalDecisionEnum.EXECUTED_SIM,
        simulated_fill={},
    )


def test_log_appends_entry(logger):
    entry = _make_entry("t1")
    logger.log(entry)
    assert os.path.exists(logger.filepath)
    with open(logger.filepath) as f:
        lines = f.readlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["trade_id"] == "t1"


def test_rotation_on_size(logger):
    # Write enough entries to exceed 500 bytes
    for i in range(20):
        logger.log(_make_entry(f"t-{i}"))

    # Current file should exist and rotated files may exist
    assert os.path.exists(logger.filepath)
    archives = [f"{logger.filepath}.{i}" for i in range(1, 4)]
    assert any(os.path.exists(a) for a in archives)


def test_get_entries_returns_last_n(logger):
    for i in range(5):
        logger.log(_make_entry(f"t-{i}"))
    entries = logger.get_entries(limit=3)
    assert len(entries) == 3
    assert entries[-1]["trade_id"] == "t-4"
