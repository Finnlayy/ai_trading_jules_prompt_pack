from datetime import datetime, timezone
import pytest
from app.services.loop_health_monitor import LoopStats

def test_loop_stats_record_cycle():
    stats = LoopStats()
    assert stats.cycles_completed == 0
    stats.record_cycle()
    assert stats.cycles_completed == 1

def test_loop_stats_record_signal():
    stats = LoopStats()
    assert stats.signals_generated == 0
    stats.record_signal()
    assert stats.signals_generated == 1

def test_loop_stats_record_trade():
    stats = LoopStats()
    assert stats.trades_executed == 0
    stats.record_trade()
    assert stats.trades_executed == 1

def test_loop_stats_record_error_and_history_limit():
    stats = LoopStats()
    assert stats.errors_last_5min == 0
    assert len(stats.error_history) == 0

    stats.record_error("error 1")
    assert stats.errors_last_5min == 1
    assert len(stats.error_history) == 1
    assert stats.error_history[0]["error"] == "error 1"
    assert "timestamp" in stats.error_history[0]

    for i in range(2, 25):
        stats.record_error(f"error {i}")

    assert stats.errors_last_5min == 24
    assert len(stats.error_history) == 20
    assert stats.error_history[-1]["error"] == "error 24"
    assert stats.error_history[0]["error"] == "error 5"

def test_loop_stats_reset_error_window():
    stats = LoopStats()
    stats.record_error("test")
    assert stats.errors_last_5min == 1
    stats.reset_error_window()
    assert stats.errors_last_5min == 0
    assert len(stats.error_history) == 1  # History should not be cleared by this method

from unittest.mock import patch, MagicMock
from app.services.loop_health_monitor import LoopHealthMonitor, HealthSnapshot

def test_loop_health_monitor_record_cycle_time():
    monitor = LoopHealthMonitor()
    assert monitor.get_avg_cycle_time_ms() == 0.0

    monitor.record_cycle_time(100.0)
    assert monitor.get_avg_cycle_time_ms() == 100.0

    monitor.record_cycle_time(200.0)
    assert monitor.get_avg_cycle_time_ms() == 150.0

    # Test limit of 100
    for i in range(105):
        monitor.record_cycle_time(10.0)

    assert len(monitor._cycle_times) == 100
    assert monitor.get_avg_cycle_time_ms() == 10.0

@patch('app.services.telegram_notifier.TelegramNotifier')
def test_loop_health_monitor_update_status_healthy(mock_notifier):
    monitor = LoopHealthMonitor()
    snapshot = monitor.update_status(is_running=True)
    assert snapshot.status == "healthy"
    assert monitor._status == "healthy"
    mock_notifier.assert_not_called()

@patch('app.services.telegram_notifier.TelegramNotifier')
def test_loop_health_monitor_update_status_halted(mock_notifier):
    monitor = LoopHealthMonitor()
    # It should become halted if not is_running

    # We will mock the instance returned
    mock_instance = MagicMock()
    mock_instance._is_configured.return_value = True
    mock_notifier.return_value = mock_instance

    snapshot = monitor.update_status(is_running=False)

    assert snapshot.status == "halted"
    assert monitor._status == "halted"

    # It should have sent an alert
    mock_notifier.assert_called_once()
    mock_instance.send_reconcile_alert.assert_called_once()
    alert_text = mock_instance.send_reconcile_alert.call_args[0][0]
    assert "HALTED" in alert_text

@patch('app.services.telegram_notifier.TelegramNotifier')
def test_loop_health_monitor_update_status_degraded(mock_notifier):
    monitor = LoopHealthMonitor()

    mock_instance = MagicMock()
    mock_instance._is_configured.return_value = True
    mock_notifier.return_value = mock_instance

    # Trigger degraded status by having 5 or more errors
    monitor.stats.errors_last_5min = 5
    snapshot = monitor.update_status(is_running=True)

    assert snapshot.status == "degraded"
    assert monitor._status == "degraded"

    mock_notifier.assert_called_once()
    mock_instance.send_reconcile_alert.assert_called_once()
    alert_text = mock_instance.send_reconcile_alert.call_args[0][0]
    assert "DEGRADED" in alert_text

def test_loop_health_monitor_reset():
    monitor = LoopHealthMonitor()
    monitor.record_cycle_time(100.0)
    monitor.stats.record_error("test error")
    monitor._status = "degraded"
    monitor._last_alert_status = "degraded"

    monitor.reset()

    assert monitor.get_avg_cycle_time_ms() == 0.0
    assert monitor.stats.errors_last_5min == 0
    assert len(monitor.stats.error_history) == 0
    assert monitor._status == "healthy"
    assert monitor._last_alert_status is None
