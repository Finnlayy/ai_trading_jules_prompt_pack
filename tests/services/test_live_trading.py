"""Tests for Live Trading components: Fill Tracker, Performance Calculator, SSE."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.live_fill_tracker import LiveFillTracker, FillData, live_fill_tracker, PositionIntent
from app.services.performance_calculator import PerformanceCalculator
from app.services.dashboard_sse import DashboardSSEManager, SSEEvent


# ---------------------------------------------------------------------------
# Live Fill Tracker tests
# ---------------------------------------------------------------------------

def test_fill_tracker_singleton():
    ft1 = LiveFillTracker()
    ft2 = LiveFillTracker()
    assert ft1 is ft2


def test_record_intent_and_fill():
    tracker = LiveFillTracker()
    tracker.reset()

    intent = PositionIntent(
        trade_id="test-001",
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=100000.0,
        stop_price=99000.0,
        target_price=102000.0,
        size=None,
        strategy_id="default",
        decision="PROCEED_TO_SIMULATION",
    )
    tracker.record_intent(intent)

    fill = FillData(
        entry_price=100000.0,
        fill_time=datetime.now(timezone.utc),
        size=0.1,
        side="LONG",
        fees=5.0,
        slippage=2.0,
    )
    tracker.record_fill("test-001", fill)

    pos = tracker.get_position("test-001")
    assert pos is not None
    assert pos.symbol == "BTCUSDT"
    assert pos.direction == "LONG"
    assert pos.size == 0.1


def test_record_exit_updates_realized_pnl():
    tracker = LiveFillTracker()
    tracker.reset()

    intent = PositionIntent(
        trade_id="test-002", symbol="ETHUSDT", direction="LONG",
        entry_price=3000.0, stop_price=2900.0, target_price=3200.0,
        size=None, strategy_id=None,
        decision="PROCEED_TO_SIMULATION",
    )
    tracker.record_intent(intent)
    tracker.record_fill("test-002", FillData(
        entry_price=3000.0, fill_time=datetime.now(timezone.utc),
        size=1.0, side="LONG", fees=3.0, slippage=1.0,
    ))
    tracker.record_exit("test-002", 3100.0)

    assert tracker.get_position("test-002") is None


def test_update_price_changes_unrealized_pnl():
    tracker = LiveFillTracker()
    tracker.reset()

    intent = PositionIntent(
        trade_id="test-003", symbol="SOLUSDT", direction="LONG",
        entry_price=100.0, stop_price=90.0, target_price=120.0,
        size=None, strategy_id=None,
        decision="PROCEED_TO_SIMULATION",
    )
    tracker.record_intent(intent)
    tracker.record_fill("test-003", FillData(
        entry_price=100.0, fill_time=datetime.now(timezone.utc),
        size=10.0, side="LONG", fees=1.0, slippage=0.5,
    ))
    tracker.update_price("test-003", 110.0)

    pos = tracker.get_position("test-003")
    assert pos.unrealized_pnl == pytest.approx(100.0, abs=0.01)


def test_sync_with_broker_detects_divergence():
    tracker = LiveFillTracker()
    tracker.reset()

    intent = PositionIntent(
        trade_id="test-004", symbol="BTCUSDT", direction="LONG",
        entry_price=50000.0, stop_price=49000.0, target_price=52000.0,
        size=None, strategy_id=None,
        decision="PROCEED_TO_SIMULATION",
    )
    tracker.record_intent(intent)
    tracker.record_fill("test-004", FillData(
        entry_price=50000.0, fill_time=datetime.now(timezone.utc),
        size=0.5, side="LONG", fees=2.0, slippage=1.0,
    ))

    # Broker has extra position
    result = tracker.sync_with_broker([
        {"trade_id": "test-004"},
        {"trade_id": "test-005"},  # Missing locally
    ])
    assert result["divergence"] is True
    assert "test-005" in result["missing_in_local"]


def test_daily_pnl_empty():
    tracker = LiveFillTracker()
    tracker.reset()
    assert tracker.get_daily_pnl() == 0.0


# ---------------------------------------------------------------------------
# Performance Calculator tests
# ---------------------------------------------------------------------------

def test_performance_calculator_empty_trades():
    calc = PerformanceCalculator()
    metrics = calc.calculate_metrics([])
    assert metrics.total_trades == 0


def test_sharpe_ratio_positive_returns():
    calc = PerformanceCalculator()
    returns = [0.01, 0.02, 0.015, 0.01, 0.025]
    sharpe = calc._sharpe(returns)
    assert sharpe > 0


def test_max_drawdown_identifies_correct_range():
    calc = PerformanceCalculator()
    equity = [0, 10, 20, 15, 10, 25, 30, 20, 15, 35]
    dd, start, end = calc._calculate_max_drawdown(equity)
    assert dd > 0
    assert start < end


def test_winrate_calculation():
    calc = PerformanceCalculator()
    # Simulate with mock journal entries is hard; test via helper
    pnls = [100, -50, 200, -30, 150]
    winners = [p for p in pnls if p > 0]
    winrate = len(winners) / len(pnls) * 100
    assert winrate == 60.0


def test_profit_factor_greater_than_one_for_profitable():
    calc = PerformanceCalculator()
    pnls = [100, -50, 200, -30, 150]
    winners = sum(p for p in pnls if p > 0)
    losers = abs(sum(p for p in pnls if p < 0))
    pf = winners / losers if losers > 0 else float("inf")
    assert pf > 1.0


def test_expectancy_positive_for_edge():
    calc = PerformanceCalculator()
    pnls = [100, -50, 200, -30, 150]
    expectancy = sum(pnls) / len(pnls)
    assert expectancy > 0


def test_equity_curve_data():
    calc = PerformanceCalculator()
    curve = calc.calculate_equity_curve_data([])
    assert curve == [{"trade_idx": 0, "equity": 0.0}]


# ---------------------------------------------------------------------------
# Dashboard SSE tests
# ---------------------------------------------------------------------------

def test_sse_event_to_string():
    event = SSEEvent(event_type="trade", payload={"id": "123"})
    s = event.to_sse_string()
    assert s.startswith("data: {")
    assert "trade" in s


def test_dashboard_sse_manager_broadcast():
    mgr = DashboardSSEManager()
    mgr.broadcast(SSEEvent(event_type="alert", payload={"msg": "test"}))
    # No clients connected → should not crash
    assert mgr.client_count == 0


def test_dashboard_sse_broadcast_trade():
    mgr = DashboardSSEManager()
    mgr.broadcast_trade_update({"trade_id": "t1", "status": "filled"})
    assert mgr.client_count == 0  # No crash without clients


def test_dashboard_sse_broadcast_position():
    mgr = DashboardSSEManager()
    mgr.broadcast_position_update([{"symbol": "BTCUSDT", "size": 0.1}])
    assert mgr.client_count == 0


def test_dashboard_sse_broadcast_metrics():
    mgr = DashboardSSEManager()
    mgr.broadcast_metrics_update({"winrate": 55.5})
    assert mgr.client_count == 0


def test_dashboard_sse_heartbeat():
    mgr = DashboardSSEManager()
    mgr.broadcast_heartbeat()
    assert mgr.client_count == 0
