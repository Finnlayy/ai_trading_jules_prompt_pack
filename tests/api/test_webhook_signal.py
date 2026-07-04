"""Epic 2 Task 2.1 — Webhook endpoint for trading signals.

Tests HMAC-SHA256 signature validation and Pydantic schema enforcement
for POST /api/webhook/signal.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient

# Patch config BEFORE importing app
import app.core.config as _config

from app.main import app

client = TestClient(app)
WEBHOOK_TEST_SECRET = "test-secret-do-not-use"


@pytest.fixture(autouse=True)
def signed_webhook_secret(reset_webhook_secret_config):
    _config.WEBHOOK_SECRET = WEBHOOK_TEST_SECRET
    yield


def _sign(payload: str, secret: str = WEBHOOK_TEST_SECRET) -> str:
    """Generate HMAC-SHA256 hex signature."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def test_webhook_signal_valid_payload():
    """POST /api/webhook/signal with valid signed payload returns 200."""
    payload = json.dumps({
        "symbol": "SOLUSD",
        "direction": "BUY",
        "price": 81.50,
        "volume": 0.5,
        "timestamp": "2026-05-29T22:00:00Z",
    })
    headers = {
        "X-Signature": _sign(payload),
        "Content-Type": "application/json",
    }
    response = client.post("/api/webhook/signal", data=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "signal_id" in data


def test_webhook_signal_invalid_signature():
    """POST with wrong signature returns 401."""
    payload = json.dumps({"symbol": "SOLUSD", "direction": "BUY"})
    headers = {
        "X-Signature": "invalid-signature",
        "Content-Type": "application/json",
    }
    response = client.post("/api/webhook/signal", data=payload, headers=headers)
    assert response.status_code == 401


def test_webhook_signal_missing_signature():
    """POST without signature header returns 401 when WEBHOOK_SECRET is set."""
    payload = json.dumps({"symbol": "SOLUSD", "direction": "BUY"})
    response = client.post(
        "/api/webhook/signal",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401


def test_signal_sanity_check_rejects_negative_price():
    """Negative prices must be rejected as invalid."""
    payload = json.dumps({"symbol": "SOLUSD", "direction": "BUY", "price": -10})
    headers = {"X-Signature": _sign(payload), "Content-Type": "application/json"}
    response = client.post("/api/webhook/signal", data=payload, headers=headers)
    assert response.status_code == 422


def test_signal_sanity_check_rejects_insane_volume():
    """Volume above 1000 is rejected as suspicious."""
    payload = json.dumps({"symbol": "SOLUSD", "direction": "BUY", "volume": 9999})
    headers = {"X-Signature": _sign(payload), "Content-Type": "application/json"}
    response = client.post("/api/webhook/signal", data=payload, headers=headers)
    assert response.status_code == 422


def test_signal_queued_for_async_execution():
    """After accepting a signal, it must be queued for the async loop."""
    payload = json.dumps({
        "symbol": "SOLUSD",
        "direction": "BUY",
        "price": 81.50,
        "volume": 0.5,
    })
    headers = {"X-Signature": _sign(payload), "Content-Type": "application/json"}
    response = client.post("/api/webhook/signal", data=payload, headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    # The signal must be findable in the pending queue
    assert "queued" in data.get("message", "").lower(), \
        "Signal was not queued for async execution"


def test_webhook_signal_invalid_schema():
    """POST with missing required fields returns 422."""
    payload = json.dumps({"symbol": "SOLUSD"})  # missing direction
    headers = {
        "X-Signature": _sign(payload),
        "Content-Type": "application/json",
    }
    response = client.post("/api/webhook/signal", data=payload, headers=headers)
    assert response.status_code == 422

def test_webhook_signal_malformed_json():
    """POST with malformed/non-JSON payload returns 422."""
    payload = "this is not a valid json string {"
    headers = {
        "X-Signature": _sign(payload),
        "Content-Type": "application/json",
    }
    response = client.post("/api/webhook/signal", data=payload, headers=headers)
    assert response.status_code == 422
