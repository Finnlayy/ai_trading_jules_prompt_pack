from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.journal import DecisionEnum, FinalDecisionEnum
from app.schemas.m8_payload import M8Payload
from app.services.pionex_direct_broker import PionexDirectBroker, PionexDirectConfig


def _payload(**overrides) -> dict:
    payload = {
        "signal_id": "safety-1",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "direction": "LONG",
        "timestamp": "2026-05-20T10:00:00Z",
        "entry_price": 100.0,
        "stop_price": 99.0,
        "target_price": 102.0,
        "confluence_score": 85.0,
        "crisis_score": 10.0,
        "mc_dispersion": 1.0,
        "spread": 1.0,
    }
    payload.update(overrides)
    return payload


def test_m8_payload_preserves_backward_compatible_entry_default():
    payload = M8Payload(**_payload())

    assert payload.intent == "ENTRY"
    assert payload.account_mode == "SPOT"


def test_m8_payload_rejects_unknown_intent():
    with pytest.raises(ValidationError):
        M8Payload(**_payload(intent="FLIP"))


def test_direct_broker_live_capability_requires_all_gates(tmp_path):
    missing_credentials = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=True,
            api_key="",
            api_secret="",
            allowed_symbols=("BTC_USDT",),
        ),
        journal_path=str(tmp_path / "journal.jsonl"),
    )
    live_ready = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=True,
            api_key="api-key",
            api_secret="api-secret",
            allowed_symbols=("BTC_USDT",),
        ),
        journal_path=str(tmp_path / "journal-live.jsonl"),
    )

    assert missing_credentials.is_live_capable() is False
    assert live_ready.is_live_capable() is True


def test_direct_broker_dry_run_stays_non_live_even_with_allowed_symbol(tmp_path):
    broker = PionexDirectBroker(
        config=PionexDirectConfig(
            enabled=True,
            live_trading_enabled=False,
            allowed_symbols=("BTC_USDT",),
        ),
        journal_path=str(tmp_path / "journal.jsonl"),
    )

    result = broker.execute_trade(
        payload=M8Payload(**_payload()),
        decision=DecisionEnum.PROCEED_TO_SIMULATION,
    )

    assert result.final_decision == FinalDecisionEnum.EXECUTED_SIM
    assert result.result["status"] == "DRY_RUN_DIRECT"
    assert result.simulated_fill["live_mode"] is False


def test_env_example_keeps_live_execution_disabled_by_default():
    text = Path(".env.example").read_text(encoding="utf-8")

    assert "BROKER_MODE=simulation" in text
    assert "PIONEX_DIRECT_ENABLED=false" in text
    assert "PIONEX_DIRECT_LIVE_TRADING_ENABLED=false" in text
    assert "AI_FAILURE_POLICY=reject_live" in text
