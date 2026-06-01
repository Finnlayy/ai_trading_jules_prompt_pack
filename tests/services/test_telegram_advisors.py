import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict
import time
import asyncio

from app.services.telegram_advisors import TelegramAdvisorHub, AdvisorAskResult
from app.services.telegram_news_receiver import GlintMessage

@pytest.fixture
def mock_receiver():
    receiver = AsyncMock()
    receiver._is_configured = MagicMock(return_value=True)
    return receiver

@pytest.fixture
def hub():
    return TelegramAdvisorHub()

def test_status(hub):
    status = hub.status()
    assert "auto_enabled" in status
    assert "timeout_seconds" in status
    assert "glint" in status
    assert "manus" in status

@pytest.mark.asyncio
@patch("app.services.telegram_advisors.TELEGRAM_BOT_TOKEN", "mock_token")
@patch("app.services.telegram_advisors.TelegramNotifier")
@patch("app.services.telegram_advisors.asyncio.to_thread")
async def test_ask_success(mock_to_thread, MockNotifier, hub, mock_receiver):
    mock_to_thread.return_value = True  # send was successful

    # Mocking the responses from poll_async
    # 1st call is drain (returns empty)
    # 2nd call returns a valid message
    msg = GlintMessage(
        id=1, text="Response", sender="bot_user", timestamp="now", chat_id="123"
    )
    mock_receiver.poll_async.side_effect = [[], [msg]]

    result = await hub._ask(
        advisor="test_advisor",
        enabled=True,
        receiver=mock_receiver,
        chat_id="123",
        bot_username="bot_user",
        question="Question?",
        require_enabled=False,
        timeout_seconds=1.0
    )

    assert result.advisor == "test_advisor"
    assert result.sent is True
    assert result.timed_out is False
    assert len(result.messages) == 1
    assert result.messages[0]["text"] == "Response"

@pytest.mark.asyncio
@patch("app.services.telegram_advisors.TELEGRAM_BOT_TOKEN", "mock_token")
@patch("app.services.telegram_advisors.TelegramNotifier")
@patch("app.services.telegram_advisors.asyncio.to_thread")
async def test_ask_timeout(mock_to_thread, MockNotifier, hub, mock_receiver):
    mock_to_thread.return_value = True  # send was successful

    # Mocking poll_async to always return empty, causing timeout
    mock_receiver.poll_async.return_value = []

    # Patch time.monotonic and asyncio.sleep to speed up test
    with patch("app.services.telegram_advisors.time.monotonic", side_effect=[0, 0, 2]):
        with patch("app.services.telegram_advisors.asyncio.sleep", new_callable=AsyncMock):
            result = await hub._ask(
                advisor="test_advisor",
                enabled=True,
                receiver=mock_receiver,
                chat_id="123",
                bot_username="bot_user",
                question="Question?",
                require_enabled=False,
                timeout_seconds=1.0
            )

    assert result.advisor == "test_advisor"
    assert result.sent is True
    assert result.timed_out is True
    assert len(result.messages) == 0

@pytest.mark.asyncio
@patch("app.services.telegram_advisors.TELEGRAM_BOT_TOKEN", "mock_token")
async def test_ask_not_configured(hub):
    mock_receiver = AsyncMock()
    mock_receiver._is_configured = MagicMock(return_value=False)

    result = await hub._ask(
        advisor="test_advisor",
        enabled=True,
        receiver=mock_receiver,
        chat_id="123",
        bot_username="bot_user",
        question="Question?",
        require_enabled=False,
        timeout_seconds=1.0
    )

    assert result.configured is False
    assert result.sent is False
    assert "not configured" in result.error

@pytest.mark.asyncio
@patch("app.services.telegram_advisors.TELEGRAM_BOT_TOKEN", "mock_token")
async def test_ask_require_enabled_but_disabled(hub, mock_receiver):
    result = await hub._ask(
        advisor="test_advisor",
        enabled=False,
        receiver=mock_receiver,
        chat_id="123",
        bot_username="bot_user",
        question="Question?",
        require_enabled=True,
        timeout_seconds=1.0
    )

    assert result.advisor == "test_advisor"
    assert result.enabled is False
    assert result.sent is False
    assert result.timed_out is False

@pytest.mark.asyncio
@patch("app.services.telegram_advisors.TELEGRAM_BOT_TOKEN", "mock_token")
@patch("app.services.telegram_advisors.TelegramNotifier")
@patch("app.services.telegram_advisors.asyncio.to_thread")
async def test_ask_send_failed(mock_to_thread, MockNotifier, hub, mock_receiver):
    mock_to_thread.return_value = False  # send failed

    result = await hub._ask(
        advisor="test_advisor",
        enabled=True,
        receiver=mock_receiver,
        chat_id="123",
        bot_username="bot_user",
        question="Question?",
        require_enabled=False,
        timeout_seconds=1.0
    )

    assert result.advisor == "test_advisor"
    assert result.sent is False
    assert "Failed to send question" in result.error

