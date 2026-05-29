"""Pydantic schemas for the cTrader API surface."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.live_trading import PositionResponse


class CTraderConnectionState(BaseModel):
    connected: bool
    app_authenticated: bool
    account_authenticated: bool
    host: str
    port: int
    last_error: str | None = None
    last_connected_at: str | None = None


class CTraderStatusResponse(BaseModel):
    status: str = "ok"
    name: str
    type: str
    mode: str
    ready: bool
    live_capable: bool
    enabled: bool
    live_trading_enabled: bool
    account_id: int | None = None
    host: str
    port: int
    symbols_cached: int
    connection: CTraderConnectionState


class CTraderSymbolsResponse(BaseModel):
    status: str = "ok"
    count: int
    symbols: dict[str, int]
    refreshed_at: datetime | None = None


class CTraderPositionsResponse(BaseModel):
    status: str = "ok"
    positions: list[PositionResponse]
    error: str | None = None


class CTraderBalanceResponse(BaseModel):
    status: str
    account_mode: str | None = None
    account_id: int | None = None
    currency: str | None = None
    balance: float | None = None
    equity: float | None = None
    used_margin: float | None = None
    free_margin: float | None = None
    balances: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] | None = None
    error: str | None = None


class CTraderActionResponse(BaseModel):
    status: str = "ok"
    health: CTraderStatusResponse


class CTraderOrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    direction: str = Field(..., pattern=r"^(BUY|SELL|LONG|SHORT)$")
    volume_lots: float = Field(..., gt=0, le=1000)
    stop_loss: float | None = None
    take_profit: float | None = None
    label: str | None = Field(default=None, max_length=50)
    comment: str | None = Field(default="MetricFlow cTrader", max_length=100)


class CTraderOrderResponse(BaseModel):
    status: str
    order_id: str | None = None
    position_id: str | None = None
    execution_price: float | None = None
    symbol: str | None = None
    direction: str | None = None
    volume_lots: float | None = None
    fill_price: float | None = None
    error: str | None = None
    margin_checked: bool = False
    free_margin_before: float | None = None
    estimated_margin_required: float | None = None
