"""FastAPI router for Kraken Paper Trading endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.kraken_paper_broker import KrakenPaperBroker, KrakenPaperConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/kraken/paper", tags=["kraken-paper"])

_broker_instance: KrakenPaperBroker | None = None


def _get_broker() -> KrakenPaperBroker:
    """Return a singleton KrakenPaperBroker instance."""
    global _broker_instance
    if _broker_instance is None:
        _broker_instance = KrakenPaperBroker(config=KrakenPaperConfig())
    return _broker_instance


# ------------------------------------------------------------------
# Schemas
# ------------------------------------------------------------------

class PaperOrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    direction: str = Field(..., pattern=r"^(BUY|SELL|LONG|SHORT)$")
    volume: float = Field(..., gt=0, le=1000)
    order_type: str = Field(default="market", pattern=r"^(market|limit)$")
    price: float | None = None


class PaperCloseRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    volume: float | None = None
    order_type: str = Field(default="market", pattern=r"^(market|limit)$")


class PaperResetRequest(BaseModel):
    balance: float | None = Field(default=None, gt=0)


# ------------------------------------------------------------------
# Status & balance
# ------------------------------------------------------------------

@router.get("/status")
async def paper_status() -> dict[str, Any]:
    broker = _get_broker()
    health = broker.health()
    balance = broker.get_wallet_balances()
    return {
        "status": "ok",
        "broker": health,
        "balance": balance,
    }


@router.get("/balance")
async def paper_balance() -> dict[str, Any]:
    broker = _get_broker()
    return broker.get_wallet_balances()


# ------------------------------------------------------------------
# Positions
# ------------------------------------------------------------------

@router.get("/positions")
async def paper_positions() -> dict[str, Any]:
    broker = _get_broker()
    return broker.get_positions()


# ------------------------------------------------------------------
# Order placement
# ------------------------------------------------------------------

@router.post("/order")
async def paper_order(req: PaperOrderRequest) -> dict[str, Any]:
    broker = _get_broker()
    result = broker.place_paper_order(
        symbol=req.symbol,
        direction=req.direction,
        volume=req.volume,
        order_type=req.order_type,
        price=req.price,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return result


# ------------------------------------------------------------------
# Position closing
# ------------------------------------------------------------------

@router.post("/close")
async def paper_close(req: PaperCloseRequest) -> dict[str, Any]:
    broker = _get_broker()
    result = broker.close_paper_position(
        symbol=req.symbol,
        volume=req.volume,
        order_type=req.order_type,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return result


# ------------------------------------------------------------------
# History
# ------------------------------------------------------------------

@router.get("/history")
async def paper_history(limit: int = 100) -> dict[str, Any]:
    broker = _get_broker()
    return broker.get_paper_history(limit=limit)


# ------------------------------------------------------------------
# Account reset
# ------------------------------------------------------------------

@router.post("/reset")
async def paper_reset(req: PaperResetRequest | None = None) -> dict[str, Any]:
    broker = _get_broker()
    new_balance = req.balance if req else None
    return broker.reset_paper_account(new_balance=new_balance)
