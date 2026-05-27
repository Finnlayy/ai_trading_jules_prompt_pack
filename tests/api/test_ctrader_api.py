from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.ctrader import router as ctrader_router
from app.api.live_trading import router as live_router


def _test_app():
    test_app = FastAPI()
    test_app.include_router(ctrader_router, prefix="/ctrader")
    test_app.include_router(live_router, prefix="/live")
    return test_app


class FakeCTraderBroker:
    def __init__(self):
        self.connected = False
        self.disconnected = False

    def get_broker_type(self):
        return "ctrader"

    def health(self):
        return {
            "name": "CTrader",
            "type": "ctrader",
            "mode": "dry-run",
            "ready": True,
            "live_capable": False,
            "enabled": True,
            "live_trading_enabled": False,
            "account_id": 12345,
            "host": "demo.ctraderapi.com",
            "port": 5035,
            "symbols_cached": 1,
            "connection": {
                "connected": self.connected,
                "app_authenticated": self.connected,
                "account_authenticated": self.connected,
                "host": "demo.ctraderapi.com",
                "port": 5035,
                "last_error": None,
                "last_connected_at": None,
            },
        }

    def get_symbols(self):
        return {"EURUSD": 1}

    def refresh_symbols(self):
        return {"EURUSD": 1, "GBPUSD": 2}

    def get_positions(self):
        return {
            "status": "ok",
            "positions": [
                {
                    "trade_id": "ctrader-position-1",
                    "symbol": "EURUSD",
                    "direction": "LONG",
                    "entry_price": 1.1,
                    "current_price": 1.101,
                    "size": 1000.0,
                    "unrealized_pnl": 1.0,
                    "unrealized_pnl_pct": 0.1,
                    "open_time": datetime.now(timezone.utc),
                    "strategy_id": "metricflow-test",
                    "stop_price": 1.095,
                    "target_price": 1.11,
                    "time_in_trade_minutes": 1.0,
                }
            ],
        }

    def get_wallet_balances(self, account_mode="CTRADER"):
        return {
            "status": "ok",
            "account_mode": account_mode,
            "account_id": 12345,
            "currency": "ACCOUNT",
            "balance": 1000.0,
            "equity": 1000.0,
            "used_margin": 10.0,
            "free_margin": 990.0,
            "raw": {},
        }

    def connect(self):
        self.connected = True
        return self.health()

    def disconnect(self):
        self.disconnected = True
        self.connected = False
        return self.health()


@pytest.fixture(autouse=True)
def fake_ctrader_router_broker(monkeypatch):
    import app.api.ctrader as ctrader_api

    fake = FakeCTraderBroker()
    monkeypatch.setattr(ctrader_api, "_ctrader_broker_instance", fake)
    yield fake
    monkeypatch.setattr(ctrader_api, "_ctrader_broker_instance", None)


@pytest.mark.asyncio
async def test_ctrader_status_endpoint():
    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.get("/ctrader/status")

    assert response.status_code == 200
    assert response.json()["name"] == "CTrader"


@pytest.mark.asyncio
async def test_ctrader_symbols_endpoint():
    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.get("/ctrader/symbols")

    assert response.status_code == 200
    assert response.json()["symbols"]["EURUSD"] == 1


@pytest.mark.asyncio
async def test_ctrader_refresh_symbols_endpoint():
    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.post("/ctrader/symbols/refresh")

    assert response.status_code == 200
    assert response.json()["count"] == 2


@pytest.mark.asyncio
async def test_ctrader_positions_endpoint():
    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.get("/ctrader/positions")

    assert response.status_code == 200
    assert response.json()["positions"][0]["symbol"] == "EURUSD"


@pytest.mark.asyncio
async def test_ctrader_balance_endpoint():
    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.get("/ctrader/balance")

    assert response.status_code == 200
    assert response.json()["free_margin"] == 990.0


@pytest.mark.asyncio
async def test_ctrader_connect_and_disconnect_endpoints(fake_ctrader_router_broker):
    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        connect = await ac.post("/ctrader/connect")
        disconnect = await ac.post("/ctrader/disconnect")

    assert connect.status_code == 200
    assert connect.json()["health"]["connection"]["connected"] is True
    assert disconnect.status_code == 200
    assert fake_ctrader_router_broker.disconnected is True


@pytest.mark.asyncio
async def test_live_status_marks_ctrader_active(monkeypatch):
    import app.api.live_trading as live_trading

    monkeypatch.setattr(live_trading, "BROKER_MODE", "ctrader")

    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.get("/live/status")

    assert response.status_code == 200
    assert response.json()["is_active"] is True


@pytest.mark.asyncio
async def test_live_positions_uses_ctrader_broker_first(monkeypatch):
    import app.api.live_trading as live_trading
    import app.api.orchestrator as orchestrator

    fake = FakeCTraderBroker()
    monkeypatch.setattr(live_trading, "BROKER_MODE", "ctrader")
    monkeypatch.setattr(orchestrator, "broker_instance", fake)

    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.get("/live/positions")

    assert response.status_code == 200
    assert response.json()[0]["symbol"] == "EURUSD"
