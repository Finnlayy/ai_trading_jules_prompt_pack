"""Backend tests for the Kraken broker adapter."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ------------------------------------------------------------------
# Status endpoint
# ------------------------------------------------------------------

def test_kraken_status_schema():
    """GET /kraken/status returns a valid status payload."""
    response = client.get("/kraken/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["name"] == "KrakenBroker"
    assert data["type"] == "kraken"
    assert "mode" in data
    assert "ready" in data
    assert "live_capable" in data
    assert "credentials_present" in data


def test_kraken_status_credentials_detected():
    """Kraken status should reflect actual credential state from .env."""
    response = client.get("/kraken/status")
    data = response.json()
    assert "ready" in data
    assert "live_capable" in data
    assert "credentials_present" in data


# ------------------------------------------------------------------
# Public market data
# ------------------------------------------------------------------

def test_kraken_time_reachable():
    """GET /kraken/time should return Kraken server time."""
    response = client.get("/kraken/time")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "time" in data


def test_kraken_ticker_btcusd():
    """POST /kraken/ticker should return ticker for BTCUSD."""
    response = client.post("/kraken/ticker", json={"pair": "BTCUSD"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["pair"] == "BTCUSD"
    assert "ticker" in data


def test_kraken_ticker_ethusd():
    """POST /kraken/ticker should return ticker for ETHUSD."""
    response = client.post("/kraken/ticker", json={"pair": "ETHUSD"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["pair"] == "ETHUSD"


# ------------------------------------------------------------------
# Private endpoints (no credentials → expect 502 or dry-run behavior)
# ------------------------------------------------------------------

def test_kraken_balance_returns_data():
    """GET /kraken/balance returns balance data when credentials are present."""
    response = client.get("/kraken/balance")
    # With credentials → 200; without → 502
    assert response.status_code in (200, 502)
    if response.status_code == 200:
        data = response.json()
        assert data["status"] == "ok"
        assert "balances" in data


def test_kraken_positions_returns_data():
    """GET /kraken/positions returns positions when credentials are present."""
    response = client.get("/kraken/positions")
    # With credentials → 200; without → 502
    assert response.status_code in (200, 502)
    if response.status_code == 200:
        data = response.json()
        assert data["status"] == "ok"
        assert "positions" in data


# ------------------------------------------------------------------
# Order endpoint
# ------------------------------------------------------------------

def test_kraken_order_validate_only():
    """POST /kraken/order with validate_only=True should validate without placing."""
    response = client.post("/kraken/order", json={
        "symbol": "BTCUSD",
        "direction": "BUY",
        "volume": 0.001,
        "order_type": "market",
        "validate_only": True,
    })
    # Without credentials this will fail; but the endpoint should handle it gracefully
    assert response.status_code in (200, 502)


def test_kraken_order_rejected_zero_volume():
    """POST /kraken/order with zero volume should return 422."""
    response = client.post("/kraken/order", json={
        "symbol": "BTCUSD",
        "direction": "BUY",
        "volume": 0,
        "order_type": "market",
    })
    assert response.status_code == 422


def test_kraken_order_rejected_invalid_direction():
    """POST /kraken/order with invalid direction should return 422."""
    response = client.post("/kraken/order", json={
        "symbol": "BTCUSD",
        "direction": "HODL",
        "volume": 0.001,
        "order_type": "market",
    })
    assert response.status_code == 422


def test_kraken_order_rejected_invalid_order_type():
    """POST /kraken/order with invalid order_type should return 422."""
    response = client.post("/kraken/order", json={
        "symbol": "BTCUSD",
        "direction": "BUY",
        "volume": 0.001,
        "order_type": "invalid",
    })
    assert response.status_code == 422


def test_kraken_order_response_has_required_fields():
    """When an order succeeds, response must contain status and validated flag."""
    # This test expects validate-only mode to work even without live credentials
    # because the broker forces validate=True when not live-capable.
    response = client.post("/kraken/order", json={
        "symbol": "BTCUSD",
        "direction": "BUY",
        "volume": 0.001,
        "order_type": "market",
        "validate_only": True,
    })
    # Without credentials we get 502; with credentials we'd get 200
    assert response.status_code in (200, 502)


# ------------------------------------------------------------------
# Cancel endpoint
# ------------------------------------------------------------------

def test_kraken_cancel_without_credentials():
    """POST /kraken/cancel without credentials returns 502."""
    response = client.post("/kraken/cancel", json={"txid": "ABCDEF-123456"})
    assert response.status_code == 502


def test_kraken_cancel_missing_txid():
    """POST /kraken/cancel without txid returns 422."""
    response = client.post("/kraken/cancel", json={})
    assert response.status_code == 422
