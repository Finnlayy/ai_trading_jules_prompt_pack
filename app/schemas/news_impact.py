"""Pydantic schemas for News Impact scoring API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class ScoredNewsItemSchema(BaseModel):
    source: str
    title: str
    link: str
    published: str
    symbol_relevance: float = Field(..., ge=0, le=1)
    sentiment_polarity: float = Field(..., ge=-1, le=1)
    urgency: float = Field(..., ge=0, le=1)
    recency_score: float = Field(..., ge=0, le=1)
    composite_score: float = Field(..., ge=-1, le=1)


class RiskAdjustmentsSchema(BaseModel):
    confluence_offset: float
    crisis_offset: float
    spread_multiplier: float
    cooldown_bars_offset: int
    human_review_required: bool


class NewsImpactSummarySchema(BaseModel):
    symbol: str
    overall_sentiment: float
    overall_urgency: float
    article_count: int
    dominant_topics: list[str]
    risk_adjustments: RiskAdjustmentsSchema
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NewsImpactRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT")
    max_age_hours: float = Field(default=24.0, ge=1, le=72)
    min_relevance: float = Field(default=0.3, ge=0, le=1)


class NewsImpactAllResponse(BaseModel):
    impacts: dict[str, NewsImpactSummarySchema]
    total_articles_scored: int
    fetched_at: datetime | None


class NewsScoredResponse(BaseModel):
    items: list[ScoredNewsItemSchema]
    count: int
    cached_at: datetime | None
