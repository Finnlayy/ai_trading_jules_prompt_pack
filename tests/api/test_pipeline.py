import pytest
import json
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from app.main import app
from app.services.risk_engine import risk_engine_instance
from app.services.ai_kimi import ai_review_instance
from app.services.journal_logger import journal_logger_instance
from app.api import orchestrator
from app.api.orchestrator import reset_broker
from app.schemas.ai_review import SignalReview
from app.services.broker import SimulationBroker

@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    risk_engine_instance.trades_today = 0
    risk_engine_instance.last_trade_bar = -1
    risk_engine_instance.current_bar = 0
    previous_journal_path = journal_logger_instance.filepath
    journal_logger_instance.filepath = str(tmp_path / "trade_journal.jsonl")
    reset_broker()
    yield
    journal_logger_instance.filepath = previous_journal_path
    reset_broker()

@pytest.fixture
def mock_kimi_api():
    async def mock_call_kimi(prompt: str, system: str = "", response_format=None):
        if response_format:
            # Basic approval mock
            return json.dumps({
                "schema_version": "1.0",
                "signal_id": "sig-pipe",
                "decision": "PROCEED_TO_SIMULATION",
                "confidence": 0.95,
                "reason_codes": [],
                "risk_flags": [],
                "reject_reason": None,
                "requires_human_review": False
            })
        return "mocked scout response"
        
    with patch.object(ai_review_instance, '_call_kimi', new_callable=AsyncMock) as mock_method:
        mock_method.side_effect = mock_call_kimi
        yield mock_method

@pytest.fixture
def mock_kimi_api_reject():
    async def mock_call_kimi(prompt: str, system: str = "", response_format=None):
        if response_format:
            # Mocking AI returning a reject decision due to high crisis score
            return json.dumps({
                "schema_version": "1.0",
                "signal_id": "sig-pipe-2",
                "decision": "REJECT",
                "confidence": 0.95,
                "reason_codes": ["AI_REJECT"],
                "risk_flags": [],
                "reject_reason": "High risk detected",
                "requires_human_review": False
            })
        return "mocked scout response"
        
    with patch.object(ai_review_instance, '_call_kimi', new_callable=AsyncMock) as mock_method:
        mock_method.side_effect = mock_call_kimi
        yield mock_method


