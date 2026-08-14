"""Pydantic schemas for the Kraken API surface."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class KrakenStatusResponse(BaseModel):
    status: str = "ok"
    name: str
    type: str
    mode: str
    ready: bool
    live_capable: bool
    enabled: bool
    live_trading_enabled: bool
    demo_mode: bool
    spot_only: bool
    credentials_present: bool
    last_error: str | None = None


class KrakenBalanceResponse(BaseModel):
    status: str
    account_mode: str | None = None
    balances: dict[str, Any] = Field(default_factory=dict)
    trade_balance: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] | None = None
    error: str | None = None


class KrakenPositionsResponse(BaseModel):
    status: str
    positions: dict[str, Any] = Field(default_factory=dict)
    count: int = 0
    error: str | None = None


class KrakenOrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    direction: str = Field(..., pattern=r"^(BUY|SELL|LONG|SHORT)$")
    volume: float = Field(..., gt=0, le=1000)
    order_type: str = Field(default="market", pattern=r"^(market|limit|stop-loss|take-profit|stop-loss-limit|take-profit-limit|settle-position)$")
    price: float | None = None
    leverage: str | None = Field(default=None, pattern=r"^[0-9]+:1$")
    validate_only: bool = False
    oflags: list[str] = Field(default_factory=list)
    label: str | None = Field(default=None, max_length=50)


class KrakenOrderResponse(BaseModel):
    status: str
    order_id: str | None = None
    descr: dict[str, Any] | None = None
    txid: list[str] | None = None
    pair: str | None = None
    direction: str | None = None
    volume: float | None = None
    order_type: str | None = None
    price: float | None = None
    error: str | None = None
    validated: bool = False
    raw: dict[str, Any] | None = None


class KrakenTickerRequest(BaseModel):
    pair: str = Field(..., min_length=1, max_length=20)


class KrakenTickerResponse(BaseModel):
    status: str = "ok"
    pair: str
    ticker: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class KrakenCancelRequest(BaseModel):
    txid: str = Field(..., min_length=1)


class KrakenCancelResponse(BaseModel):
    status: str
    count: int = 0
    error: str | None = None
