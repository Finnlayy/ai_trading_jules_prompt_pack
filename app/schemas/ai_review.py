from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class DecisionEnum(str, Enum):
    PROCEED_TO_SIMULATION = "PROCEED_TO_SIMULATION"
    REJECT = "REJECT"
    HUMAN_REVIEW = "HUMAN_REVIEW"

class SignalReview(BaseModel):
    explanation: str = ""
    scout_explanations: dict = Field(default_factory=dict)
    schema_version: str
    signal_id: str
    decision: DecisionEnum
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: List[str]
    risk_flags: List[str]
    reject_reason: Optional[str] = None
    requires_human_review: bool
    audit_trace: Optional[Dict[str, Any]] = None
