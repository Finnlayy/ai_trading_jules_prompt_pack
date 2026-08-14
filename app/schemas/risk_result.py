from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class RiskValidationResult(BaseModel):
    decision: str  # "PROCEED_TO_SIMULATION", "REJECT", "HUMAN_REVIEW"
    reject_reason: Optional[str] = None
    risk_score: float
    violated_rules: List[str] = Field(default_factory=list)
    allowed_size: float
    risk_adjusted_plan: Optional[Dict[str, Any]] = None
