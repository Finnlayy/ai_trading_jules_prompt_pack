from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from app.services.loop_health_monitor import LoopStats, LoopHealthMonitor, HealthSnapshot


def test_loop_stats_recording():
    stats = LoopStats()
    assert stats.cycles_completed == 0
    assert stats.signals_generated == 0
    assert stats.trades_executed == 0
    assert stats.errors_last_5min == 0
    assert len(stats.error_history) == 0

    stats.record_cycle()
    assert stats.cycles_completed == 1

    stats.record_signal()
    assert stats.signals_generated == 1

    stats.record_trade()
    assert stats.trades_executed == 1

    stats.record_error("Test error 1")
    assert stats.errors_last_5min == 1
    assert len(stats.error_history) == 1
    assert stats.error_history[0]["error"] == "Test error 1"


def test_loop_stats_error_history_limit():
    stats = LoopStats()
    for i in range(25):
        stats.record_error(f"Error {i}")

    assert stats.errors_last_5min == 25
    assert len(stats.error_history) == 20
    assert stats.error_history[-1]["error"] == "Error 24"
    assert stats.error_history[0]["error"] == "Error 5"


def test_loop_stats_reset_error_window():
    stats = LoopStats()
    stats.record_error("Test error")
    assert stats.errors_last_5min == 1

    stats.reset_error_window()
    assert stats.errors_last_5min == 0
    # ensure history is untouched
    assert len(stats.error_history) == 1


def test_loop_health_monitor_cycle_times():
    monitor = LoopHealthMonitor()
    assert monitor.get_avg_cycle_time_ms() == 0.0

    monitor.record_cycle_time(10.0)
    monitor.record_cycle_time(20.0)
    assert monitor.get_avg_cycle_time_ms() == 15.0


def test_loop_health_monitor_cycle_time_limit():
    monitor = LoopHealthMonitor()
    for i in range(1, 105):
        monitor.record_cycle_time(i * 10.0)

    # Should only keep the last 100
    assert len(monitor._cycle_times) == 100
    assert monitor._cycle_times[0] == 50.0  # (5 * 10.0)
    assert monitor._cycle_times[-1] == 1040.0


def test_loop_health_monitor_status_healthy():
    monitor = LoopHealthMonitor()
    snapshot = monitor.update_status(is_running=True)

    assert snapshot.status == "healthy"
    assert snapshot.errors_last_5min == 0
    assert monitor._status == "healthy"


def test_loop_health_monitor_status_halted():
    monitor = LoopHealthMonitor()
    snapshot = monitor.update_status(is_running=False)

    assert snapshot.status == "halted"
    assert monitor._status == "halted"


def test_loop_health_monitor_status_degraded():
    monitor = LoopHealthMonitor()

    # Simulate errors
    for _ in range(5):
        monitor.stats.record_error("Simulated error")

    snapshot = monitor.update_status(is_running=True)

    assert snapshot.status == "degraded"
    assert snapshot.errors_last_5min == 5
    assert monitor._status == "degraded"


@patch("app.services.telegram_notifier.TelegramNotifier.send_reconcile_alert")
def test_loop_health_monitor_alerts(mock_send_reconcile_alert):
    monitor = LoopHealthMonitor()

    # 1. Update to healthy (should not send alert)
    monitor.update_status(is_running=True)
    mock_send_reconcile_alert.assert_not_called()

    # 2. Update to degraded (should send alert once)
    for _ in range(5):
        monitor.stats.record_error("Error")

    monitor.update_status(is_running=True)
    # The actual implementation fails if NOTIFICATIONS_ENABLED is False or bot token missing
    # But because we mock the method itself, it still doesn't get called if it bails earlier due to config check

    # Let's mock _is_configured too so it bypasses config check
    with patch("app.services.telegram_notifier.TelegramNotifier._is_configured", return_value=True):
        # We need to reset the alert status so it actually tries to send again
        monitor._last_alert_status = None
        monitor.update_status(is_running=True)
        assert mock_send_reconcile_alert.call_count == 1

        # 3. Update to degraded again (should NOT send alert because status hasn't changed)
        monitor.update_status(is_running=True)
        assert mock_send_reconcile_alert.call_count == 1

        # 4. Update to halted (should send alert once)
        monitor.update_status(is_running=False)
        assert mock_send_reconcile_alert.call_count == 2

        # 5. Update to healthy again (should NOT send alert since 'healthy' is not in alert list)
        monitor.stats.reset_error_window()
        monitor.update_status(is_running=True)
        assert mock_send_reconcile_alert.call_count == 2


def test_loop_health_monitor_reset():
    monitor = LoopHealthMonitor()
    monitor.record_cycle_time(100.0)
    monitor.stats.record_error("err")
    monitor.update_status(is_running=False)  # sets to halted

    assert monitor._status == "halted"
    assert len(monitor._cycle_times) == 1

    monitor.reset()

    assert monitor._status == "healthy"
    assert len(monitor._cycle_times) == 0
    assert monitor.stats.errors_last_5min == 0
    assert monitor._last_alert_status is None
