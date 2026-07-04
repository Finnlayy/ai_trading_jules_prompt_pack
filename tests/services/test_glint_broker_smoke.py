"""Smoke tests for GlintBroker.

Verifies command formatting, dry-run mode, and Telegram interaction
without sending real messages.
"""
import pytest
from datetime import datetime, timezone

from app.services.glint_broker import GlintBroker, GlintConfig
from app.schemas.m8_payload import M8Payload
from app.schemas.journal import DecisionEnum, FinalDecisionEnum
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum


class FakeNotifier:
    """Mock Telegram notifier that records sent messages."""
    def __init__(self):
        self.messages = []

    def send(self, text: str) -> bool:
        self.messages.append(text)
        return True

    def send_reject(self, symbol, reason, trade_id, intent=None):
        self.messages.append(f"REJECT: {symbol} {reason}")
        return True


class FakeReceiver:
    """Mock Telegram receiver with pre-loaded responses."""
    def __init__(self, responses=None):
        self.responses = responses or []
        self.poll_calls = 0

    def poll_sync(self, limit=20):
        self.poll_calls += 1
        return []

    def get_messages(self, limit=50):
        return self.responses

    def status(self):
        return {"configured": True, "stored_messages": len(self.responses)}


def _payload(
    signal_id: str = "test-1",
    symbol: str = "BTCUSDT",
    direction: str = "LONG",
    intent: str = "ENTRY",
    entry_price: float = 50000.0,
    stop_price: float = 48000.0,
    target_price: float = 54000.0,
    confluence_score: float = 85.0,
    crisis_score: float = 5.0,
) -> M8Payload:
    return M8Payload(
        signal_id=signal_id,
        symbol=symbol,
        timeframe="1h",
        direction=direction,
        intent=intent,
        account_mode="FUTURES",
        timestamp=datetime.now(timezone.utc).isoformat(),
        entry_price=entry_price,
        stop_price=stop_price,
        target_price=target_price,
        confluence_score=confluence_score,
        crisis_score=crisis_score,
        mc_dispersion=1.5,
        spread=3.0,
    )


def _patch_broker(broker):
    """Replace Telegram components with fakes and override blocking wait."""
    broker.notifier = FakeNotifier()
    broker.receiver = FakeReceiver()
    broker._wait_for_glint_response = lambda timeout_seconds=15: "[MOCK: GLINT response]"
    return broker


@pytest.fixture
def glint_broker_dry_run():
    """GlintBroker in dry-run mode (enabled, no live trading)."""
    broker = GlintBroker(
        config=GlintConfig(
            enabled=True,
            live_trading_enabled=False,
            telegram_chat_id="-1001234567890",
            bot_username="GlintTradeBot",
        ),
        journal_path="/tmp/test_glint_journal.jsonl",
    )
    return _patch_broker(broker)


@pytest.fixture
def glint_broker_live():
    """GlintBroker in live mode."""
    broker = GlintBroker(
        config=GlintConfig(
            enabled=True,
            live_trading_enabled=True,
            telegram_chat_id="-1001234567890",
            bot_username="GlintTradeBot",
        ),
        journal_path="/tmp/test_glint_journal.jsonl",
    )
    return _patch_broker(broker)


class TestGlintBrokerReadiness:
    def test_broker_ready_when_enabled(self, glint_broker_dry_run):
        assert glint_broker_dry_run.is_ready() is True
        assert glint_broker_dry_run.get_broker_name() == "GlintBroker"
        assert glint_broker_dry_run.get_broker_type() == "glint"
        assert glint_broker_dry_run.get_broker_mode() == "dry-run"

    def test_broker_not_ready_without_chat_id(self):
        broker = GlintBroker(
            config=GlintConfig(enabled=True, telegram_chat_id=""),
            journal_path="/tmp/test_glint_journal.jsonl",
        )
        assert broker.is_ready() is False

    def test_broker_not_ready_when_disabled(self):
        broker = GlintBroker(
            config=GlintConfig(enabled=False, telegram_chat_id="-100123"),
            journal_path="/tmp/test_glint_journal.jsonl",
        )
        assert broker.is_ready() is False

    def test_live_capable_only_when_all_set(self, glint_broker_live):
        assert glint_broker_live.is_live_capable() is True
        assert glint_broker_live.get_broker_mode() == "live"

    def test_not_live_capable_without_live_flag(self, glint_broker_dry_run):
        assert glint_broker_dry_run.is_live_capable() is False


