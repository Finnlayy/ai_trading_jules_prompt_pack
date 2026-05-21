import pytest
import json
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from app.main import app
from app.services.risk_engine import risk_engine_instance
from app.services.ai_kimi import ai_review_instance
from app.services.journal_logger import journal_logger_instance

@pytest.fixture(autouse=True)
def reset_state(tmp_path):
    risk_engine_instance.trades_today = 0
    risk_engine_instance.last_trade_bar = -1
    risk_engine_instance.current_bar = 0
    previous_journal_path = journal_logger_instance.filepath
    journal_logger_instance.filepath = str(tmp_path / "trade_journal.jsonl")
    yield
    journal_logger_instance.filepath = previous_journal_path

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