def test_message_matches():
    # Test message_matches logic
    question = "Positions"

    # Exact match of question should be ignored (bot echoing question)
    msg1 = GlintMessage(id=1, text="Positions", sender="bot_user", timestamp="now", chat_id="123")
    assert not TelegramAdvisorHub._message_matches(msg1, "bot_user", question)

    # Matching bot_username
    msg2 = GlintMessage(id=2, text="Here are positions...", sender="bot_user", timestamp="now", chat_id="123")
    assert TelegramAdvisorHub._message_matches(msg2, "bot_user", question)

    # Different bot_username
    msg3 = GlintMessage(id=3, text="Here are positions...", sender="other_user", timestamp="now", chat_id="123")
    assert not TelegramAdvisorHub._message_matches(msg3, "bot_user", question)

    # No bot_username specified (matches all non-echo)
    msg4 = GlintMessage(id=4, text="Here are positions...", sender="anyone", timestamp="now", chat_id="123")
    assert TelegramAdvisorHub._message_matches(msg4, "", question)

@pytest.mark.asyncio
@patch("app.services.telegram_advisors.TelegramAdvisorHub._ask")
async def test_ask_glint(mock_ask, hub):
    mock_ask.return_value = AdvisorAskResult(
        advisor="glint", enabled=True, configured=True, sent=True, timed_out=False, question="Positions", messages=[]
    )
    result = await hub.ask_glint(question="Positions", require_enabled=True, timeout_seconds=10.0)
    assert result["advisor"] == "glint"
    mock_ask.assert_called_once()

@pytest.mark.asyncio
@patch("app.services.telegram_advisors.TelegramAdvisorHub._ask")
async def test_ask_manus(mock_ask, hub):
    mock_ask.return_value = AdvisorAskResult(
        advisor="manus", enabled=True, configured=True, sent=True, timed_out=False, question="Test?", messages=[]
    )
    result = await hub.ask_manus(question="Test?", require_enabled=True, timeout_seconds=10.0)
    assert result["advisor"] == "manus"
    mock_ask.assert_called_once()

@pytest.mark.asyncio
@patch("app.services.telegram_advisors.TelegramAdvisorHub.ask_glint")
@patch("app.services.telegram_advisors.TelegramAdvisorHub.ask_manus")
async def test_ask_signal_advisors_success(mock_ask_manus, mock_ask_glint, hub):
    hub.auto_enabled = True

    with patch("app.services.telegram_advisors.MANUS_ENABLED", True), \
         patch("app.services.telegram_advisors.GLINT_ENABLED", True):

        mock_ask_manus.return_value = {"advisor": "manus", "messages": []}
        mock_ask_glint.return_value = {"advisor": "glint", "messages": []}

        result = await hub.ask_signal_advisors("Manus Question?")

        assert result["auto_enabled"] is True
        assert len(result["advisors"]) == 2
        mock_ask_manus.assert_called_once()
        mock_ask_glint.assert_called_once()

@pytest.mark.asyncio
async def test_ask_signal_advisors_auto_disabled(hub):
    hub.auto_enabled = False
    result = await hub.ask_signal_advisors("Manus Question?")
    assert result["auto_enabled"] is False
    assert len(result["advisors"]) == 0

@pytest.mark.asyncio
@patch("app.services.telegram_advisors.TelegramAdvisorHub.ask_glint")
@patch("app.services.telegram_advisors.TelegramAdvisorHub.ask_manus")
async def test_ask_signal_advisors_exception_handling(mock_ask_manus, mock_ask_glint, hub):
    hub.auto_enabled = True

    with patch("app.services.telegram_advisors.MANUS_ENABLED", True), \
         patch("app.services.telegram_advisors.GLINT_ENABLED", True):

        mock_ask_manus.side_effect = Exception("Test Error")
        mock_ask_glint.return_value = {"advisor": "glint", "messages": []}

        result = await hub.ask_signal_advisors("Manus Question?")

        assert result["auto_enabled"] is True
        assert len(result["advisors"]) == 2

        # one should be the normal glint result, one should be the exception dictionary
        errors = [adv for adv in result["advisors"] if adv.get("error")]
        assert len(errors) == 1
        assert "Test Error" in errors[0]["error"]

@pytest.mark.asyncio
async def test_ask_signal_advisors_no_tasks(hub):
    hub.auto_enabled = True

    with patch("app.services.telegram_advisors.MANUS_ENABLED", False), \
         patch("app.services.telegram_advisors.GLINT_ENABLED", False):

        result = await hub.ask_signal_advisors("Manus Question?")
        assert result["auto_enabled"] is True
        assert len(result["advisors"]) == 0
