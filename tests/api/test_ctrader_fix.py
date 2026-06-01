"""Tests for cTrader FIX API endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.ctrader_fix import router as fix_router


def _test_app():
    test_app = FastAPI()
    test_app.include_router(fix_router, prefix="/ctrader-fix")
    return test_app


class FakeFixClient:
    def __init__(self):
        self.connected = False
        self.logged_on = False
        self.orders = []

    def connect(self, timeout=10.0):
        self.connected = True
        self.logged_on = True
        return {"status": "connected"}

    def disconnect(self):
        self.connected = False
        self.logged_on = False
        return {"status": "disconnected"}

    def status(self):
        return {
            "connected": self.connected,
            "logged_on": self.logged_on,
            "host": "demo-uk-eqx-01.p.c-trader.com",
            "port": 5212,
            "last_error": None,
        }

    def send_market_order(self, symbol, side, qty, cl_ord_id, **kwargs):
        self.orders.append({"symbol": symbol, "side": side, "qty": qty, "cl_ord_id": cl_ord_id})
        return {
            "status": "FILLED",
            "cl_ord_id": cl_ord_id,
            "order_id": "order-1",
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": "1.1000",
        }


@pytest.fixture(autouse=True)
def fake_fix_broker(monkeypatch):
    import app.api.ctrader_fix as fix_api
    from app.services.ctrader_fix_broker import CTraderFixBroker, CTraderFixConfig

    config = CTraderFixConfig(enabled=True, sender_comp_id="demo.test", password="test")
    fake_client = FakeFixClient()
    fake_broker = CTraderFixBroker(config=config, client=fake_client)
    monkeypatch.setattr(fix_api, "_fix_broker_instance", fake_broker)
    yield fake_broker
    monkeypatch.setattr(fix_api, "_fix_broker_instance", None)


@pytest.mark.asyncio
async def test_fix_status_endpoint():
    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.get("/ctrader-fix/status")

    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "ctrader_fix"
    assert data["name"] == "CTrader FIX"


@pytest.mark.asyncio
async def test_fix_order_endpoint(fake_fix_broker):
    fake_fix_broker.config.live_trading_enabled = True

    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.post("/ctrader-fix/order", json={
            "symbol": "EURUSD",
            "direction": "BUY",
            "volume_lots": 0.01,
        })

    assert response.status_code == 200, f"Unexpected: {response.status_code} {response.text[:200]}"
    data = response.json()
    assert data["status"] == "FILLED"
    assert data["symbol"] == "EURUSD"
    assert data["direction"] == "BUY"


@pytest.mark.asyncio
async def test_fix_order_dry_run_when_live_trading_disabled(fake_fix_broker):
    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.post("/ctrader-fix/order", json={
            "symbol": "EURUSD",
            "direction": "BUY",
            "volume_lots": 0.01,
        })

    assert response.status_code == 200, f"Unexpected: {response.status_code} {response.text[:200]}"
    data = response.json()
    assert data["status"] == "DRY_RUN_CTRADER_FIX"
    assert data["symbol"] == "EURUSD"
    assert fake_fix_broker.client.orders == []


@pytest.mark.asyncio
async def test_fix_order_rejected_zero_volume():
    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.post("/ctrader-fix/order", json={
            "symbol": "EURUSD",
            "direction": "BUY",
            "volume_lots": 0,
        })

    assert response.status_code == 422, f"Expected 422, got {response.status_code}"
