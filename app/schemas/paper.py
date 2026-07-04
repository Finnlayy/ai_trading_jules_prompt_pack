from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PaperReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(default="HYPEUSDT")
    timeframe: str = Field(default="1m")
    bars: int = Field(default=500)
    max_signals: Optional[int] = Field(default=20)
    min_confluence: Optional[float] = Field(default=None)
    max_holding_bars: int = Field(default=50)
    use_ai: bool = Field(default=True)


class PaperSessionStartRequest(PaperReplayRequest):
    poll_interval_seconds: float = Field(default=60.0, ge=5.0)
    run_once: bool = Field(default=True)
