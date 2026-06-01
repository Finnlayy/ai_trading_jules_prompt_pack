from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.services.live_fill_tracker import (
    LiveFillTracker,
    FillData,
    PositionIntent,
    OpenPosition,
    _normalize_symbol,
    live_fill_tracker
)


@pytest.fixture(autouse=True)
def mock_db_and_registry(monkeypatch, tmp_path):
    """Mock external dependencies and setup isolated state."""
    # Mock DB Session
    mock_session = MagicMock()
    mock_session_local = MagicMock(return_value=mock_session)
    monkeypatch.setattr("app.db.SessionLocal", mock_session_local)

    # Mock Confidence Registry
    mock_registry = MagicMock()
    monkeypatch.setattr("app.services.confidence_registry.confidence_registry", mock_registry)

    # Mock Models (just in case they are used in queries)
    mock_db_position = MagicMock()
    monkeypatch.setattr("app.db.models.Position", mock_db_position)

    # Override persist path
    live_fill_tracker._persist_path = tmp_path / "test_positions.json"

    # Reset singleton state before and after test
    live_fill_tracker.reset()
    yield
    live_fill_tracker.reset()


def test_normalize_symbol():
    assert _normalize_symbol("BTCUSD") == "BTCUSDT"
    assert _normalize_symbol("btcUsd   ") == "BTCUSDT"
    assert _normalize_symbol("SOLUSDT") == "SOLUSDT"
    assert _normalize_symbol("XRPUSD") == "XRPUSDT"


def test_record_intent_and_fill():
    trade_id = "test_trade_1"

    # 1. Record Intent
    live_fill_tracker.record_intent(
        trade_id=trade_id,
        symbol="BTCUSD",
        direction="LONG",
        entry_price=50000.0,
        stop_price=49000.0,
        target_price=52000.0,
        decision="PROCEED_TO_SIMULATION",
        size=1.0
    )

    assert trade_id in live_fill_tracker._intents
    intent = live_fill_tracker._intents[trade_id]
    assert intent.symbol == "BTCUSDT"

    # 2. Record Fill
    fill_data = FillData(
        entry_price=50010.0,
        fill_time=datetime.now(timezone.utc),
        size=1.0,
        side="BUY",
        fees=1.5,
        slippage=10.0
    )

    live_fill_tracker.record_fill(trade_id, fill_data)

    assert trade_id in live_fill_tracker._positions
    pos = live_fill_tracker.get_position(trade_id)
    assert pos is not None
    assert pos.symbol == "BTCUSDT"
    assert pos.entry_price == 50010.0
    assert pos.current_price == 50010.0
    assert pos.unrealized_pnl == 0.0
    assert len(live_fill_tracker.get_open_positions()) == 1


def test_update_price():
    trade_id = "test_trade_2"

    live_fill_tracker.record_intent(
        trade_id=trade_id,
        symbol="ETHUSDT",
        direction="LONG",
        entry_price=3000.0,
        stop_price=2900.0,
        target_price=3200.0,
        decision="PROCEED",
        size=2.0
    )

    live_fill_tracker.record_fill(trade_id, FillData(
        entry_price=3000.0,
        fill_time=datetime.now(timezone.utc),
        size=2.0,
        side="BUY",
        fees=0.0,
        slippage=0.0
    ))

    # Update price upwards
    live_fill_tracker.update_price(trade_id, 3100.0)
    pos = live_fill_tracker.get_position(trade_id)
    assert pos.current_price == 3100.0
    assert pos.unrealized_pnl == 200.0  # (3100 - 3000) * 2

    # Test short position
    trade_id_short = "test_trade_short"
    live_fill_tracker.record_intent(
        trade_id=trade_id_short,
        symbol="SOLUSDT",
        direction="SHORT",
        entry_price=100.0,
        stop_price=110.0,
        target_price=90.0,
        decision="PROCEED",
        size=10.0
    )
    live_fill_tracker.record_fill(trade_id_short, FillData(
        entry_price=100.0,
        fill_time=datetime.now(timezone.utc),
        size=10.0,
        side="SELL",
        fees=0.0,
        slippage=0.0
    ))

    live_fill_tracker.update_price(trade_id_short, 95.0)
    pos_short = live_fill_tracker.get_position(trade_id_short)
    assert pos_short.unrealized_pnl == 50.0  # (100 - 95) * 10


def test_record_exit():
    trade_id = "test_trade_3"

    live_fill_tracker.record_intent(
        trade_id=trade_id,
        symbol="ADAUSDT",
        direction="LONG",
        entry_price=1.0,
        stop_price=0.9,
        target_price=1.2,
        decision="PROCEED",
        size=1000.0
    )

    live_fill_tracker.record_fill(trade_id, FillData(
        entry_price=1.0,
        fill_time=datetime.now(timezone.utc),
        size=1000.0,
        side="BUY",
        fees=0.0,
        slippage=0.0
    ))

    # Exit with profit
    live_fill_tracker.record_exit(trade_id, exit_price=1.1)

    # Position should be removed
    assert live_fill_tracker.get_position(trade_id) is None

    # Check history
    assert len(live_fill_tracker._history) == 2  # 1 fill, 1 exit
    exit_event = live_fill_tracker._history[-1]
    assert exit_event["event"] == "exit"
    assert pytest.approx(exit_event["realized_pnl"]) == 100.0  # (1.1 - 1.0) * 1000


def test_get_daily_pnl():
    trade_id1 = "test_trade_pnl_1"
    trade_id2 = "test_trade_pnl_2"

    # Setup two positions and close them
    for tid in (trade_id1, trade_id2):
        live_fill_tracker.record_intent(tid, "BTC", "LONG", 100, 90, 110, "PROC", 1)
        live_fill_tracker.record_fill(tid, FillData(100, datetime.now(timezone.utc), 1, "BUY", 0, 0))

    # Win 10, Lose 5
    live_fill_tracker.record_exit(trade_id1, exit_price=110.0)
    live_fill_tracker.record_exit(trade_id2, exit_price=95.0)

    daily_pnl = live_fill_tracker.get_daily_pnl()
    assert daily_pnl == 5.0


def test_sync_with_broker():
    # Setup local positions
    live_fill_tracker.record_intent("loc1", "BTC", "LONG", 100, 90, 110, "PROC", 1)
    live_fill_tracker.record_fill("loc1", FillData(100, datetime.now(timezone.utc), 1, "BUY", 0, 0))

    live_fill_tracker.record_intent("loc2", "ETH", "LONG", 100, 90, 110, "PROC", 1)
    live_fill_tracker.record_fill("loc2", FillData(100, datetime.now(timezone.utc), 1, "BUY", 0, 0))

    # Broker positions: missing loc2, has extra_broker
    broker_positions = [
        {"trade_id": "loc1", "symbol": "BTCUSDT"},
        {"trade_id": "extra_broker", "symbol": "SOLUSDT"}
    ]

    result = live_fill_tracker.sync_with_broker(broker_positions)

    assert result["divergence"] is True
    assert "loc2" in result["missing_in_broker"]
    assert "extra_broker" in result["missing_in_local"]
    assert result["matched"] == 1
