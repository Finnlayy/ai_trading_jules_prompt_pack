"""cTrader FIX API broker control and order endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from app.schemas.ctrader import (
    CTraderActionResponse,
    CTraderBalanceResponse,
    CTraderOrderRequest,
    CTraderOrderResponse,
    CTraderStatusResponse,
)
from app.services.ctrader_fix_broker import CTraderFixBroker, CTraderFixConfig
from app.core.config import (
    CTRADER_FIX_ENABLED,
    CTRADER_FIX_HOST,
    CTRADER_FIX_LIVE_TRADING_ENABLED,
    CTRADER_FIX_PORT,
    CTRADER_FIX_SENDER_COMP_ID,
    CTRADER_FIX_TARGET_COMP_ID,
    CTRADER_FIX_PASSWORD,
    CTRADER_FIX_SENDER_SUB_ID,
)

router = APIRouter()

_fix_broker_instance: CTraderFixBroker | None = None


def _get_fix_broker() -> CTraderFixBroker:
    global _fix_broker_instance
    if _fix_broker_instance is None:
        config = CTraderFixConfig()
        _fix_broker_instance = CTraderFixBroker(config=config)
    return _fix_broker_instance


@router.get("/status", response_model=CTraderStatusResponse)
async def get_fix_status():
    """Return cTrader FIX connection and configuration status."""
    broker = _get_fix_broker()
    return await asyncio.to_thread(broker.health)


@router.post("/connect", response_model=CTraderActionResponse)
async def connect_fix():
    """Manually trigger cTrader FIX logon."""
    broker = _get_fix_broker()
    try:
        status = await asyncio.to_thread(broker.client.connect)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return CTraderActionResponse(
        status="ok",
        health=await asyncio.to_thread(broker.health),
    )


@router.post("/disconnect", response_model=CTraderActionResponse)
async def disconnect_fix():
    """Gracefully disconnect cTrader FIX session."""
    broker = _get_fix_broker()
    await asyncio.to_thread(broker.client.disconnect)
    return CTraderActionResponse(
        status="ok",
        health=await asyncio.to_thread(broker.health),
    )


@router.post("/order", response_model=CTraderOrderResponse)
async def place_fix_order(req: CTraderOrderRequest):
    """Place a market order via cTrader FIX API."""
    broker = _get_fix_broker()
    result = await asyncio.to_thread(
        broker.place_direct_order,
        symbol=req.symbol,
        direction=req.direction,
        volume_lots=req.volume_lots,
        stop_loss=req.stop_loss,
        take_profit=req.take_profit,
        label=req.label,
    )
    return CTraderOrderResponse(**result)


@router.get("/balance", response_model=CTraderBalanceResponse)
async def get_fix_balance():
    """Return cTrader FIX balance (not available via FIX, returns placeholder)."""
    broker = _get_fix_broker()
    return CTraderBalanceResponse(
        status="not_implemented",
        error="FIX API does not expose balance endpoint directly",
    )
