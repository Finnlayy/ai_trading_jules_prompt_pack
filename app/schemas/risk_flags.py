from enum import Enum
from pydantic import BaseModel

class SeverityEnum(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class SourceEnum(str, Enum):
    M8 = "M8"
    RISK_ENGINE = "RISK_ENGINE"
    AI_REVIEW = "AI_REVIEW"
    BROKER_SIM = "BROKER_SIM"
    DATA_PIPELINE = "DATA_PIPELINE"

class ActionEnum(str, Enum):
    LOG_ONLY = "LOG_ONLY"
    REDUCE_SIZE = "REDUCE_SIZE"
    REJECT = "REJECT"
    HALT_SIMULATION = "HALT_SIMULATION"
    HUMAN_REVIEW = "HUMAN_REVIEW"

class RiskFlag(BaseModel):
    flag_code: str
    severity: SeverityEnum
    source: SourceEnum
    evidence: str
    action: ActionEnum
