from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class IndicatorState(BaseModel):
    name: str
    value: float
    signal: str  # "bullish", "bearish", "neutral"

class RegimeContext(BaseModel):
    market_regime: str
    volatility: str
    trend_strength: float

class NewsContext(BaseModel):
    recent_sentiment_polarity: float
    high_impact_news_count: int
    crisis_flags: List[str] = Field(default_factory=list)

class PerceptionContext(BaseModel):
    symbol: str
    timeframe: str
    timestamp: int
    current_price: float
    indicators: List[IndicatorState] = Field(default_factory=list)
    regime: RegimeContext
    news: NewsContext
    advisor_consensus: Optional[str] = None
    orderbook_imbalance: Optional[float] = None
    raw_data_refs: Dict[str, Any] = Field(default_factory=dict)
