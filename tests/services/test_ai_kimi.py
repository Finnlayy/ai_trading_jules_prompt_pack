import pytest
import json
from unittest.mock import AsyncMock, patch

from app.services.ai_kimi import AIProviderConfig, KimiSwarmService, _resolve_scout_model
from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import DecisionEnum
from app.services.confidence_registry import confidence_registry


def create_valid_payload() -> M8Payload:
    return M8Payload(
        signal_id="sig-001",
        symbol="BTCUSD",
        timeframe="1h",
        direction="LONG",
        timestamp="2026-05-20T10:00:00Z",
        entry_price=50000.0,
        stop_price=48000.0,
        target_price=54000.0,
        confluence_score=85.0,
        crisis_score=10.0,
        mc_dispersion=2.0,
        spread=5.0,
        market_regime="GREEN",
    )


@pytest.fixture(autouse=True)
def reset_confidence_registry():
    confidence_registry.reset_all()
    yield
    confidence_registry.reset_all()


@pytest.mark.asyncio
async def test_kimi_swarm_success():
    service = KimiSwarmService(provider="moonshot")
    payload = create_valid_payload()

    async def mock_call_kimi(scout_name: str, prompt: str, system: str = "", response_format=None):
        if response_format:
            return json.dumps({
                "schema_version": "1.0",
                "signal_id": "sig-001",
                "decision": "PROCEED_TO_SIMULATION",
                "confidence": 0.95,
                "reason_codes": ["STRONG_CONFLUENCE", "LOW_RISK"],
                "risk_flags": [],
                "reject_reason": None,
                "requires_human_review": False,
            })
        return "Confidence: 0.75\nmocked scout response"

    with patch.object(service, "_call_llm_for_scout", new_callable=AsyncMock) as mock_method:
        mock_method.side_effect = mock_call_kimi

        review = await service.review_signal(payload)

        assert review.decision == DecisionEnum.PROCEED_TO_SIMULATION
        assert review.confidence == 0.85
        assert "STRONG_CONFLUENCE" in review.reason_codes
        assert review.audit_trace["trace_type"] == "ai_reasoning_audit_not_hidden_chain_of_thought"
        # 4 scouts + 1 orchestrator
        assert mock_method.call_count == 7
        # Verify all 4 scouts are present
        scouts = review.audit_trace["scouts"]
        assert "technical" in scouts
        assert "sentiment" in scouts
        assert "risk" in scouts
        assert "macro" in scouts
        assert "execution" in scouts
        assert "correlation" in scouts
        # Verify symbol context was injected
        assert "symbol_context" in review.audit_trace
        assert "BTCUSD" in review.audit_trace["symbol_context"]
        # Verify scout weights are tracked
        assert "scout_weights" in review.audit_trace
        assert set(review.audit_trace["scout_weights"].keys()) == {"technical", "sentiment", "risk", "macro", "execution", "correlation"}
        assert "weighted_scout_vote" in review.audit_trace
        assert review.audit_trace["confidence_recorded"] is True
        assert review.audit_trace["weighted_scout_vote"]["decision_hint"] == DecisionEnum.PROCEED_TO_SIMULATION.value


@pytest.mark.asyncio
async def test_kimi_swarm_api_failure_fallback():
    service = KimiSwarmService(provider="moonshot")
    payload = create_valid_payload()

    async def mock_fail(*args, **kwargs):
        raise Exception("API Timeout")

    with patch.object(service, "_call_llm_for_scout", new_callable=AsyncMock) as mock_method:
        mock_method.side_effect = mock_fail

        review = await service.review_signal(payload)

        assert review.decision == DecisionEnum.PROCEED_TO_SIMULATION
        assert "API_FALLBACK" in review.reason_codes
        assert "KIMI_UNAVAILABLE" in review.risk_flags
        assert review.audit_trace["fallback"] is True


@pytest.mark.asyncio
async def test_kimi_swarm_invalid_provider_fallback(monkeypatch):
    from app.core import config

    for scout in KimiSwarmService.SCOUT_NAMES:
        monkeypatch.setattr(config, f"AI_PROVIDER_{scout.upper()}", "")

    service = KimiSwarmService(provider="unknown-provider")
    payload = create_valid_payload()

    review = await service.review_signal(payload)

    assert review.decision == DecisionEnum.PROCEED_TO_SIMULATION
    assert "API_FALLBACK" in review.reason_codes
    assert "AI_PROVIDER_UNAVAILABLE" in review.risk_flags


def test_extract_confidence_from_report():
    service = KimiSwarmService()
    assert service._extract_confidence_from_report("Confidence: 0.82\nSome text") == 0.82
    assert service._extract_confidence_from_report("confidence: 0.33") == 0.33
    assert service._extract_confidence_from_report("No confidence here") == 0.5
    assert service._extract_confidence_from_report("") == 0.5


def test_gemini_scout_model_falls_back_from_non_gemini_override():
    provider_config = AIProviderConfig(
        provider="gemini",
        api_key="test",
        api_key_env="GEMINI_API_KEY",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        model="gemini-2.5-flash",
        unavailable_flag="GEMINI_UNAVAILABLE",
    )

    assert _resolve_scout_model(provider_config, "google/gemma-4-e2b:3") == "gemini-2.5-flash"
    assert _resolve_scout_model(provider_config, "models/gemini-2.5-pro") == "gemini-2.5-pro"


def test_weighted_vote_rejects_low_confidence_reports():
    service = KimiSwarmService(provider="moonshot")
    payload = create_valid_payload()
    reports = {name: "Confidence: 0.40\nReject; critical risk." for name in service.SCOUT_NAMES}

    weighted = service._weighted_scout_vote(payload, reports)

    assert weighted["decision_hint"] == DecisionEnum.REJECT.value
    assert weighted["rejection_score"] > weighted["approval_score"]
