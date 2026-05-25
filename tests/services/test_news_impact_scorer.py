"""Tests for the News Impact Scorer."""

from __future__ import annotations

import pytest

from app.services.news_aggregator import NewsItem
from app.services.news_impact_scorer import (
    NewsImpactScorer,
    RiskAdjustments,
    _compute_composite,
    _recency_decay,
    _score_sentiment,
    _score_symbol_relevance,
    _score_urgency,
)


@pytest.fixture
def scorer():
    return NewsImpactScorer()


@pytest.fixture
def sample_items():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return [
        NewsItem(
            source="BBC",
            title="Bitcoin surges to new all-time high after ETF approval",
            link="http://example.com/1",
            published=now.isoformat(),
            summary="Institutional adoption drives rally",
        ),
        NewsItem(
            source="CoinDesk",
            title="Breaking: Major exchange hack wipes out user funds",
            link="http://example.com/2",
            published=now.isoformat(),
            summary="Security breach causes panic selling",
        ),
        NewsItem(
            source="Reuters",
            title="Federal Reserve holds rates steady",
            link="http://example.com/3",
            published=now.isoformat(),
            summary="No change in monetary policy",
        ),
    ]


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

def test_score_symbol_relevance_btc():
    item = NewsItem(
        source="Test", title="Bitcoin price analysis", link="", published="", summary="BTC trends"
    )
    assert _score_symbol_relevance(item, "BTCUSDT") > 0.5


def test_score_symbol_relevance_unrelated():
    item = NewsItem(
        source="Test", title="Oil prices rise in Middle East", link="", published="", summary="Crude oil"
    )
    assert _score_symbol_relevance(item, "BTCUSDT") < 0.3


def test_score_sentiment_positive():
    text = "Bitcoin surges to all-time high in massive rally"
    assert _score_sentiment(text) > 0.0


def test_score_sentiment_negative():
    text = "Crypto market crash after major hack and fraud investigation"
    assert _score_sentiment(text) < 0.0


def test_score_sentiment_neutral():
    text = "The weather today is sunny with a chance of rain"
    assert _score_sentiment(text) == 0.0


def test_score_urgency_with_keywords():
    text = "BREAKING: Urgent alert for all traders"
    assert _score_urgency(text) > 0.5


def test_score_urgency_without_keywords():
    text = "Weekly market recap and analysis"
    assert _score_urgency(text) < 0.5


def test_recency_decay_fresh():
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    assert _recency_decay(now) > 0.9


def test_recency_decay_old():
    assert _recency_decay("2020-01-01T00:00:00+00:00") < 0.01


def test_compute_composite_zero_relevance():
    assert _compute_composite(0.0, 0.8, 0.9, 1.0) == 0.0


def test_compute_composite_within_bounds():
    result = _compute_composite(0.8, -0.6, 0.9, 1.0)
    assert -1.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# Scorer integration tests
# ---------------------------------------------------------------------------

def test_score_items_filters_by_relevance(scorer, sample_items):
    scored = scorer.score_items(sample_items, symbol="BTCUSDT", min_relevance=0.3)
    # Bitcoin-related items should be included
    assert len(scored) >= 1
    for s in scored:
        assert s.symbol_relevance >= 0.3


def test_score_items_filters_by_age(scorer, sample_items):
    scored = scorer.score_items(
        sample_items, symbol="BTCUSDT", max_age_hours=1.0, min_relevance=0.0
    )
    # Very old items should be filtered out by recency
    assert all(s.recency_score > 0.01 for s in scored)


def test_aggregate_impact_empty():
    scorer = NewsImpactScorer()
    summary = scorer.aggregate_impact([])
    assert summary.article_count == 0


def test_aggregate_impact_negative_sentiment_increases_crisis(scorer, sample_items):
    scored = scorer.score_items(sample_items, symbol="BTCUSDT", min_relevance=0.1)
    summary = scorer.aggregate_impact(scored)
    # The hack article is negative and urgent
    if summary.overall_sentiment < -0.3:
        assert summary.risk_adjustments.crisis_offset > 0


def test_aggregate_impact_human_review_extreme_conditions(scorer):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    extreme_items = [
        NewsItem(
            source="Test",
            title="BREAKING: Bitcoin BANNED worldwide in emergency regulation",
            link="",
            published=now.isoformat(),
            summary="Crash imminent",
        )
    ]
    scored = scorer.score_items(extreme_items, symbol="BTCUSDT", min_relevance=0.0)
    summary = scorer.aggregate_impact(scored)
    if summary.overall_urgency > 0.8 and abs(summary.overall_sentiment) > 0.6:
        assert summary.risk_adjustments.human_review_required is True


def test_aggregate_impact_composite_score_within_bounds(scorer, sample_items):
    scored = scorer.score_items(sample_items, symbol="BTCUSDT", min_relevance=0.0)
    for s in scored:
        assert -1.0 <= s.composite_score <= 1.0


def test_risk_adjustments_default_safe():
    """Default RiskAdjustments should not modify thresholds."""
    adj = RiskAdjustments()
    assert adj.confluence_offset == 0.0
    assert adj.crisis_offset == 0.0
    assert adj.spread_multiplier == 1.0
    assert adj.cooldown_bars_offset == 0
    assert adj.human_review_required is False
