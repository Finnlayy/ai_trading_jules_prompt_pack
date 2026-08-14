import pytest
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.endpoints import router
import hashlib
import hmac
from datetime import datetime, timezone

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_m8_payload_exception_hiding(monkeypatch):
    import app.api.endpoints

    # Mock to simulate an exception with sensitive internal details
    async def mock_process_signal(payload):
        raise ValueError("Database connection failed. Password 'secret' rejected for user 'root'")

    monkeypatch.setattr(app.api.endpoints, "process_signal", mock_process_signal)

    # Valid payload to bypass validation
    payload = {
        "signal_id": "test",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "direction": "LONG",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "entry_price": 50000.0,
        "stop_price": 49000.0,
        "target_price": 52000.0,
        "confluence_score": 85.5,
        "crisis_score": 10.0,
        "mc_dispersion": 0.5,
        "spread": 0.1
    }

    # Needs valid signature if secret is set, or bypass
    monkeypatch.setattr("app.api.endpoints.WEBHOOK_SECRET", None)

    response = client.post("/m8", json=payload)

    # After the fix, the endpoint should return 500 and a generic error
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error processing payload"}
    assert "Database connection failed" not in response.text
