"""Tests for Live Fill Tracker."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from app.services.live_fill_tracker import (
    LiveFillTracker,
    FillData,
    OpenPosition,
    PositionIntent,
    _normalize_symbol,
)

@pytest.fixture(autouse=True)
def mock_db_and_registry(monkeypatch):
    """Mock database and confidence registry calls to avoid external dependencies during tests."""
    mock_session_local = MagicMock()
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    mock_position = MagicMock()

    monkeypatch.setattr("app.services.live_fill_tracker.SessionLocal", mock_session_local, raising=False)
    monkeypatch.setattr("app.services.live_fill_tracker.Position", mock_position, raising=False)

    # Mock confidence registry
    mock_registry = MagicMock()
    monkeypatch.setattr("app.services.live_fill_tracker.confidence_registry", mock_registry, raising=False)

    # Mock the internal try/except imports dynamically since they occur inline
    import sys

    # Mock app.db and app.db.models
    mock_app_db = MagicMock()
    mock_app_db.SessionLocal = mock_session_local
    sys.modules["app.db"] = mock_app_db

    mock_app_db_models = MagicMock()
    mock_app_db_models.Position = mock_position
    sys.modules["app.db.models"] = mock_app_db_models

    mock_app_services_confidence_registry = MagicMock()
    mock_app_services_confidence_registry.confidence_registry = mock_registry
    sys.modules["app.services.confidence_registry"] = mock_app_services_confidence_registry

    return {
        "db": mock_db,
        "registry": mock_registry,
        "position_model": mock_position
    }

@pytest.fixture
def tracker():
    tracker = LiveFillTracker()
    tracker.reset()
    return tracker


def test_normalize_symbol():
    """Test symbol normalization for Bybit linear tickers."""
    assert _normalize_symbol("BTCUSD") == "BTCUSDT"
    assert _normalize_symbol("ETHUSD") == "ETHUSDT"
    assert _normalize_symbol("BTCUSDT") == "BTCUSDT"
    assert _normalize_symbol("BTCUSDC") == "BTCUSDC"
    assert _normalize_symbol("SOLUSD") == "SOLUSDT"
    assert _normalize_symbol(" DOGEUSD ") == "DOGEUSDT"
    assert _normalize_symbol("UNKNOWN") == "UNKNOWN"
    assert _normalize_symbol("UNKNOWNUSD") == "UNKNOWNUSDT"

def test_time_in_trade_minutes():
    """Test time in trade calculation."""
    now = datetime.now(timezone.utc)
    ten_mins_ago = now - timedelta(minutes=10)
    pos = OpenPosition(
        trade_id="t1",
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=50000.0,
        current_price=50100.0,
        size=1.0,
        unrealized_pnl=100.0,
        realized_pnl=0.0,
        open_time=ten_mins_ago,
        strategy_id="s1",
        stop_price=49000.0,
        target_price=52000.0
    )
    mins = pos.time_in_trade_minutes
    assert 9.9 < mins < 10.1

def test_singleton_instance():
    """Test LiveFillTracker is a singleton."""
    t1 = LiveFillTracker()
    t2 = LiveFillTracker()
    assert t1 is t2

def test_record_intent(tracker):
    """Test recording an intent stores it properly."""
    tracker.record_intent(
        trade_id="t1",
        symbol="BTCUSD",
        direction="LONG",
        entry_price=50000.0,
        stop_price=49000.0,
        target_price=52000.0,
        decision="PROCEED",
        strategy_id="s1",
        size=0.5,
        ai_trace={"scouts": {"test": "APPROVE"}}
    )

    assert "t1" in tracker._intents
    intent = tracker._intents["t1"]
    assert intent.symbol == "BTCUSDT"
    assert intent.direction == "LONG"
    assert intent.entry_price == 50000.0
    assert intent.size == 0.5
    assert intent.ai_trace == {"scouts": {"test": "APPROVE"}}

def test_record_fill(tracker, mock_db_and_registry):
    """Test recording a fill creates a position and logs to history."""
    tracker.record_intent(
        trade_id="t2",
        symbol="ETHUSD",
        direction="SHORT",
        entry_price=3000.0,
        stop_price=3100.0,
        target_price=2800.0,
        decision="PROCEED",
        strategy_id="s2",
    )

    fill_time = datetime.now(timezone.utc)
    fill = FillData(
        entry_price=3005.0,
        fill_time=fill_time,
        size=2.0,
        side="SELL",
        fees=5.0,
        slippage=5.0
    )

    tracker.record_fill("t2", fill)

    # Check position created
    pos = tracker.get_position("t2")
    assert pos is not None
    assert pos.symbol == "ETHUSDT"
    assert pos.direction == "SHORT"
    assert pos.entry_price == 3005.0
    assert pos.current_price == 3005.0
    assert pos.size == 2.0
    assert pos.unrealized_pnl == 0.0

    # Check history
    assert len(tracker._history) == 1
    assert tracker._history[0]["event"] == "fill"
    assert tracker._history[0]["trade_id"] == "t2"

    # Check DB was accessed
    mock_db = mock_db_and_registry["db"]
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()

def test_record_exit_long(tracker, mock_db_and_registry):
    """Test record exit for LONG positions."""
    tracker.record_intent(
        trade_id="t3", symbol="BTCUSDT", direction="LONG",
        entry_price=40000.0, stop_price=39000.0, target_price=42000.0,
        decision="PROCEED", strategy_id="s3", size=1.0
    )
    tracker.record_fill("t3", FillData(
        entry_price=40000.0, fill_time=datetime.now(timezone.utc),
        size=1.0, side="BUY", fees=0.0, slippage=0.0
    ))

    # Exit with profit
    exit_time = datetime.now(timezone.utc)
    tracker.record_exit("t3", 41000.0, exit_time)

    assert tracker.get_position("t3") is None
    # Check history to find realized pnl
    history = tracker._history
    exit_event = next(h for h in history if h["event"] == "exit" and h["trade_id"] == "t3")
    assert exit_event["realized_pnl"] == 1000.0
    assert exit_event["exit_price"] == 41000.0

def test_record_exit_short(tracker, mock_db_and_registry):
    """Test record exit for SHORT positions."""
    tracker.record_intent(
        trade_id="t4", symbol="BTCUSDT", direction="SHORT",
        entry_price=40000.0, stop_price=41000.0, target_price=38000.0,
        decision="PROCEED", strategy_id="s4", size=0.5
    )
    tracker.record_fill("t4", FillData(
        entry_price=40000.0, fill_time=datetime.now(timezone.utc),
        size=0.5, side="SELL", fees=0.0, slippage=0.0
    ))

    # Exit with loss
    exit_time = datetime.now(timezone.utc)
    tracker.record_exit("t4", 41000.0, exit_time)

    assert tracker.get_position("t4") is None
    # Check history to find realized pnl
    history = tracker._history
    exit_event = next(h for h in history if h["event"] == "exit" and h["trade_id"] == "t4")
    assert exit_event["realized_pnl"] == -500.0
    assert exit_event["exit_price"] == 41000.0

def test_update_price(tracker):
    """Test unrealized PnL updates properly."""
    # LONG
    tracker.record_intent(
        trade_id="t5", symbol="BTCUSDT", direction="LONG",
        entry_price=10000.0, stop_price=9000.0, target_price=12000.0,
        decision="PROCEED", size=2.0
    )
    tracker.record_fill("t5", FillData(
        entry_price=10000.0, fill_time=datetime.now(timezone.utc),
        size=2.0, side="BUY", fees=0.0, slippage=0.0
    ))

    tracker.update_price("t5", 10500.0)
    pos1 = tracker.get_position("t5")
    assert pos1.unrealized_pnl == 1000.0
    assert pos1.current_price == 10500.0

    # SHORT
    tracker.record_intent(
        trade_id="t6", symbol="ETHUSDT", direction="SHORT",
        entry_price=2000.0, stop_price=2100.0, target_price=1800.0,
        decision="PROCEED", size=10.0
    )
    tracker.record_fill("t6", FillData(
        entry_price=2000.0, fill_time=datetime.now(timezone.utc),
        size=10.0, side="SELL", fees=0.0, slippage=0.0
    ))

    tracker.update_price("t6", 1900.0)
    pos2 = tracker.get_position("t6")
    assert pos2.unrealized_pnl == 1000.0
    assert pos2.current_price == 1900.0

    tracker.update_price("t6", 2100.0)
    pos3 = tracker.get_position("t6")
    assert pos3.unrealized_pnl == -1000.0

def test_sync_with_broker(tracker):
    """Test divergence detection logic."""
    # Add local position
    tracker.record_intent(
        trade_id="local_t1", symbol="BTCUSDT", direction="LONG",
        entry_price=100.0, stop_price=90.0, target_price=110.0,
        decision="PROCEED", size=1.0
    )
    tracker.record_fill("local_t1", FillData(
        entry_price=100.0, fill_time=datetime.now(timezone.utc),
        size=1.0, side="BUY", fees=0.0, slippage=0.0
    ))

    broker_positions = [
        {"trade_id": "local_t1"},
        {"trade_id": "broker_t2"}
    ]

    divergence_info = tracker.sync_with_broker(broker_positions)

    assert divergence_info["divergence"] is True
    assert "broker_t2" in divergence_info["missing_in_local"]
    assert len(divergence_info["missing_in_broker"]) == 0
    assert divergence_info["matched"] == 1

def test_get_daily_pnl(tracker, mock_db_and_registry):
    """Test daily PnL calculation sums properly."""
    tracker.record_intent(
        trade_id="t7", symbol="BTCUSDT", direction="LONG",
        entry_price=1000.0, stop_price=900.0, target_price=1100.0,
        decision="PROCEED", size=1.0
    )
    tracker.record_fill("t7", FillData(
        entry_price=1000.0, fill_time=datetime.now(timezone.utc),
        size=1.0, side="BUY", fees=0.0, slippage=0.0
    ))

    tracker.record_intent(
        trade_id="t8", symbol="ETHUSDT", direction="SHORT",
        entry_price=2000.0, stop_price=2100.0, target_price=1900.0,
        decision="PROCEED", size=1.0
    )
    tracker.record_fill("t8", FillData(
        entry_price=2000.0, fill_time=datetime.now(timezone.utc),
        size=1.0, side="SELL", fees=0.0, slippage=0.0
    ))

    tracker.record_exit("t7", 1100.0) # PnL: +100
    tracker.record_exit("t8", 1950.0) # PnL: +50

    daily_pnl = tracker.get_daily_pnl()
    assert daily_pnl == 150.0

def test_get_open_positions(tracker):
    """Test that all open positions are returned properly."""
    tracker.record_intent(
        trade_id="t9", symbol="SOLUSDT", direction="LONG",
        entry_price=100.0, stop_price=90.0, target_price=110.0,
        decision="PROCEED", size=1.0
    )
    tracker.record_fill("t9", FillData(
        entry_price=100.0, fill_time=datetime.now(timezone.utc),
        size=1.0, side="BUY", fees=0.0, slippage=0.0
    ))

    open_pos = tracker.get_open_positions()
    assert len(open_pos) == 1
    assert open_pos[0].trade_id == "t9"
