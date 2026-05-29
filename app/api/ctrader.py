"""cTrader broker control and inspection endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.schemas.ctrader import (
    CTraderActionResponse,
    CTraderBalanceResponse,
    CTraderOrderRequest,
    CTraderOrderResponse,
    CTraderPositionsResponse,
    CTraderStatusResponse,
    CTraderSymbolsResponse,
)
from app.services.ctrader_broker import CTraderBroker
from app.services.journal_logger import journal_logger_instance

router = APIRouter()

_ctrader_broker_instance: CTraderBroker | None = None


def _active_ctrader_broker() -> CTraderBroker | None:
    from app.api import orchestrator

    broker = orchestrator.broker_instance
    broker_type = getattr(broker, "get_broker_type", lambda: "")()
    if broker_type == "ctrader":
        return broker
    return None


def _get_ctrader_broker() -> CTraderBroker:
    global _ctrader_broker_instance
    active = _active_ctrader_broker()
    if active is not None:
        return active
    if _ctrader_broker_instance is None:
        _ctrader_broker_instance = CTraderBroker(journal_path=journal_logger_instance.filepath)
    return _ctrader_broker_instance


@router.get("/status", response_model=CTraderStatusResponse)
async def get_ctrader_status():
    """Return cTrader connection, auth, and configuration status."""
    broker = _get_ctrader_broker()
    return await asyncio.to_thread(broker.health)


@router.get("/symbols", response_model=CTraderSymbolsResponse)
async def get_ctrader_symbols():
    """Return the cached cTrader symbol map."""
    broker = _get_ctrader_broker()
    symbols = await asyncio.to_thread(broker.get_symbols)
    return CTraderSymbolsResponse(count=len(symbols), symbols=symbols)


@router.post("/symbols/refresh", response_model=CTraderSymbolsResponse)
async def refresh_ctrader_symbols():
    """Force-refresh the cTrader symbol map from Open API."""
    broker = _get_ctrader_broker()
    try:
        symbols = await asyncio.to_thread(broker.refresh_symbols)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CTraderSymbolsResponse(
        count=len(symbols),
        symbols=symbols,
        refreshed_at=datetime.now(timezone.utc),
    )


@router.get("/positions", response_model=CTraderPositionsResponse)
async def get_ctrader_positions():
    """Return cTrader open positions."""
    broker = _get_ctrader_broker()
    result = await asyncio.to_thread(broker.get_positions)
    return CTraderPositionsResponse(
        status=result.get("status", "ok"),
        positions=result.get("positions", []),
        error=result.get("error"),
    )


@router.get("/balance", response_model=CTraderBalanceResponse)
async def get_ctrader_balance():
    """Return cTrader account balance and margin data."""
    broker = _get_ctrader_broker()
    return await asyncio.to_thread(broker.get_wallet_balances, "CTRADER")


@router.post("/connect", response_model=CTraderActionResponse)
async def connect_ctrader():
    """Manually trigger cTrader connection and authentication."""
    broker = _get_ctrader_broker()
    try:
        health = await asyncio.to_thread(broker.connect)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CTraderActionResponse(health=health)


@router.post("/disconnect", response_model=CTraderActionResponse)
async def disconnect_ctrader():
    """Gracefully stop the cTrader client connection."""
    broker = _get_ctrader_broker()
    health = await asyncio.to_thread(broker.disconnect)
    return CTraderActionResponse(health=health)


@router.post("/order", response_model=CTraderOrderResponse)
async def place_ctrader_order(req: CTraderOrderRequest):
    """Place a direct market order through cTrader Open API."""
    broker = _get_ctrader_broker()
    result = await asyncio.to_thread(
        broker.place_direct_order,
        symbol=req.symbol,
        direction=req.direction,
        volume_lots=req.volume_lots,
        stop_loss=req.stop_loss,
        take_profit=req.take_profit,
        label=req.label,
        comment=req.comment or "MetricFlow cTrader",
    )
    return CTraderOrderResponse(**result)
