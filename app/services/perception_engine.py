import time
from typing import Dict, Any, Optional
from app.schemas.perception import PerceptionContext, IndicatorState, RegimeContext, NewsContext

from app.services.regime_engine import regime_engine_instance
from app.services.news_aggregator import news_aggregator_instance
from app.services.news_impact_scorer import news_impact_scorer

class PerceptionEngine:
    def __init__(self):
        pass

    async def build_context(self, symbol: str, timeframe: str) -> PerceptionContext:
        """
        Builds a normalized PerceptionContext by gathering data from various sources.
        """
        # Fetch latest price
        try:
            # latest_bar = market_data_service.get_latest_bar(symbol)
            latest_bar = None  # mock for now as market_data_service is undefined
            current_price = latest_bar['close'] if latest_bar else 0.0
        except Exception:
            current_price = 0.0

        # 1. Market Indicators (Mocked/Simplified for v1, in real scenario fetch from technicals)
        indicators = [
            IndicatorState(name="RSI", value=50.0, signal="neutral"),
            IndicatorState(name="MACD", value=0.0, signal="neutral")
        ]

        # 2. Market Regime
        try:
            regime_data = regime_engine_instance.get_current_regime(symbol)
            regime = RegimeContext(
                market_regime=regime_data.get("regime", "unknown"),
                volatility="medium", # Simplified
                trend_strength=regime_data.get("trend_strength", 0.5)
            )
        except Exception:
            regime = RegimeContext(market_regime="unknown", volatility="unknown", trend_strength=0.0)

        # 3. News Context
        try:
            news_items = news_aggregator_instance.get_cached()
            scored_news = news_impact_scorer.score_items(news_items, symbol)
            summary = news_impact_scorer.aggregate_impact(scored_news)

            news_ctx = NewsContext(
                recent_sentiment_polarity=summary.composite_sentiment,
                high_impact_news_count=len([n for n in scored_news if n.relevance > 0.7]),
                crisis_flags=summary.risk_adjustments.crisis_flags if hasattr(summary.risk_adjustments, 'crisis_flags') else []
            )
        except Exception:
            news_ctx = NewsContext(recent_sentiment_polarity=0.0, high_impact_news_count=0, crisis_flags=[])

        return PerceptionContext(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=int(time.time()),
            current_price=current_price,
            indicators=indicators,
            regime=regime,
            news=news_ctx,
            advisor_consensus="neutral",
            orderbook_imbalance=0.0,
            raw_data_refs={}
        )

perception_engine = PerceptionEngine()
