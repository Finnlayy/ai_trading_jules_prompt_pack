import pytest
import os
import json
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.api.endpoints import router
from app.api.broker import router as broker_router
from fastapi import FastAPI

app = FastAPI()
app.include_router(router, prefix="/webhook")
app.include_router(broker_router, prefix="/broker")
client = TestClient(app)

def test_ui_live_smoke_placeholder():
    """
    Simulate frontend sending signal payload.
    Ensures that the API surface matches what frontend expects for live execution.
    """
    # 1. Fetch broker status to see if live
    status_resp = client.get("/broker/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()

    assert "live_enabled" in status_data
    assert "allowed_symbols" in status_data

    # 2. Pretend UI submitted an order
    payload = {
        "signal_id": "test_ui_1",
        "symbol": "ETH_USDT",
        "timeframe": "1h",
        "direction": "LONG",
        "intent": "ENTRY",
        "account_mode": "SPOT",
        "timestamp": "2024-05-28T12:00:00Z",
        "entry_price": 3500.0,
        "stop_price": 3400.0,
        "target_price": 3800.0,
        "confluence_score": 95.0,
        "crisis_score": 5.0,
        "mc_dispersion": 0.5,
        "spread": 0.1
    }

    # Needs to bypass actual Pionex/AI calls if not mocked here,
    # but the point is testing the structure is intact.
    # Because we're not mocking we should expect a rejection if disabled or simulation if enabled.

    resp = client.post("/webhook/m8", json=payload)
    assert resp.status_code == 200
    resp_data = resp.json()

    assert resp_data["status"] == "success"
    assert "execution_mode" in resp_data["result"]
    assert "broker_result" in resp_data["result"]
