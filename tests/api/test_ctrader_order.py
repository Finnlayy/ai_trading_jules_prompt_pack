"""RED/GREEN tests for POST /ctrader/order — cTrader direct order execution."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.ctrader import router as ctrader_router


def _test_app():
    test_app = FastAPI()
    test_app.include_router(ctrader_router, prefix="/ctrader")
    return test_app


class FakeCTraderBrokerWithOrder:
    def __init__(self, enabled=True, live=False):
        self.enabled = enabled
        self.live = live
        self.orders = []
        self.margin_check_results = []

    def get_broker_type(self):
        return "ctrader"

    def health(self):
        return {
            "name": "CTrader",
            "type": "ctrader",
            "mode": "live" if self.live else "dry-run",
            "ready": self.enabled,
            "live_capable": self.live,
            "enabled": self.enabled,
            "live_trading_enabled": self.live,
            "account_id": 12345,
            "host": "demo.ctraderapi.com",
            "port": 5035,
            "symbols_cached": 2,
            "connection": {
                "connected": True,
                "app_authenticated": True,
                "account_authenticated": True,
                "host": "demo.ctraderapi.com",
                "port": 5035,
                "last_error": None,
                "last_connected_at": None,
            },
        }

    def get_symbols(self):
        return {"EURUSD": 1, "GBPUSD": 2}

    def get_wallet_balances(self, account_mode="CTRADER"):
        return {
            "status": "ok",
            "account_mode": account_mode,
            "account_id": 12345,
            "currency": "ACCOUNT",
            "balance": 10000.0,
            "equity": 10000.0,
            "used_margin": 100.0,
            "free_margin": 9900.0,
            "raw": {},
        }

    def execute_trade(self, payload, decision, reject_reason=None, ai_decision=None):
        from app.schemas.journal import FinalDecisionEnum, TradeJournalEntry, DirectionEnum, DecisionEnum
        self.orders.append({
            "symbol": payload.symbol,
            "direction": payload.direction,
            "volume": payload.execution_quantity,
        })
        return TradeJournalEntry(
            trade_id="test-order-1",
            timestamp="2026-05-29T10:00:00Z",
            symbol=payload.symbol,
            timeframe="1h",
            direction=DirectionEnum(payload.direction),
            entry_price=payload.entry_price,
            stop_price=payload.stop_price or 0.0,
            target_price=payload.target_price or 0.0,
            risk_reward=2.0,
            m8_score=50.0,
            ai_decision=DecisionEnum.PROCEED_TO_SIMULATION,
            final_decision=FinalDecisionEnum.EXECUTED_SIM,
            simulated_fill={"mode": "CTRADER", "live_mode": self.live},
            result={
                "status": "SENT_TO_CTRADER" if self.live else "DRY_RUN_CTRADER",
                "reject_reason": None,
                "order": {"symbol_id": 1, "trade_side": "BUY"},
            },
        )

    def place_direct_order(self, symbol, direction, volume_lots, stop_loss=None, take_profit=None, label=None, comment="MetricFlow cTrader"):
        self.orders.append({
            "symbol": symbol,
            "direction": direction,
            "volume_lots": volume_lots,
        })
        symbol_name = symbol.upper().replace("/", "").replace("_", "").replace("-", "")
        if symbol_name not in self.get_symbols():
            return {
                "status": "REJECTED",
                "error": f"CTRADER_SYMBOL_NOT_FOUND:{symbol_name}",
                "symbol": symbol,
                "direction": direction,
                "volume_lots": volume_lots,
                "margin_checked": False,
            }
        trade_side = "BUY" if direction.upper() in {"BUY", "LONG"} else "SELL"
        if self.live:
            return {
                "status": "SENT_TO_CTRADER",
                "order_id": "order-1",
                "position_id": "pos-1",
                "symbol": symbol,
                "direction": trade_side,
                "volume_lots": volume_lots,
                "fill_price": None,
                "margin_checked": True,
                "free_margin_before": 9900.0,
                "estimated_margin_required": volume_lots * 1000.0,
                "error": None,
            }
        return {
            "status": "DRY_RUN",
            "order_id": None,
            "position_id": None,
            "symbol": symbol,
            "direction": trade_side,
            "volume_lots": volume_lots,
            "fill_price": None,
            "margin_checked": True,
            "free_margin_before": 9900.0,
            "estimated_margin_required": volume_lots * 1000.0,
            "error": None,
            "preview": {"symbol_id": 1, "trade_side": trade_side, "volume_lots": volume_lots},
        }

    def is_ready(self):
        return self.enabled


@pytest.fixture(autouse=True)
def fake_ctrader_order_broker(monkeypatch):
    import app.api.ctrader as ctrader_api

    fake = FakeCTraderBrokerWithOrder()
    monkeypatch.setattr(ctrader_api, "_ctrader_broker_instance", fake)
    yield fake
    monkeypatch.setattr(ctrader_api, "_ctrader_broker_instance", None)


@pytest.mark.asyncio
async def test_ctrader_order_rejected_without_symbol_id():
    """Unknown symbol should return 422 or 400."""
    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.post("/ctrader/order", json={
            "symbol": "UNKNOWNPAIR",
            "direction": "BUY",
            "volume_lots": 0.01,
        })

    # 422 = Pydantic validation, 400 = business logic rejection
    assert response.status_code in {200, 400, 422}, (
        f"Expected 200/400/422 for unknown symbol, got {response.status_code}: {response.text[:200]}"
    )
    if response.status_code == 200:
        data = response.json()
        assert "error" in data or data.get("status") in {"REJECTED", "ERROR"}, (
            "Expected error indication for unknown symbol"
        )


@pytest.mark.asyncio
async def test_ctrader_order_rejected_with_zero_volume():
    """Volume ≤ 0 should fail Pydantic validation (422)."""
    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.post("/ctrader/order", json={
            "symbol": "EURUSD",
            "direction": "BUY",
            "volume_lots": 0,
        })

    assert response.status_code == 422, (
        f"Expected 422 for zero volume, got {response.status_code}: {response.text[:200]}"
    )


@pytest.mark.asyncio
async def test_ctrader_order_dry_run_returns_preview(fake_ctrader_order_broker):
    """When live trading is disabled, order should return DRY_RUN status."""
    fake_ctrader_order_broker.live = False

    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.post("/ctrader/order", json={
            "symbol": "EURUSD",
            "direction": "BUY",
            "volume_lots": 0.01,
            "stop_loss": 1.0950,
            "take_profit": 1.1100,
        })

    assert response.status_code == 200, f"Unexpected status: {response.status_code}: {response.text[:200]}"
    data = response.json()
    assert data["status"] in {"DRY_RUN", "DRY_RUN_CTRADER", "EXECUTED_SIM"}, (
        f"Expected dry-run status, got {data.get('status')}"
    )
    assert data["symbol"] == "EURUSD"
    assert data["direction"] in {"BUY", "LONG"}
    assert data["volume_lots"] == 0.01


@pytest.mark.asyncio
async def test_ctrader_order_live_sends_to_bridge(fake_ctrader_order_broker):
    """When live trading is enabled, order should be sent to cTrader bridge."""
    fake_ctrader_order_broker.live = True

    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.post("/ctrader/order", json={
            "symbol": "EURUSD",
            "direction": "SELL",
            "volume_lots": 0.02,
        })

    assert response.status_code == 200, f"Unexpected status: {response.status_code}: {response.text[:200]}"
    data = response.json()
    assert data["status"] in {"SENT_TO_CTRADER", "EXECUTED"}, (
        f"Expected live execution status, got {data.get('status')}"
    )
    assert len(fake_ctrader_order_broker.orders) == 1
    assert fake_ctrader_order_broker.orders[0]["symbol"] == "EURUSD"


@pytest.mark.asyncio
async def test_ctrader_order_response_has_margin_fields(fake_ctrader_order_broker):
    """Response should include margin check metadata."""
    async with AsyncClient(transport=ASGITransport(app=_test_app()), base_url="http://test") as ac:
        response = await ac.post("/ctrader/order", json={
            "symbol": "EURUSD",
            "direction": "BUY",
            "volume_lots": 0.01,
        })

    assert response.status_code == 200
    data = response.json()
    assert "margin_checked" in data, "Missing margin_checked field"
    assert "free_margin_before" in data, "Missing free_margin_before field"
