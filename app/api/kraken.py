"""FastAPI router for Kraken REST API endpoints."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.config import (
    KRAKEN_API_KEY,
    KRAKEN_API_SECRET,
    KRAKEN_DEMO_MODE,
    KRAKEN_ENABLED,
    KRAKEN_LIVE_TRADING_ENABLED,
    KRAKEN_MAX_ORDER_USD,
    KRAKEN_MIN_ORDER_USD,
    KRAKEN_SPOT_ONLY,
)
from app.schemas.kraken import (
    KrakenBalanceResponse,
    KrakenCancelRequest,
    KrakenCancelResponse,
    KrakenOrderRequest,
    KrakenOrderResponse,
    KrakenPositionsResponse,
    KrakenStatusResponse,
    KrakenTickerRequest,
    KrakenTickerResponse,
)
from app.services.kraken_broker import KrakenBroker, KrakenBrokerError, KrakenConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kraken", tags=["kraken"])

_broker_instance: KrakenBroker | None = None


def _get_broker() -> KrakenBroker:
    """Return a singleton KrakenBroker instance."""
    global _broker_instance
    if _broker_instance is None:
        config = KrakenConfig(
            enabled=KRAKEN_ENABLED,
            live_trading_enabled=KRAKEN_LIVE_TRADING_ENABLED,
            api_key=KRAKEN_API_KEY,
            api_secret=KRAKEN_API_SECRET,
            demo_mode=KRAKEN_DEMO_MODE,
            spot_only=KRAKEN_SPOT_ONLY,
            max_order_usd=KRAKEN_MAX_ORDER_USD,
            min_order_usd=KRAKEN_MIN_ORDER_USD,
        )
        _broker_instance = KrakenBroker(config=config)
    return _broker_instance


# ------------------------------------------------------------------
# Status & health
# ------------------------------------------------------------------

@router.get("/status", response_model=KrakenStatusResponse)
async def kraken_status() -> dict[str, Any]:
    broker = _get_broker()
    health = broker.health()
    return {
        "status": "ok",
        "name": health["name"],
        "type": health["type"],
        "mode": health["mode"],
        "ready": health["ready"],
        "live_capable": health["live_capable"],
        "enabled": broker.config.enabled,
        "live_trading_enabled": broker.config.live_trading_enabled,
        "demo_mode": broker.config.demo_mode,
        "spot_only": broker.config.spot_only,
        "credentials_present": health["credentials_present"],
        "last_error": health["last_error"],
    }


# ------------------------------------------------------------------
# Market data (public, no auth)
# ------------------------------------------------------------------

@router.get("/time")
async def kraken_time() -> dict[str, Any]:
    broker = _get_broker()
    try:
        result = await asyncio.to_thread(broker.get_server_time)
        return {"status": "ok", "time": result}
    except KrakenBrokerError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/ticker", response_model=KrakenTickerResponse)
async def kraken_ticker(req: KrakenTickerRequest) -> dict[str, Any]:
    broker = _get_broker()
    try:
        result = await asyncio.to_thread(broker.get_ticker, req.pair)
        return {
            "status": "ok",
            "pair": req.pair.upper(),
            "ticker": result,
        }
    except KrakenBrokerError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ------------------------------------------------------------------
# Private account data
# ------------------------------------------------------------------

@router.get("/balance", response_model=KrakenBalanceResponse)
async def kraken_balance() -> dict[str, Any]:
    broker = _get_broker()
    result = broker.get_wallet_balances()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Unknown error"))
    return result


@router.get("/positions", response_model=KrakenPositionsResponse)
async def kraken_positions() -> dict[str, Any]:
    broker = _get_broker()
    result = broker.get_positions()
    if result.get("status") == "error":
        raise HTTPException(status_code=502, detail=result.get("error", "Unknown error"))
    return result


# ------------------------------------------------------------------
# Order management
# ------------------------------------------------------------------

@router.post("/order", response_model=KrakenOrderResponse)
async def kraken_order(req: KrakenOrderRequest) -> dict[str, Any]:
    broker = _get_broker()

    # Validate USD bounds
    # Volume is in base currency; we cannot easily validate USD without ticker price here.
    # Rely on broker min_order_usd / max_order_usd for safety.

    side = "buy" if req.direction.upper() in {"BUY", "LONG"} else "sell"
    pair = broker.normalize_pair(req.symbol)

    # Safety: if no credentials or live trading disabled, force validate_only
    validate = req.validate_only or not broker.is_live_capable()

    try:
        result = await asyncio.to_thread(
            broker.place_order,
            pair=pair,
            side=side,
            volume=req.volume,
            order_type=req.order_type,
            price=req.price,
            leverage=req.leverage,
            validate=validate,
            oflags=req.oflags or None,
        )
        return {
            "status": "ok",
            "order_id": result.get("txid", [None])[0] if isinstance(result.get("txid"), list) else None,
            "descr": result.get("descr"),
            "txid": result.get("txid"),
            "pair": pair,
            "direction": side,
            "volume": req.volume,
            "order_type": req.order_type,
            "price": req.price,
            "validated": validate,
            "raw": result,
        }
    except KrakenBrokerError as exc:
        logger.error("Kraken order failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/cancel", response_model=KrakenCancelResponse)
async def kraken_cancel(req: KrakenCancelRequest) -> dict[str, Any]:
    broker = _get_broker()
    try:
        result = await asyncio.to_thread(broker.cancel_order, req.txid)
        count = result.get("count", 0)
        return {
            "status": "ok",
            "count": count,
        }
    except KrakenBrokerError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/orders/open")
async def kraken_open_orders() -> dict[str, Any]:
    broker = _get_broker()
    try:
        result = await asyncio.to_thread(broker.get_open_orders)
        return {"status": "ok", "orders": result}
    except KrakenBrokerError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
