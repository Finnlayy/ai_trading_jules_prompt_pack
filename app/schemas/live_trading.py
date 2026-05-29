"""Pydantic schemas for Live Paper Trading API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class PositionResponse(BaseModel):
    trade_id: str
    symbol: str
    direction: str
    entry_price: float
    current_price: float
    size: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    open_time: datetime
    strategy_id: str | None = None
    stop_price: float
    target_price: float
    time_in_trade_minutes: float


class PerformanceMetricsSchema(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    winrate_pct: float
    profit_factor: float
    expectancy: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    max_drawdown_start_idx: int
    max_drawdown_end_idx: int
    total_pnl: float
    avg_trade_pnl: float
    avg_winner: float
    avg_loser: float
    largest_winner: float
    largest_loser: float
    avg_holding_time_minutes: float
    calculated_at: str


class PerformanceResponse(BaseModel):
    metrics: PerformanceMetricsSchema
    lookback_days: int
    generated_at: datetime


class EquityCurvePoint(BaseModel):
    trade_idx: int
    equity: float


class LiveTradingStatus(BaseModel):
    is_active: bool
    broker_mode: str
    loop_running: bool
    open_positions_count: int
    total_exposure_usdt: float
    today_pnl: float
    today_trades: int
    circuit_breaker_tripped: bool
    last_trade_at: datetime | None = None
    uptime_seconds: float = 0.0


class EmergencyStopRequest(BaseModel):
    reason: str = "Manual emergency stop"
    close_open_positions: bool = True
    halt_duration_minutes: int = Field(default=60, ge=1, le=1440)


class EmergencyStopResponse(BaseModel):
    success: bool
    reason: str
    positions_closed: int
    halted_until: datetime


class ManualOrderRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair, e.g. BTCUSDT")
    direction: Literal["LONG", "SHORT"] = Field(..., description="Trade direction")
    intent: Literal["ENTRY", "CLOSE"] = Field(default="ENTRY", description="ENTRY or CLOSE")
    quantity: float = Field(..., gt=0.0, description="Order quantity / size")
    entry_price: float | None = Field(default=None, description="Limit price or null for market")
    stop_price: float | None = Field(default=None, description="Stop loss price")
    target_price: float | None = Field(default=None, description="Take profit price")
    account_mode: Literal["SPOT", "FUTURES"] = Field(default="SPOT")
    leverage: float | None = Field(default=None, gt=0.0)
    order_command: Literal["GO", "HOLD", "KILL"] = Field(default="GO")


class SSEEventSchema(BaseModel):
    event_type: Literal["trade", "position", "metrics", "alert", "heartbeat"]
    payload: dict[str, Any]
    timestamp: datetime
