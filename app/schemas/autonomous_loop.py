"""Pydantic schemas for the Autonomous Trading Loop API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class WatchlistItemSchema(BaseModel):
    symbol: str = Field(..., pattern=r"^[A-Za-z0-9_\-\.]+$")
    timeframes: list[str] = Field(default=["1m", "5m", "15m"])
    active: bool = True
    strategy_id: str | None = None
    min_confluence: float | None = Field(default=None, ge=0, le=100)
    max_position_size_usdt: float | None = Field(default=None, gt=0)


class LoopControlRequest(BaseModel):
    action: Literal["start", "stop", "pause", "resume"]


class HealthSnapshotSchema(BaseModel):
    status: str
    cycles_completed: int
    signals_generated: int
    trades_executed: int
    errors_last_5min: int
    avg_cycle_time_ms: float
    next_poll: str | None
    timestamp: datetime


class LoopStatusResponse(BaseModel):
    is_running: bool
    is_paused: bool
    active_symbols: list[str]
    poll_interval_seconds: float
    loop_stats: dict[str, Any]
    health: HealthSnapshotSchema
    current_strategy_id: str
    last_generation_summary: dict[str, Any] = Field(default_factory=dict)
    last_processed_bars: dict[str, dict[str, Any]] = Field(default_factory=dict)


class StrategyRotationLogSchema(BaseModel):
    symbol: str
    old_strategy: str
    new_strategy: str
    regime: str
    reason: str
    timestamp: datetime


class LoopStatsResponse(BaseModel):
    cycles_completed: int
    signals_generated: int
    trades_executed: int
    errors_last_5min: int
    error_history: list[dict[str, Any]]
    avg_cycle_time_ms: float
    generated_at: datetime

class StrategyRotationResponse(BaseModel):
    symbol: str
    old_strategy: str
    new_strategy: str
    regime: str
    reason: str
    timestamp: str
