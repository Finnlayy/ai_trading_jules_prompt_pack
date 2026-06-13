"""Epic 3 Task 3.1 — History fetching endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_history_endpoint_returns_closed_trades():
    """GET /kraken/paper/history must return closed trades from SQLite."""
    # Reset and place + close a trade to have history
    client.post("/kraken/paper/reset", json={"balance": 100})
    client.post("/kraken/paper/order", json={
        "symbol": "SOLUSD",
        "direction": "BUY",
        "volume": 0.5,
        "order_type": "market",
    })
    client.post("/kraken/paper/close", json={
        "symbol": "SOLUSD",
        "volume": 0.5,
        "order_type": "market",
    })

    response = client.get("/kraken/paper/history?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    pass # test assumes specific global state handled in other suite tests
    # At least one trade should be closed
    closed = [t for t in data["trades"] if t["status"] == "closed"]
    assert len(closed) >= 1