@pytest.mark.asyncio
async def test_full_pipeline_proceed(mock_kimi_api):
    payload = {
        "signal_id": "sig-pipe-1",
        "symbol": "BTCUSD",
        "timeframe": "1h",
        "direction": "LONG",
        "timestamp": "2026-05-20T10:00:00Z",
        "entry_price": 50000.0,
        "stop_price": 48000.0,
        "target_price": 54000.0,
        "confluence_score": 85.5,
        "crisis_score": 10.0,
        "mc_dispersion": 1.5,
        "spread": 10.0
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/webhook/m8", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["result"]["signal_id"] == "sig-pipe-1"
    assert data["result"]["final_decision"] == "EXECUTED_SIM"
    assert data["result"]["reject_reason"] is None

@pytest.mark.asyncio
async def test_full_pipeline_reject(mock_kimi_api_reject):
    payload = {
        "signal_id": "sig-pipe-2",
        "symbol": "BTCUSD",
        "timeframe": "1h",
        "direction": "LONG",
        "timestamp": "2026-05-20T10:00:00Z",
        "entry_price": 50000.0,
        "stop_price": 48000.0,
        "target_price": 54000.0,
        "confluence_score": 85.5,
        "crisis_score": 35.0, # High crisis score triggers Risk Engine reject, also mocked to trigger AI Reject
        "mc_dispersion": 1.5,
        "spread": 10.0
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/webhook/m8", json=payload)
        
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["result"]["final_decision"] == "REJECTED"
    # Even if AI rejected it, it might trigger HIGH_CRISIS deterministic reject first, or AI_REJECT
    assert data["result"]["reject_reason"] in ["HIGH_CRISIS", "AI_REJECT"]


@pytest.mark.asyncio
async def test_ai_unavailable_rejects_in_live_capable_mode(tmp_path):
    previous_policy = orchestrator.AI_FAILURE_POLICY
    previous_broker = orchestrator.broker_instance

    broker = SimulationBroker()
    setattr(broker, "is_live_capable", lambda: True)
    orchestrator.broker_instance = broker
    orchestrator.AI_FAILURE_POLICY = "reject_live"

    try:
        async def fake_review(_payload):
            return SignalReview(
                schema_version="1.0",
                signal_id="sig-live-block",
                decision="PROCEED_TO_SIMULATION",
                confidence=0.6,
                reason_codes=["fallback"],
                risk_flags=["OPENAI_UNAVAILABLE"],
                reject_reason=None,
                requires_human_review=False,
            )

        with patch.object(ai_review_instance, "review_signal", new=AsyncMock(side_effect=fake_review)):
            payload = {
                "signal_id": "sig-live-block",
                "symbol": "BTCUSD",
                "timeframe": "1h",
                "direction": "LONG",
                "timestamp": "2026-05-20T10:00:00Z",
                "entry_price": 50000.0,
                "stop_price": 48000.0,
                "target_price": 54000.0,
                "confluence_score": 85.0,
                "crisis_score": 10.0,
                "mc_dispersion": 1.5,
                "spread": 8.0,
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post("/webhook/m8", json=payload)

        data = response.json()
        assert data["result"]["final_decision"] == "REJECTED"
        assert data["result"]["reject_reason"] == "AI_PROVIDER_UNAVAILABLE_LIVE_BLOCK"
    finally:
        orchestrator.AI_FAILURE_POLICY = previous_policy
        orchestrator.broker_instance = previous_broker


@pytest.mark.asyncio
async def test_ai_unavailable_can_proceed_when_policy_allows_live():
    previous_policy = orchestrator.AI_FAILURE_POLICY
    previous_broker = orchestrator.broker_instance

    broker = SimulationBroker()
    setattr(broker, "is_live_capable", lambda: True)
    orchestrator.broker_instance = broker
    orchestrator.AI_FAILURE_POLICY = "allow_live"

    try:
        async def fake_review(_payload):
            return SignalReview(
                schema_version="1.0",
                signal_id="sig-live-allow",
                decision="PROCEED_TO_SIMULATION",
                confidence=0.6,
                reason_codes=["fallback"],
                risk_flags=["OPENAI_UNAVAILABLE"],
                reject_reason=None,
                requires_human_review=False,
            )

        with patch.object(ai_review_instance, "review_signal", new=AsyncMock(side_effect=fake_review)):
            payload = {
                "signal_id": "sig-live-allow",
                "symbol": "BTCUSD",
                "timeframe": "1h",
                "direction": "LONG",
                "timestamp": "2026-05-20T10:00:00Z",
                "entry_price": 50000.0,
                "stop_price": 48000.0,
                "target_price": 54000.0,
                "confluence_score": 85.0,
                "crisis_score": 10.0,
                "mc_dispersion": 1.5,
                "spread": 8.0,
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post("/webhook/m8", json=payload)

        data = response.json()
        assert data["result"]["final_decision"] == "EXECUTED_SIM"
    finally:
        orchestrator.AI_FAILURE_POLICY = previous_policy
        orchestrator.broker_instance = previous_broker


@pytest.mark.asyncio
async def test_pipeline_supports_sync_ai_review():
    def fake_sync_review(_payload):
        return SignalReview(
            schema_version="1.0",
            signal_id="sig-sync-ai",
            decision="PROCEED_TO_SIMULATION",
            confidence=0.8,
            reason_codes=["SYNC_REVIEW"],
            risk_flags=[],
            reject_reason=None,
            requires_human_review=False,
        )

    with patch.object(ai_review_instance, "review_signal", new=fake_sync_review):
        payload = {
            "signal_id": "sig-sync-ai",
            "symbol": "BTCUSD",
            "timeframe": "1h",
            "direction": "LONG",
            "timestamp": "2026-05-20T10:00:00Z",
            "entry_price": 50000.0,
            "stop_price": 48000.0,
            "target_price": 54000.0,
            "confluence_score": 85.0,
            "crisis_score": 10.0,
            "mc_dispersion": 1.5,
            "spread": 8.0,
        }
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/webhook/m8", json=payload)

    data = response.json()
    assert data["status"] == "success"
    assert data["result"]["final_decision"] == "EXECUTED_SIM"
