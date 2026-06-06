"""Pydantic schemas for the Strategy Engine and Pattern Recognition APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Strategy schemas
# ---------------------------------------------------------------------------

class StrategyConfig(BaseModel):
    strategy_id: str = Field(..., pattern=r"^[a-z0-9_-]+$")
    name: str
    description: str = ""
    strategy_type: Literal["cisd", "pattern_enhanced", "custom"] = "cisd"
    weights: dict[str, float] = Field(default_factory=dict)
    enabled: bool = True
    min_confluence: float = Field(default=6.0, ge=0, le=100)
    timeframes: list[str] = Field(default=["1m"])
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StrategySwitchRequest(BaseModel):
    strategy_id: str
    force: bool = False


class StrategyStatusResponse(BaseModel):
    active_strategy_id: str
    available_strategies: list[StrategyConfig]
    last_switch: datetime | None
    pattern_stats: dict[str, int] = Field(default_factory=dict)


class StrategySmokeRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT")
    timeframe: str = Field(default="1h")
    bars: int = Field(default=100, ge=20, le=1000)


class StrategySmokeResponse(BaseModel):
    strategy_id: str
    symbol: str
    timeframe: str
    bars_scored: int
    signals_generated: int
    max_confluence: float
    sample_scores: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Pattern schemas
# ---------------------------------------------------------------------------

class PatternMatchSchema(BaseModel):
    pattern_type: str
    direction: Literal["LONG", "SHORT", "NEUTRAL"]
    confidence: float = Field(..., ge=0, le=1)
    start_idx: int
    end_idx: int
    neckline: float | None = None
    target_price: float | None = None


class PatternScanRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT")
    timeframe: str = Field(default="1h")
    bars: int = Field(default=200, ge=20, le=2000)


class PatternScanResponse(BaseModel):
    symbol: str
    timeframe: str
    bars_scanned: int
    patterns_found: list[PatternMatchSchema]
    aggregated_score: float = Field(..., ge=0, le=100)
    dominant_pattern: str | None = None
    avg_confidence: float = Field(..., ge=0, le=1)


class PatternStatsResponse(BaseModel):
    pattern_counts: dict[str, int]
    last_scan: datetime | None
    total_scans: int


# ---------------------------------------------------------------------------
# Strategy Health Dashboard schemas
# ---------------------------------------------------------------------------

class StrategyHealthItem(BaseModel):
    strategy_id: str
    name: str
    description: str = ""
    is_active: bool = False
    last_switch: datetime | None = None
    total_signals: int = 0
    win_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    profit_factor: float = Field(default=0.0, ge=0.0)
    avg_pnl_pct: float = Field(default=0.0)
    max_drawdown_pct: float = Field(default=0.0)
    last_signal_age_seconds: float | None = None
    health_score: float = Field(default=0.0, ge=0.0, le=100.0)
    signal_count_24h: int = 0


class StrategyHealthResponse(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    strategies: list[StrategyHealthItem]
