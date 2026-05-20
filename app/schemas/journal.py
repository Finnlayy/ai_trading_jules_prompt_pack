from enum import Enum
from pydantic import BaseModel
from typing import Optional, Any, Dict

class DirectionEnum(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class DecisionEnum(str, Enum):
    PROCEED_TO_SIMULATION = "PROCEED_TO_SIMULATION"
    REJECT = "REJECT"
    HUMAN_REVIEW = "HUMAN_REVIEW"

class FinalDecisionEnum(str, Enum):
    EXECUTED_SIM = "EXECUTED_SIM"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"

class TradeJournalEntry(BaseModel):
    trade_id: str
    timestamp: str
    symbol: str
    timeframe: str
    direction: DirectionEnum
    entry_price: float
    stop_price: float
    target_price: float
    risk_reward: float
    m8_score: float
    ai_decision: DecisionEnum
    final_decision: FinalDecisionEnum
    simulated_fill: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
