import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from dataclasses import asdict

from app.services.telegram_advisors import TelegramAdvisorHub, AdvisorAskResult
from app.services.telegram_news_receiver import GlintMessage

@pytest.fixture
def advisor_hub():
    with patch("app.services.telegram_advisors.AI_TELEGRAM_ADVISORS_ENABLED", True), \
         patch("app.services.telegram_advisors.AI_TELEGRAM_ADVISOR_TIMEOUT_SECONDS", 1.0), \
         patch("app.services.telegram_advisors.GLINT_ENABLED", True), \
         patch("app.services.telegram_advisors.MANUS_ENABLED", True):
        hub = TelegramAdvisorHub()
        hub.timeout_seconds = 0.1 # short timeout for tests
        yield hub

def test_status(advisor_hub):
    with patch("app.services.telegram_advisors.telegram_news_receiver_instance._is_configured", return_value=True), \
         patch("app.services.telegram_advisors.manus_telegram_receiver_instance._is_configured", return_value=False), \
         patch("app.services.telegram_advisors.GLINT_BOT_USERNAME", "glint_bot"), \
         patch("app.services.telegram_advisors.MANUS_BOT_USERNAME", "manus_bot"):
        status = advisor_hub.status()
        assert status["auto_enabled"] is True
        assert status["glint"]["configured"] is True
        assert status["manus"]["configured"] is False
        assert status["glint"]["bot_username"] == "glint_bot"

def test_message_matches():
    msg = GlintMessage(id=1, text="Test answer", sender="@glint_bot", timestamp="123", chat_id="1")
    assert TelegramAdvisorHub._message_matches(msg, "glint_bot", "Question?") is True

    # Should ignore question echoes
    msg_echo = GlintMessage(id=2, text="Question?", sender="@glint_bot", timestamp="123", chat_id="1")
    assert TelegramAdvisorHub._message_matches(msg_echo, "glint_bot", "Question?") is False

def test_message_to_dict():
    msg = GlintMessage(id=1, text="text", sender="sender", timestamp="123", chat_id="1")
    d = TelegramAdvisorHub._message_to_dict(msg)
    assert d == {"id": 1, "text": "text", "sender": "sender", "timestamp": "123", "chat_id": "1"}

@pytest.mark.asyncio
async def test_ask_not_configured(advisor_hub):
    receiver_mock = MagicMock()
    receiver_mock._is_configured.return_value = False

    with patch("app.services.telegram_advisors.TELEGRAM_BOT_TOKEN", "token"):
        res = await advisor_hub._ask(
            advisor="test",
            enabled=True,
            receiver=receiver_mock,
            chat_id="123",
            bot_username="bot",
            question="q",
            require_enabled=True,
            timeout_seconds=0.1
        )
        assert res.configured is False
        assert "not configured" in res.error

@pytest.mark.asyncio
async def test_ask_success(advisor_hub):
    receiver_mock = MagicMock()
    receiver_mock._is_configured.return_value = True

    # First poll returns nothing (drain), second returns a matching message
    msg = GlintMessage(id=1, text="Answer", sender="bot", timestamp="123", chat_id="123")
    receiver_mock.poll_async = AsyncMock(side_effect=[[], [msg]])

    with patch("app.services.telegram_advisors.TELEGRAM_BOT_TOKEN", "token"), \
         patch("app.services.telegram_notifier.TelegramNotifier.send", return_value=True):
        res = await advisor_hub._ask(
            advisor="test",
            enabled=True,
            receiver=receiver_mock,
            chat_id="123",
            bot_username="bot",
            question="q",
            require_enabled=True,
            timeout_seconds=1.0
        )
        assert res.sent is True
        assert res.timed_out is False
        assert len(res.messages) == 1
        assert res.messages[0]["text"] == "Answer"

@pytest.mark.asyncio
async def test_ask_signal_advisors(advisor_hub):
    with patch.object(advisor_hub, "ask_manus", return_value={"advisor": "manus", "messages": []}) as mock_manus, \
         patch.object(advisor_hub, "ask_glint", return_value={"advisor": "glint", "messages": []}) as mock_glint:
        res = await advisor_hub.ask_signal_advisors("question")
        assert res["auto_enabled"] is True
        assert len(res["advisors"]) == 2
        mock_manus.assert_called_once()
        mock_glint.assert_called_once()
