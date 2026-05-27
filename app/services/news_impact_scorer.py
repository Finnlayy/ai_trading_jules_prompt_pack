"""
News Impact Scorer — deterministic scoring of news items for trading symbols.

Evaluates:
- Symbol relevance (keyword matching)
- Sentiment polarity (lexicon-based)
- Urgency (keyword detection)
- Recency decay (exponential decay based on age)

Outputs RiskAdjustments that modulate the Risk Engine thresholds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Sequence

from app.services.news_aggregator import NewsItem
from app.services.news_sentiment_lexicon import (
    NEGATIVE_KEYWORDS,
    POSITIVE_KEYWORDS,
    URGENCY_KEYWORDS,
    get_symbol_synonyms,
)


@dataclass
class RiskAdjustments:
    """Additive / multiplicative adjustments applied to Risk Engine thresholds."""

    confluence_offset: float = 0.0
    crisis_offset: float = 0.0
    spread_multiplier: float = 1.0
    cooldown_bars_offset: int = 0
    human_review_required: bool = False


@dataclass
class ScoredNewsItem:
    item: NewsItem
    symbol_relevance: float = 0.0
    sentiment_polarity: float = 0.0
    urgency: float = 0.0
    recency_score: float = 0.0
    composite_score: float = 0.0


@dataclass
class NewsImpactSummary:
    symbol: str
    overall_sentiment: float = 0.0
    overall_urgency: float = 0.0
    article_count: int = 0
    dominant_topics: list[str] = field(default_factory=list)
    risk_adjustments: RiskAdjustments = field(default_factory=RiskAdjustments)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _score_symbol_relevance(item: NewsItem, symbol: str) -> float:
    """0.0–1.0 based on keyword presence in title + summary."""
    text = f"{item.title} {item.summary}".lower()
    synonyms = get_symbol_synonyms(symbol)
    hits = sum(1 for syn in synonyms if syn.lower() in text)
    # Also check exact symbol fragments (e.g. "BTC" inside "BTCUSDT")
    fragments = [symbol[:3].lower(), symbol[:4].lower()]
    hits += sum(1 for frag in fragments if frag in text)
    # Cap at 1.0
    return min(1.0, hits / max(1, len(synonyms)))


def _score_sentiment(text: str) -> float:
    """Return polarity between -1.0 (very negative) and +1.0 (very positive)."""
    text_lower = text.lower()
    pos_score = sum(
        weight for word, weight in POSITIVE_KEYWORDS.items() if word in text_lower
    )
    neg_score = sum(
        weight for word, weight in NEGATIVE_KEYWORDS.items() if word in text_lower
    )
    total = pos_score + neg_score
    if total == 0:
        return 0.0
    return (pos_score - neg_score) / total


def _score_urgency(text: str) -> float:
    """0.0–1.0 based on urgency keywords."""
    text_lower = text.lower()
    hits = sum(1 for word in URGENCY_KEYWORDS if word in text_lower)
    return min(1.0, hits * 0.25 + 0.1)  # 1 keyword → 0.35, 2 → 0.6, 3+ → 0.85+


def _recency_decay(published_iso: str, half_life_hours: float = 2.0) -> float:
    """Exponential decay from 1.0 (fresh) to ~0.0 (stale)."""
    try:
        pub_dt = datetime.fromisoformat(published_iso.replace("Z", "+00:00"))
    except ValueError:
        return 0.5
    now = datetime.now(timezone.utc)
    age_hours = (now - pub_dt).total_seconds() / 3600.0
    return math.exp(-age_hours / half_life_hours)


def _compute_composite(
    relevance: float,
    sentiment: float,
    urgency: float,
    recency: float,
) -> float:
    """Weighted composite in range [-1, 1]."""
    # Urgency and recency amplify sentiment, relevance gates it
    if relevance < 0.1:
        return 0.0
    amplified = sentiment * (0.5 + urgency * 0.5) * recency
    return max(-1.0, min(1.0, amplified))


# ---------------------------------------------------------------------------
# Threshold rules
# ---------------------------------------------------------------------------

def _compute_risk_adjustments(summary: NewsImpactSummary) -> RiskAdjustments:
    """Deterministic rule set translating impact summary into risk adjustments."""
    adj = RiskAdjustments()
    sentiment = summary.overall_sentiment
    urgency = summary.overall_urgency

    # Extreme conditions → mandatory human review
    if urgency > 0.8 and abs(sentiment) > 0.6:
        adj.human_review_required = True

    # Strong negative sentiment → tighten thresholds
    if sentiment < -0.5:
        adj.crisis_offset = +10.0
        adj.confluence_offset = +5.0

    # Strong positive sentiment → slightly relax crisis threshold (floor at 0)
    if sentiment > 0.5:
        adj.crisis_offset = -5.0

    # High urgency → increase cooldown
    if urgency > 0.7:
        adj.cooldown_bars_offset = +1

    # Regulation / exchange hack keywords implicitly raise spread tolerance
    # (detected via negative sentiment + urgency combination)
    if sentiment < -0.4 and urgency > 0.6:
        adj.spread_multiplier = 1.5

    return adj


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class NewsImpactScorer:
    """Deterministic scorer for news impact on trading decisions."""

    def score_items(
        self,
        items: Sequence[NewsItem],
        symbol: str,
        max_age_hours: float = 24.0,
        min_relevance: float = 0.3,
    ) -> List[ScoredNewsItem]:
        """Score a list of news items for relevance to a symbol."""
        scored: List[ScoredNewsItem] = []
        for item in items:
            recency = _recency_decay(item.published)
            # Hard cutoff for very old news
            if recency < 0.01:
                continue
            relevance = _score_symbol_relevance(item, symbol)
            if relevance < min_relevance:
                continue
            text = f"{item.title} {item.summary}"
            sentiment = _score_sentiment(text)
            urgency = _score_urgency(text)
            composite = _compute_composite(relevance, sentiment, urgency, recency)
            scored.append(
                ScoredNewsItem(
                    item=item,
                    symbol_relevance=round(relevance, 3),
                    sentiment_polarity=round(sentiment, 3),
                    urgency=round(urgency, 3),
                    recency_score=round(recency, 3),
                    composite_score=round(composite, 3),
                )
            )
        return scored

    def aggregate_impact(
        self,
        scored_items: Sequence[ScoredNewsItem],
    ) -> NewsImpactSummary:
        """Aggregate scored items into a summary with risk adjustments."""
        if not scored_items:
            return NewsImpactSummary(symbol="", article_count=0)

        # Weighted averages by recency
        total_weight = sum(s.recency_score for s in scored_items)
        if total_weight == 0:
            total_weight = 1.0

        overall_sentiment = sum(
            s.sentiment_polarity * s.recency_score for s in scored_items
        ) / total_weight
        overall_urgency = sum(
            s.urgency * s.recency_score for s in scored_items
        ) / total_weight

        # Dominant topics = most frequent pattern keywords in titles
        topic_counts: dict[str, int] = {}
        for s in scored_items:
            title_lower = s.item.title.lower()
            for topic in ("hack", "regulation", "etf", "futures", "sec", "fed", "cpi", "war", "ban", "partnership", "upgrade"):
                if topic in title_lower:
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1
        dominant = sorted(topic_counts, key=topic_counts.get, reverse=True)[:3]

        summary = NewsImpactSummary(
            symbol="",
            overall_sentiment=round(overall_sentiment, 3),
            overall_urgency=round(overall_urgency, 3),
            article_count=len(scored_items),
            dominant_topics=dominant,
        )
        summary.risk_adjustments = _compute_risk_adjustments(summary)
        return summary

    def get_risk_adjustments(
        self,
        summary: NewsImpactSummary,
    ) -> RiskAdjustments:
        """Public accessor for risk adjustments (computed in aggregate_impact)."""
        return summary.risk_adjustments


# Global singleton
news_impact_scorer = NewsImpactScorer()
