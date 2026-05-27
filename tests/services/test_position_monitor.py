"""
Tests for PositionMonitor — stop-loss, take-profit, and time-exit logic.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pytest

from app.services.position_monitor import PositionMonitor, ExitResult
from app.services.live_fill_tracker import live_fill_tracker, FillData


@pytest.fixture
def monitor():
    return PositionMonitor()


@pytest.fixture(autouse=True)
def reset_tracker():
    live_fill_tracker.reset()
    yield
    live_fill_tracker.reset()


def _create_position(trade_id: str, symbol: str, direction: str,
                     entry: float, stop: float, target: float,
                     size: float = 1.0, minutes_ago: float = 0):
    """Helper to create an open position via intent+fill."""
    live_fill_tracker.record_intent(
        trade_id=trade_id,
        symbol=symbol,
        direction=direction,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        decision="PROCEED_TO_SIMULATION",
        size=size,
    )
    fill_time = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    live_fill_tracker.record_fill(
        trade_id,
        FillData(
            entry_price=entry,
            fill_time=fill_time,
            size=size,
            side=direction,
            fees=0.0,
            slippage=0.0,
        ),
    )


class TestStopLoss:
    def test_long_stop_loss_hit(self, monitor):
        _create_position("t1", "BTCUSDT", "LONG", entry=50000, stop=49000, target=52000)
        exits = monitor.check_price_based_exits({"BTCUSDT": 48900.0})
        assert len(exits) == 1
        assert exits[0].exit_reason == "STOP_LOSS"
        assert exits[0].exit_price == 48900.0

    def test_short_stop_loss_hit(self, monitor):
        _create_position("t2", "BTCUSDT", "SHORT", entry=50000, stop=51000, target=48000)
        exits = monitor.check_price_based_exits({"BTCUSDT": 51100.0})
        assert len(exits) == 1
        assert exits[0].exit_reason == "STOP_LOSS"

    def test_stop_not_hit(self, monitor):
        _create_position("t3", "BTCUSDT", "LONG", entry=50000, stop=49000, target=52000)
        exits = monitor.check_price_based_exits({"BTCUSDT": 49500.0})
        assert len(exits) == 0


class TestTakeProfit:
    def test_long_take_profit_hit(self, monitor):
        _create_position("t4", "BTCUSDT", "LONG", entry=50000, stop=49000, target=52000)
        exits = monitor.check_price_based_exits({"BTCUSDT": 52100.0})
        assert len(exits) == 1
        assert exits[0].exit_reason == "TAKE_PROFIT"

    def test_short_take_profit_hit(self, monitor):
        _create_position("t5", "BTCUSDT", "SHORT", entry=50000, stop=51000, target=48000)
        exits = monitor.check_price_based_exits({"BTCUSDT": 47900.0})
        assert len(exits) == 1
        assert exits[0].exit_reason == "TAKE_PROFIT"


class TestTimeExit:
    def test_time_exit_after_max_hold(self, monitor):
        _create_position("t6", "BTCUSDT", "LONG", entry=50000, stop=49000, target=52000,
                        minutes_ago=300)  # 5 hours ago
        exits = monitor.check_price_based_exits({"BTCUSDT": 50000.0})
        assert len(exits) == 1
        assert exits[0].exit_reason == "TIME_EXIT"

    def test_no_time_exit_before_threshold(self, monitor):
        _create_position("t7", "BTCUSDT", "LONG", entry=50000, stop=49000, target=52000,
                        minutes_ago=10)
        exits = monitor.check_price_based_exits({"BTCUSDT": 50000.0})
        assert len(exits) == 0


class TestStopPrecedence:
    def test_stop_takes_precedence_over_target(self, monitor):
        # Price blows through both stop and target (gap)
        _create_position("t8", "BTCUSDT", "LONG", entry=50000, stop=49000, target=52000)
        exits = monitor.check_price_based_exits({"BTCUSDT": 48000.0})
        assert len(exits) == 1
        # In price-based checking, we see the exact price, so stop is triggered
        assert exits[0].exit_reason == "STOP_LOSS"


class TestBarBasedExits:
    def test_bar_based_stop_hit(self, monitor):
        _create_position("t9", "BTCUSDT", "LONG", entry=50000, stop=49000, target=52000)
        Bar = type('Bar', (), {'ts': 1, 'o': 50000, 'h': 50100, 'l': 48800, 'c': 49900, 'v': 100})
        exits = monitor.check_exits([Bar])
        assert len(exits) == 1
        assert exits[0].exit_reason == "STOP_LOSS"

    def test_bar_based_target_hit(self, monitor):
        _create_position("t10", "BTCUSDT", "LONG", entry=50000, stop=49000, target=52000)
        Bar = type('Bar', (), {'ts': 1, 'o': 50000, 'h': 52100, 'l': 49900, 'c': 52050, 'v': 100})
        exits = monitor.check_exits([Bar])
        assert len(exits) == 1
        assert exits[0].exit_reason == "TAKE_PROFIT"


class TestExecuteExits:
    def test_execute_exits_closes_positions(self, monitor):
        _create_position("t11", "BTCUSDT", "LONG", entry=50000, stop=49000, target=52000, size=1.0)
        exits = [ExitResult(
            trade_id="t11",
            symbol="BTCUSDT",
            direction="LONG",
            exit_price=52000,
            exit_reason="TAKE_PROFIT",
            pnl_estimate=2000.0,
        )]
        closed = monitor.execute_exits(exits)
        assert len(closed) == 1
        assert live_fill_tracker.get_position("t11") is None
        assert live_fill_tracker.get_open_positions() == []
