"""Pydantic schema for the /api/webhook/signal endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WebhookSignalPayload(BaseModel):
    """Incoming trading signal from external sources (TradingView, bots, etc.)."""

    symbol: str = Field(..., min_length=1, max_length=20, description="Trading pair symbol, e.g. SOLUSD")
    direction: str = Field(..., pattern=r"^(BUY|SELL|LONG|SHORT)$", description="Signal direction")
    price: float | None = Field(default=None, gt=0, description="Entry price if known")
    volume: float | None = Field(default=None, gt=0, description="Suggested order volume")
    timestamp: str | None = Field(default=None, description="ISO timestamp from source")


class WebhookSignalResponse(BaseModel):
    """Acknowledgement response for a received signal."""

    status: str = "ok"
    signal_id: str
    message: str | None = None
