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
