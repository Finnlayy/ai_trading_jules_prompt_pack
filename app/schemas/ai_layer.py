from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AIBehaviorProfile(BaseModel):
    trading_style: str = "balanced"
    risk_tolerance: str = "moderate"
    preferred_symbols: list[str] = Field(default_factory=list)
    blocked_symbols: list[str] = Field(default_factory=list)
    max_risk_pct: float | None = Field(default=None, gt=0.0)
    min_confluence_preference: float | None = Field(default=None, ge=0.0, le=100.0)
    notes: str = ""
    guardrails: list[str] = Field(
        default_factory=lambda: [
            "Do not bypass deterministic risk gates.",
            "Do not request live execution directly.",
            "Prefer human review when confidence is low or preferences conflict.",
        ]
    )
    updated_at: str = Field(default_factory=utc_now)


class AIChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str = Field(default_factory=utc_now)


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=100000)
    apply_to_profile: bool = True
    chart_context: dict[str, Any] | None = Field(default=None, description="Optional market data snapshot (symbol, timeframe, recent candles, indicators) for AI analysis.")
    bars_count: int = Field(default=50, ge=10, le=300, description="Number of recent bars to include in chart_context.")
    strategy_context: str | None = Field(default=None, description="Name of the mounted strategy (Pine Script or Python) to include in AI context.")
    return_prompt_only: bool = Field(default=False, description="If true, return the generated prompt without calling the LLM.")


class AIChatResponse(BaseModel):
    reply: str
    provider: str
    used_llm: bool
    profile: AIBehaviorProfile
    memory: list[AIChatMessage]
    truncated: bool | None = Field(default=None, description="True if the user message was truncated due to length limits.")
    raw_profile_patch: dict[str, Any] = Field(default_factory=dict)
    recommended_action: dict[str, Any] | None = Field(default=None, description="Action recommended by the assistant (e.g., run_backtest, trigger_drill, etc.)")
    generated_prompt: str | None = Field(default=None, description="The full prompt that was sent to the LLM.")
    system_prompt: str | None = Field(default=None, description="The system prompt used for the LLM call.")
