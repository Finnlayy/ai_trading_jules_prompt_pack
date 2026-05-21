from pydantic import BaseModel, Field
from typing import Optional

class M8Payload(BaseModel):
    signal_id: str
    symbol: str
    timeframe: str
    direction: str = Field(pattern="^(LONG|SHORT)$")
    timestamp: str
    entry_price: float
    stop_price: float
    target_price: float
    confluence_score: float = Field(ge=0.0, le=100.0)
    relative_volume: Optional[float] = None
    crisis_score: float = Field(ge=0.0, le=100.0)
    mc_dispersion: float = Field(ge=0.0)
    spread: float = Field(ge=0.0)
    m8_reject_reason: Optional[str] = None
