"""Schemas for the paper-training trade lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


OutcomeSource = Literal["backtest", "shadow", "live_paper", "live"]
CandidateStatus = Literal[
    "created",
    "reviewed",
    "risk_rejected",
    "paper_filled",
    "closed",
    "discarded",
]


class SignalCandidateRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    candidate_id: str = Field(..., min_length=1)
    signal_id: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1)
    timeframe: str = Field(..., min_length=1)
    strategy_id: str = Field(..., min_length=1)
    direction: Literal["LONG", "SHORT"]
    entry_price: float
    stop_price: float | None = None
    target_price: float | None = None
    confluence_score: float = Field(default=0.0, ge=0.0, le=100.0)
    bar_timestamp: datetime | None = None
    bar_ts_ms: int | None = None
    status: CandidateStatus = "created"
    features: dict[str, Any] = Field(default_factory=dict)
    source: OutcomeSource = "live_paper"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: datetime | None = None


class AgentReviewRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    candidate_id: str = Field(..., min_length=1)
    signal_id: str | None = None
    scout_name: str = Field(..., min_length=1)
    decision: str = Field(..., min_length=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    provider: str | None = None
    model: str | None = None
    reasons: list[str] = Field(default_factory=list)
    raw_report: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskDecisionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    candidate_id: str = Field(..., min_length=1)
    signal_id: str | None = None
    decision: str = Field(..., min_length=1)
    reason_code: str | None = None
    limits_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PaperExecutionRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    candidate_id: str | None = None
    trade_id: str = Field(..., min_length=1)
    signal_id: str | None = None
    symbol: str = Field(..., min_length=1)
    direction: Literal["LONG", "SHORT"]
    strategy_id: str | None = None
    timeframe: str | None = None
    fill_price: float
    volume: float = Field(..., gt=0.0)
    fee: float = 0.0
    status: Literal["open", "closed", "cancelled"] = "open"
    outcome_source: OutcomeSource = "live_paper"


class PaperOutcomeRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    candidate_id: str | None = None
    trade_id: str = Field(..., min_length=1)
    signal_id: str | None = None
    symbol: str = Field(..., min_length=1)
    direction: Literal["LONG", "SHORT"]
    strategy_id: str | None = None
    timeframe: str | None = None
    close_reason: str = Field(..., min_length=1)
    exit_price: float
    pnl: float
    pnl_pct: float = 0.0
    r_multiple: float = 0.0
    win: bool
    duration_seconds: float | None = None
    outcome_source: OutcomeSource = "live_paper"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentLearningRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scout_name: str = Field(..., min_length=1)
    symbol: str = Field(..., min_length=1)
    direction: Literal["LONG", "SHORT"]
    was_correct: bool
    candidate_id: str | None = None
    trade_id: str | None = None
    signal_id: str | None = None
    strategy_id: str | None = None
    timeframe: str | None = None
    outcome_source: OutcomeSource = "live_paper"
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
