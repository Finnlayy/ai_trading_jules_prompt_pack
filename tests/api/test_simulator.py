import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.simulator import router

app = FastAPI()
app.include_router(router)

client = TestClient(app)

def test_get_orderbook_handles_exceptions(monkeypatch):
    async def mock_fetch_snapshot(*args, **kwargs):
        raise Exception("Secret key leaked!")

    from app.services.orderbook_simulator import orderbook_simulator
    monkeypatch.setattr(orderbook_simulator, "fetch_snapshot", mock_fetch_snapshot)

    resp = client.get("/orderbook/binance/BTCUSDT")
    assert resp.status_code == 500
    assert "Secret key" not in resp.text
    assert "internal server error" in resp.text.lower()

def test_quote_fill_handles_exceptions(monkeypatch):
    async def mock_fetch_snapshot(*args, **kwargs):
        raise Exception("Database password exposed!")

    from app.services.orderbook_simulator import orderbook_simulator
    monkeypatch.setattr(orderbook_simulator, "fetch_snapshot", mock_fetch_snapshot)

    payload = {
        "venue": "binance",
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "size": 1.5
    }
    resp = client.post("/quote-fill", json=payload)
    assert resp.status_code == 500
    assert "Database password" not in resp.text
    assert "internal server error" in resp.text.lower()
