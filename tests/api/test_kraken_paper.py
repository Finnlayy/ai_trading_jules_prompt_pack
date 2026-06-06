"""Backend tests for the Kraken Paper Trading broker."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ------------------------------------------------------------------
# Setup & reset
# ------------------------------------------------------------------

def test_paper_reset():
    """POST /kraken/paper/reset should reset the paper account."""
    response = client.post("/kraken/paper/reset", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["balance"] == 50.0  # Default initial balance


def test_paper_reset_custom_balance():
    """POST /kraken/paper/reset with custom balance."""
    response = client.post("/kraken/paper/reset", json={"balance": 100.0})
    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == 100.0


# ------------------------------------------------------------------
# Status & balance
# ------------------------------------------------------------------

def test_paper_status():
    """GET /kraken/paper/status returns broker health and balance."""
    client.post("/kraken/paper/reset", json={})
    response = client.get("/kraken/paper/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["broker"]["name"] == "KrakenPaperBroker"
    assert data["broker"]["mode"] == "paper"
    assert "balance" in data


def test_paper_balance():
    """GET /kraken/paper/balance returns paper balance."""
    client.post("/kraken/paper/reset", json={})
    response = client.get("/kraken/paper/balance")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["currency"] == "USD"
    assert data["balance"] == 50.0
    assert data["equity"] == 50.0
    assert data["open_positions"] == 0


# ------------------------------------------------------------------
# Order placement
# ------------------------------------------------------------------

def test_paper_buy_order():
    """POST /kraken/paper/order BUY creates a paper position."""
    client.post("/kraken/paper/reset", json={})
    response = client.post("/kraken/paper/order", json={
        "symbol": "SOLUSD",
        "direction": "BUY",
        "volume": 0.5,
        "order_type": "market",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["symbol"] == "SOLUSD"
    assert data["direction"] == "LONG"
    assert data["volume"] == 0.5
    assert data["fill_price"] > 0
    assert data["fee"] > 0
    assert data["mode"] == "paper"
    assert data["balance_after"] < 50.0


def test_paper_sell_without_position():
    """POST /kraken/paper/order SELL without open position returns error."""
    client.post("/kraken/paper/reset", json={})
    response = client.post("/kraken/paper/order", json={
        "symbol": "SOLUSD",
        "direction": "SELL",
        "volume": 0.5,
        "order_type": "market",
    })
    assert response.status_code == 400
    data = response.json()
    assert "Insufficient" in data["detail"]


def test_paper_buy_insufficient_balance():
    """POST /kraken/paper/order BUY with more than balance returns error."""
    client.post("/kraken/paper/reset", json={"balance": 5.0})
    response = client.post("/kraken/paper/order", json={
        "symbol": "BTCUSD",
        "direction": "BUY",
        "volume": 1.0,
        "order_type": "market",
    })
    assert response.status_code == 400
    data = response.json()
    assert "Insufficient" in data["detail"]


def test_paper_order_invalid_direction():
    """POST /kraken/paper/order with invalid direction returns 422."""
    response = client.post("/kraken/paper/order", json={
        "symbol": "SOLUSD",
        "direction": "HODL",
        "volume": 0.5,
        "order_type": "market",
    })
    assert response.status_code == 422


def test_paper_order_zero_volume():
    """POST /kraken/paper/order with zero volume returns 422."""
    response = client.post("/kraken/paper/order", json={
        "symbol": "SOLUSD",
        "direction": "BUY",
        "volume": 0,
        "order_type": "market",
    })
    assert response.status_code == 422


# ------------------------------------------------------------------
# Position closing
# ------------------------------------------------------------------

def test_paper_close_position():
    """POST /kraken/paper/close closes an open position."""
    client.post("/kraken/paper/reset", json={})
    # Buy first
    client.post("/kraken/paper/order", json={
        "symbol": "SOLUSD",
        "direction": "BUY",
        "volume": 0.5,
        "order_type": "market",
    })
    # Then close
    response = client.post("/kraken/paper/close", json={
        "symbol": "SOLUSD",
        "volume": 0.5,
        "order_type": "market",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["symbol"] == "SOLUSD"
    assert "pnl" in data
    assert data["position_remaining"] == 0.0


def test_paper_close_without_position():
    """POST /kraken/paper/close without open position returns error."""
    client.post("/kraken/paper/reset", json={})
    response = client.post("/kraken/paper/close", json={
        "symbol": "SOLUSD",
        "volume": 0.5,
        "order_type": "market",
    })
    assert response.status_code == 400
    data = response.json()
    assert "No open position" in data["detail"]


# ------------------------------------------------------------------
# History
# ------------------------------------------------------------------

def test_paper_history():
    """GET /kraken/paper/history returns trade history."""
    client.post("/kraken/paper/reset", json={})
    client.post("/kraken/paper/order", json={
        "symbol": "SOLUSD",
        "direction": "BUY",
        "volume": 0.5,
        "order_type": "market",
    })
    response = client.get("/kraken/paper/history?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["count"] >= 1
    assert "trades" in data
    assert data["trades"][0]["symbol"] == "SOLUSD"


# ------------------------------------------------------------------
# Full round-trip
# ------------------------------------------------------------------

def test_paper_full_round_trip():
    """Buy, check position, close, verify balance changed."""
    client.post("/kraken/paper/reset", json={"balance": 100.0})

    # Buy
    r1 = client.post("/kraken/paper/order", json={
        "symbol": "SOLUSD",
        "direction": "BUY",
        "volume": 0.5,
        "order_type": "market",
    })
    assert r1.status_code == 200
    buy_data = r1.json()
    balance_after_buy = buy_data["balance_after"]
    assert balance_after_buy < 100.0

    # Check position
    r2 = client.get("/kraken/paper/positions")
    assert r2.status_code == 200
    pos_data = r2.json()
    assert pos_data["count"] == 1
    assert pos_data["positions"][0]["symbol"] == "SOLUSD"

    # Close
    r3 = client.post("/kraken/paper/close", json={
        "symbol": "SOLUSD",
        "volume": 0.5,
        "order_type": "market",
    })
    assert r3.status_code == 200
    close_data = r3.json()

    # Verify history has 2 trades
    r4 = client.get("/kraken/paper/history?limit=10")
    hist = r4.json()
    assert hist["count"] >= 2

    # Balance should be different (fees deducted)
    r5 = client.get("/kraken/paper/balance")
    bal = r5.json()
    assert bal["balance"] != 100.0  # Fees changed balance
    assert bal["total_pnl"] != 0.0  # P&L tracked
