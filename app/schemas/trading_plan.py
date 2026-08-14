from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class PlanSetup(BaseModel):
    market_conditions: str
    regime: str
    sentiment: str
    volatility: str
    structure: str

class PlanTrigger(BaseModel):
    entry_condition: str
    price_zone_min: float
    price_zone_max: float
    timeframe: str
    confirmation_rule: str

class PlanInvalidation(BaseModel):
    hard_stop_price: float
    thesis_invalidated_condition: str
    max_loss_pct: float

class PlanRiskIntent(BaseModel):
    target_size_usd: float
    risk_reward_ratio: float
    leverage_desired: float
    confidence_score: float

class TradingPlan(BaseModel):
    setup: PlanSetup
    trigger: PlanTrigger
    invalidation: PlanInvalidation
    risk_intent: PlanRiskIntent
    evidence: Dict[str, str] = Field(default_factory=dict) # e.g. "news": "...", "chart": "..."
    direction: str # "LONG" or "SHORT"