class TestGlintBrokerExecution:
    def test_entry_long_command_format(self, glint_broker_dry_run):
        payload = _payload(symbol="BTCUSDT", direction="LONG", intent="ENTRY")
        entry = glint_broker_dry_run.execute_trade(
            payload=payload,
            decision=DecisionEnum.PROCEED_TO_SIMULATION,
            ai_decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
        )

        assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
        assert entry.symbol == "BTCUSDT"
        assert entry.result["status"] == "DRY_RUN"
        assert "LONG BTC for $50" in entry.result["command"]

        # Check Telegram notification was sent
        assert any("GLINT DRY-RUN" in msg for msg in glint_broker_dry_run.notifier.messages)
        assert any("LONG BTC for $50" in msg for msg in glint_broker_dry_run.notifier.messages)

    def test_entry_short_command_format(self, glint_broker_dry_run):
        payload = _payload(symbol="ETHUSDT", direction="SHORT", intent="ENTRY")
        entry = glint_broker_dry_run.execute_trade(
            payload=payload,
            decision=DecisionEnum.PROCEED_TO_SIMULATION,
            ai_decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
        )

        assert entry.result["status"] == "DRY_RUN"
        assert "SHORT ETH for $50" in entry.result["command"]

    def test_close_command_format(self, glint_broker_dry_run):
        payload = _payload(symbol="BTCUSDT", direction="LONG", intent="CLOSE")
        entry = glint_broker_dry_run.execute_trade(
            payload=payload,
            decision=DecisionEnum.PROCEED_TO_SIMULATION,
            ai_decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
        )

        assert entry.result["status"] == "DRY_RUN"
        assert "Close BTC" in entry.result["command"]

    def test_rejected_trade_no_command_sent(self, glint_broker_dry_run):
        payload = _payload(symbol="BTCUSDT", direction="LONG", intent="ENTRY")
        entry = glint_broker_dry_run.execute_trade(
            payload=payload,
            decision=DecisionEnum.REJECT,
            reject_reason="HIGH_CRISIS",
            ai_decision=AIDecisionEnum.REJECT,
        )

        assert entry.final_decision == FinalDecisionEnum.REJECTED
        assert entry.result["status"] == "REJECTED"
        assert any("REJECT: BTCUSDT HIGH_CRISIS" in msg for msg in glint_broker_dry_run.notifier.messages)

    def test_symbol_normalization(self, glint_broker_dry_run):
        """Symbols like BTC_USDT_PERP should become BTC."""
        payload = _payload(symbol="BTC_USDT_PERP", direction="LONG", intent="ENTRY")
        entry = glint_broker_dry_run.execute_trade(
            payload=payload,
            decision=DecisionEnum.PROCEED_TO_SIMULATION,
            ai_decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
        )

        assert "LONG BTC for $50" in entry.result["command"]

    def test_disabled_broker_returns_dry_run(self):
        broker = GlintBroker(
            config=GlintConfig(enabled=False),
            journal_path="/tmp/test_glint_journal.jsonl",
        )
        broker = _patch_broker(broker)

        payload = _payload()
        entry = broker.execute_trade(
            payload=payload,
            decision=DecisionEnum.PROCEED_TO_SIMULATION,
            ai_decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
        )

        assert entry.result["status"] == "DRY_RUN_GLINT_DISABLED"
        assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM


class TestGlintBrokerLiveExecution:
    def test_live_entry_sends_command(self, glint_broker_live):
        payload = _payload(symbol="BTCUSDT", direction="LONG", intent="ENTRY")
        entry = glint_broker_live.execute_trade(
            payload=payload,
            decision=DecisionEnum.PROCEED_TO_SIMULATION,
            ai_decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
        )

        assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
        assert entry.result["status"] == "PENDING_GLINT"
        assert "LONG BTC for $50" in entry.result["command"]

        # Telegram notification should indicate LIVE
        assert any("GLINT LIVE" in msg for msg in glint_broker_live.notifier.messages)

    def test_live_close_sends_command(self, glint_broker_live):
        payload = _payload(symbol="ETHUSDT", direction="SHORT", intent="CLOSE")
        entry = glint_broker_live.execute_trade(
            payload=payload,
            decision=DecisionEnum.PROCEED_TO_SIMULATION,
            ai_decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
        )

        assert entry.final_decision == FinalDecisionEnum.EXECUTED_SIM
        assert "Close ETH" in entry.result["command"]


class TestGlintBrokerPositions:
    def test_get_positions_when_ready(self, glint_broker_dry_run):
        result = glint_broker_dry_run.get_positions()
        assert result["raw_response"] == "[MOCK: GLINT response]"
        assert "queried_at" in result

    def test_get_positions_when_not_ready(self):
        broker = GlintBroker(
            config=GlintConfig(enabled=True, telegram_chat_id=""),
            journal_path="/tmp/test_glint_journal.jsonl",
        )
        result = broker.get_positions()
        assert result["error"] == "not_ready"


class TestGlintBrokerHealth:
    def test_health_returns_expected_fields(self, glint_broker_dry_run):
        health = glint_broker_dry_run.health()
        assert health["name"] == "GlintBroker"
        assert health["type"] == "glint"
        assert health["mode"] == "dry-run"
        assert health["ready"] is True
        assert health["live_capable"] is False

    def test_rejected_trade_records_reason(self, glint_broker_dry_run):
        payload = _payload(symbol="ETHUSDT", direction="SHORT", intent="ENTRY")
        entry = glint_broker_dry_run.execute_trade(
            payload=payload,
            decision=DecisionEnum.REJECT,
            reject_reason="AI_CONFIDENCE_LOW",
            ai_decision=AIDecisionEnum.REJECT,
        )

        assert entry.final_decision == FinalDecisionEnum.REJECTED
        assert entry.result["status"] == "REJECTED"
        assert "AI_CONFIDENCE_LOW" in entry.result["reject_reason"]
        assert any("REJECT: ETHUSDT AI_CONFIDENCE_LOW" in msg for msg in glint_broker_dry_run.notifier.messages)
