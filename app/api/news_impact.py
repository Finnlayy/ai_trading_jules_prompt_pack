"""API endpoints for news impact scoring and introspection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.schemas.news_impact import (
    NewsImpactAllResponse,
    NewsImpactRequest,
    NewsImpactSummarySchema,
    NewsScoredResponse,
    RiskAdjustmentsSchema,
    ScoredNewsItemSchema,
)
from app.services.news_aggregator import news_aggregator_instance
from app.services.news_impact_scorer import news_impact_scorer

router = APIRouter()


@router.get("/impact")
async def get_news_impact(
    symbol: str = Query(default="BTCUSDT"),
    max_age_hours: float = Query(default=24.0, ge=1, le=72),
    min_relevance: float = Query(default=0.3, ge=0, le=1),
):
    """Return the current news impact score for a single symbol."""
    cached = news_aggregator_instance.get_cached()
    scored = news_impact_scorer.score_items(
        cached, symbol=symbol, max_age_hours=max_age_hours, min_relevance=min_relevance
    )
    summary = news_impact_scorer.aggregate_impact(scored)
    summary.symbol = symbol

    return NewsImpactSummarySchema(
        symbol=symbol,
        overall_sentiment=summary.overall_sentiment,
        overall_urgency=summary.overall_urgency,
        article_count=summary.article_count,
        dominant_topics=summary.dominant_topics,
        risk_adjustments=RiskAdjustmentsSchema(
            confluence_offset=summary.risk_adjustments.confluence_offset,
            crisis_offset=summary.risk_adjustments.crisis_offset,
            spread_multiplier=summary.risk_adjustments.spread_multiplier,
            cooldown_bars_offset=summary.risk_adjustments.cooldown_bars_offset,
            human_review_required=summary.risk_adjustments.human_review_required,
        ),
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/impact/all")
async def get_all_news_impacts(
    symbols: list[str] = Query(default=["BTCUSDT", "ETHUSDT"]),
    max_age_hours: float = Query(default=24.0, ge=1, le=72),
    min_relevance: float = Query(default=0.3, ge=0, le=1),
):
    """Return impact scores for all requested symbols."""
    cached = news_aggregator_instance.get_cached()
    impacts: dict[str, NewsImpactSummarySchema] = {}
    total_articles = 0

    for symbol in symbols:
        scored = news_impact_scorer.score_items(
            cached, symbol=symbol, max_age_hours=max_age_hours, min_relevance=min_relevance
        )
        summary = news_impact_scorer.aggregate_impact(scored)
        summary.symbol = symbol
        total_articles += summary.article_count

        impacts[symbol] = NewsImpactSummarySchema(
            symbol=symbol,
            overall_sentiment=summary.overall_sentiment,
            overall_urgency=summary.overall_urgency,
            article_count=summary.article_count,
            dominant_topics=summary.dominant_topics,
            risk_adjustments=RiskAdjustmentsSchema(
                confluence_offset=summary.risk_adjustments.confluence_offset,
                crisis_offset=summary.risk_adjustments.crisis_offset,
                spread_multiplier=summary.risk_adjustments.spread_multiplier,
                cooldown_bars_offset=summary.risk_adjustments.cooldown_bars_offset,
                human_review_required=summary.risk_adjustments.human_review_required,
            ),
            timestamp=datetime.now(timezone.utc),
        )

    return NewsImpactAllResponse(
        impacts=impacts,
        total_articles_scored=total_articles,
        fetched_at=news_aggregator_instance.last_fetch_iso(),
    )


@router.post("/refresh")
async def refresh_news():
    """Force an immediate news fetch + scoring cycle."""
    items = await news_aggregator_instance.fetch(source="all")
    return {
        "fetched": len(items),
        "cached_total": len(news_aggregator_instance.get_cached()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/scored")
async def get_scored_news(
    symbol: str = Query(default="BTCUSDT"),
    max_age_hours: float = Query(default=24.0, ge=1, le=72),
    min_relevance: float = Query(default=0.3, ge=0, le=1),
):
    """Return individual scored news items with metadata."""
    cached = news_aggregator_instance.get_cached()
    scored = news_impact_scorer.score_items(
        cached, symbol=symbol, max_age_hours=max_age_hours, min_relevance=min_relevance
    )

    return NewsScoredResponse(
        items=[
            ScoredNewsItemSchema(
                source=s.item.source,
                title=s.item.title,
                link=s.item.link,
                published=s.item.published,
                symbol_relevance=s.symbol_relevance,
                sentiment_polarity=s.sentiment_polarity,
                urgency=s.urgency,
                recency_score=s.recency_score,
                composite_score=s.composite_score,
            )
            for s in scored
        ],
        count=len(scored),
        cached_at=datetime.fromisoformat(news_aggregator_instance.last_fetch_iso())
        if news_aggregator_instance.last_fetch_iso()
        else None,
    )
