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
_config.WEBHOOK_SECRET = "test-secret-do-not-use"

from app.main import app

client = TestClient(app)


def _sign(payload: str, secret: str = "test-secret-do-not-use") -> str:
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


def test_webhook_signal_invalid_schema():
    """POST with missing required fields returns 422."""
    payload = json.dumps({"symbol": "SOLUSD"})  # missing direction
    headers = {
        "X-Signature": _sign(payload),
        "Content-Type": "application/json",
    }
    response = client.post("/api/webhook/signal", data=payload, headers=headers)
    assert response.status_code == 422
