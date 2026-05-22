from pydantic import BaseModel, Field
from typing import Optional

class M8Payload(BaseModel):
    signal_id: str
    symbol: str
    timeframe: str
    direction: str = Field(pattern="^(LONG|SHORT)$")
    intent: str = Field(default="ENTRY", pattern="^(ENTRY|CLOSE)$")
    account_mode: str = Field(default="SPOT", pattern="^(SPOT|FUTURES)$")
    timestamp: str
    entry_price: float
    stop_price: float
    target_price: float
    confluence_score: float = Field(ge=0.0, le=100.0)
    relative_volume: Optional[float] = None
    crisis_score: float = Field(ge=0.0, le=100.0)
    mc_dispersion: float = Field(ge=0.0)
    spread: float = Field(ge=0.0)
    leverage: Optional[float] = Field(default=None, gt=0.0)
    execution_quantity: Optional[float] = Field(default=None, gt=0.0)
    order_command: str = Field(default="GO", pattern="^(GO|HOLD|KILL)$")
    market_regime: Optional[str] = Field(default=None, pattern="^(GREEN|YELLOW|ORANGE|RED)$")
    bar_confirmed: bool = True
    chop_index: Optional[float] = Field(default=None, ge=0.0)
    hurst_exponent: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    macro_event_risk: bool = False
    drawdown_pct: Optional[float] = Field(default=None, ge=0.0)
    pending_order_age_seconds: Optional[float] = Field(default=None, ge=0.0)
    max_pending_order_age_seconds: Optional[float] = Field(default=None, gt=0.0)
    m8_reject_reason: Optional[str] = None
