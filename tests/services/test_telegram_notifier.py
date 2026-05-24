from unittest.mock import Mock, patch
from app.services.telegram_notifier import TelegramNotifier, TelegramConfig


def test_send_heartbeat_formats_message():
    config = TelegramConfig(enabled=True, bot_token="token", chat_id="123")
    notifier = TelegramNotifier(config)

    with patch.object(notifier, "send", return_value=True) as send_mock:
        notifier.send_heartbeat(uptime_minutes=65, trades_today=3, circuit_status={"drawdown_pct": 2.5, "halted": False})

    text = send_mock.call_args[0][0]
    assert "HEARTBEAT" in text
    assert "65 min" in text
    assert "3" in text
    assert "OK" in text


def test_send_reconcile_alert():
    config = TelegramConfig(enabled=True, bot_token="token", chat_id="123")
    notifier = TelegramNotifier(config)

    with patch.object(notifier, "send", return_value=True) as send_mock:
        notifier.send_reconcile_alert(["BTC: local=1.0 vs exchange=0.5"])

    text = send_mock.call_args[0][0]
    assert "RECONCILIATION ALERT" in text
    assert "BTC: local=1.0 vs exchange=0.5" in text


def test_send_fill_alert():
    config = TelegramConfig(enabled=True, bot_token="token", chat_id="123")
    notifier = TelegramNotifier(config)

    with patch.object(notifier, "send", return_value=True) as send_mock:
        notifier.send_fill_alert("BTCUSDT", "ord-1", 50100.0, 50000.0)

    text = send_mock.call_args[0][0]
    assert "FILL ALERT" in text
    assert "50100.0" in text
    assert "50000.0" in text
