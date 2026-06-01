import pytest
import json
import hashlib
import hmac
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

from app.main import app
from app.services.risk_engine import risk_engine_instance
from app.services.ai_kimi import ai_review_instance
from app.services.journal_logger import journal_logger_instance
from app.api.orchestrator import reset_broker
from app.core.config import WEBHOOK_SECRET


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
            return json.dumps(
                {
                    "schema_version": "1.0",
                    "signal_id": "sig-123",
                    "decision": "PROCEED_TO_SIMULATION",
                    "confidence": 0.95,
                    "reason_codes": [],
                    "risk_flags": [],
                    "reject_reason": None,
                    "requires_human_review": False,
                }
            )
        return "mocked scout response"

    with patch.object(
        ai_review_instance, "_call_llm", new_callable=AsyncMock
    ) as mock_method:
        mock_method.side_effect = mock_call_kimi
        yield mock_method


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_root_serves_frontend():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert "MetricFlow Bot Command Center" in response.text
    assert "Pine Script Studio" not in response.text


@pytest.mark.asyncio
async def test_m8_webhook_valid_payload(mock_kimi_api):
    payload = {
        "signal_id": "sig-123",
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
        "spread": 10.0,
    }

    import app.core.config as config_module
    import app.api.endpoints as endpoints

    original_secret = config_module.WEBHOOK_SECRET
    config_module.WEBHOOK_SECRET = "test-secret-123"
    endpoints.WEBHOOK_SECRET = "test-secret-123"

    try:
        body_bytes = json.dumps(payload).encode("utf-8")
        valid_sig = hmac.new(
            "test-secret-123".encode("utf-8"), body_bytes, hashlib.sha256
        ).hexdigest()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/webhook/m8", content=body_bytes, headers={"x-m8-signature": valid_sig}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["result"]["signal_id"] == "sig-123"
        assert data["result"]["final_decision"] == "EXECUTED_SIM"
        assert (
            data["result"]["ai_trace"]["trace_type"]
            == "ai_reasoning_audit_not_hidden_chain_of_thought"
        )
    finally:
        config_module.WEBHOOK_SECRET = original_secret
        endpoints.WEBHOOK_SECRET = original_secret


@pytest.mark.asyncio
async def test_m8_webhook_invalid_payload():
    payload = {"signal_id": "sig-123", "direction": "INVALID"}
    import app.core.config as config_module
    import app.api.endpoints as endpoints

    original_secret = config_module.WEBHOOK_SECRET
    config_module.WEBHOOK_SECRET = "test-secret-123"
    endpoints.WEBHOOK_SECRET = "test-secret-123"

    try:
        body_bytes = json.dumps(payload).encode("utf-8")
        valid_sig = hmac.new(
            "test-secret-123".encode("utf-8"), body_bytes, hashlib.sha256
        ).hexdigest()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/webhook/m8", content=body_bytes, headers={"x-m8-signature": valid_sig}
            )
        assert response.status_code == 422
    finally:
        config_module.WEBHOOK_SECRET = original_secret
        endpoints.WEBHOOK_SECRET = original_secret


@pytest.mark.asyncio
async def test_m8_webhook_requires_signature_when_secret_configured(mock_kimi_api):
    import app.api.endpoints as endpoints
    import app.core.config as config_module

    original_secret = config_module.WEBHOOK_SECRET
    config_module.WEBHOOK_SECRET = "test-secret-123"
    endpoints.WEBHOOK_SECRET = "test-secret-123"

    try:
        payload = {
            "signal_id": "sig-auth",
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
            "spread": 10.0,
        }
        body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        # Request without signature → 401
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post("/webhook/m8", json=payload)
        assert response.status_code == 401

        # Request with valid signature → 200
        valid_sig = hmac.new(
            "test-secret-123".encode("utf-8"), body_bytes, hashlib.sha256
        ).hexdigest()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/webhook/m8", content=body_bytes, headers={"x-m8-signature": valid_sig}
            )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Request with invalid signature → 401
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/webhook/m8", content=body_bytes, headers={"x-m8-signature": "invalid"}
            )
        assert response.status_code == 401
    finally:
        config_module.WEBHOOK_SECRET = original_secret
        endpoints.WEBHOOK_SECRET = original_secret
