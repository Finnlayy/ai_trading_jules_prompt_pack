from unittest.mock import Mock, patch
from datetime import datetime, timezone
from app.services.loop_health_monitor import LoopHealthMonitor, LoopStats

def test_initial_health_status():
    monitor = LoopHealthMonitor()
    snapshot = monitor.update_status(is_running=True)
    assert snapshot.status == "healthy"
    assert snapshot.cycles_completed == 0

def test_record_cycle():
    monitor = LoopHealthMonitor()
    monitor.stats.record_cycle()
    snapshot = monitor.update_status(is_running=True)
    assert snapshot.cycles_completed == 1

def test_record_signal():
    monitor = LoopHealthMonitor()
    monitor.stats.record_signal()
    snapshot = monitor.update_status(is_running=True)
    assert snapshot.signals_generated == 1

def test_record_trade():
    monitor = LoopHealthMonitor()
    monitor.stats.record_trade()
    snapshot = monitor.update_status(is_running=True)
    assert snapshot.trades_executed == 1

def test_halted_status():
    monitor = LoopHealthMonitor()
    snapshot = monitor.update_status(is_running=False)
    assert snapshot.status == "halted"

def test_degraded_status():
    monitor = LoopHealthMonitor()
    for _ in range(5):
        monitor.stats.record_error("Test error")

    snapshot = monitor.update_status(is_running=True)
    assert snapshot.status == "degraded"
    assert snapshot.errors_last_5min == 5

def test_error_history_limit():
    monitor = LoopHealthMonitor()
    for i in range(25):
        monitor.stats.record_error(f"Error {i}")

    assert len(monitor.stats.error_history) == 20
    assert monitor.stats.error_history[-1]["error"] == "Error 24"

def test_reset_error_window():
    monitor = LoopHealthMonitor()
    monitor.stats.record_error("Test error")
    monitor.stats.reset_error_window()
    assert monitor.stats.errors_last_5min == 0

def test_average_cycle_time():
    monitor = LoopHealthMonitor()
    monitor.record_cycle_time(100.0)
    monitor.record_cycle_time(200.0)
    assert monitor.get_avg_cycle_time_ms() == 150.0

def test_cycle_time_limit():
    monitor = LoopHealthMonitor()
    for i in range(110):
        monitor.record_cycle_time(10.0)

    assert len(monitor._cycle_times) == 100

def test_reset_functionality():
    monitor = LoopHealthMonitor()
    monitor.stats.record_cycle()
    monitor.record_cycle_time(150.0)
    monitor.reset()

    snapshot = monitor.update_status(is_running=True)
    assert snapshot.cycles_completed == 0
    assert monitor.get_avg_cycle_time_ms() == 0.0

def test_alert_sent_on_status_change():
    monitor = LoopHealthMonitor()

    # We also need to mock _is_configured since otherwise it won't send the alert
    with patch("app.services.telegram_notifier.TelegramNotifier.send_reconcile_alert", return_value=True) as mock_send:
        with patch("app.services.telegram_notifier.TelegramNotifier._is_configured", return_value=True) as mock_configured:
            # Simulate degraded status
            for _ in range(5):
                monitor.stats.record_error("Test error")

            # Trigger update and maybe alert
            snapshot = monitor.update_status(is_running=True)

            assert snapshot.status == "degraded"
            mock_send.assert_called_once()
            assert "DEGRADED" in mock_send.call_args[0][0]

def test_no_alert_on_same_status():
    monitor = LoopHealthMonitor()

    with patch("app.services.telegram_notifier.TelegramNotifier.send_reconcile_alert", return_value=True) as mock_send:
        with patch("app.services.telegram_notifier.TelegramNotifier._is_configured", return_value=True):
            # Initial call sets healthy, doesn't send alert because it's not degraded/halted
            monitor.update_status(is_running=True)
            assert mock_send.call_count == 0

            # Change to degraded
            for _ in range(5):
                monitor.stats.record_error("Test error")
            monitor.update_status(is_running=True)
            assert mock_send.call_count == 1

            # Second call also degraded, should NOT trigger another alert
            monitor.update_status(is_running=True)
            assert mock_send.call_count == 1

def test_alert_exceptions_swallowed():
    monitor = LoopHealthMonitor()

    with patch("app.services.telegram_notifier.TelegramNotifier.send_reconcile_alert", side_effect=Exception("Test Exception")):
        with patch("app.services.telegram_notifier.TelegramNotifier._is_configured", return_value=True):
            # Ensure that triggering an alert which throws an exception doesn't blow up the monitor
            for _ in range(5):
                monitor.stats.record_error("Test error")

            # This shouldn't raise
            monitor.update_status(is_running=True)
