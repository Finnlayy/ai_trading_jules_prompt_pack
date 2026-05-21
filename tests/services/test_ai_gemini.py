import pytest
import json
from unittest.mock import AsyncMock, patch

from app.services.ai_gemini import GeminiSwarmService
from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import DecisionEnum

def create_valid_payload() -> M8Payload:
    return M8Payload(
        signal_id="sig-gemini-001",
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
        spread=5.0
    )

@pytest.mark.asyncio
async def test_gemini_swarm_success():
    service = GeminiSwarmService()
    payload = create_valid_payload()

    # Mock the underlying _call_gemini method to avoid real API calls
    async def mock_call_gemini(prompt: str, system: str = "", response_mime_type: str = "text/plain"):
        if response_mime_type == "application/json":
            # It's the orchestrator call
            return json.dumps({
                "schema_version": "1.0",
                "signal_id": "sig-gemini-001",
                "decision": "PROCEED_TO_SIMULATION",
                "confidence": 0.98,
                "reason_codes": ["GEMINI_STRONG_CONFLUENCE"],
                "risk_flags": [],
                "reject_reason": None,
                "requires_human_review": False
            })
        return "mocked scout response"

    with patch.object(service, '_call_gemini', new_callable=AsyncMock) as mock_method:
        mock_method.side_effect = mock_call_gemini

        review = await service.review_signal(payload)

        assert review.decision == DecisionEnum.PROCEED_TO_SIMULATION
        assert review.confidence == 0.98
        assert "GEMINI_STRONG_CONFLUENCE" in review.reason_codes
        assert mock_method.call_count == 4 # 3 scouts + 1 orchestrator

@pytest.mark.asyncio
async def test_gemini_swarm_api_failure_fallback():
    service = GeminiSwarmService()
    payload = create_valid_payload()

    async def mock_fail(*args, **kwargs):
        raise Exception("API Timeout")

    with patch.object(service, '_call_gemini', new_callable=AsyncMock) as mock_method:
        mock_method.side_effect = mock_fail

        review = await service.review_signal(payload)

        # Fallback should trigger PROCEED_TO_SIMULATION but log API_FALLBACK
        assert review.decision == DecisionEnum.PROCEED_TO_SIMULATION
        assert "API_FALLBACK" in review.reason_codes
        assert "GEMINI_UNAVAILABLE" in review.risk_flags
