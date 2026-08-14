from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


GemPipelineMode = Literal[
    "auto",
    "live_trade_evaluation",
    "strategy_review",
    "pionex_deployment",
    "backtest_area",
    "learning_meta_circle",
]


class GemPipelineRequest(BaseModel):
    mode: GemPipelineMode = Field(
        default="auto",
        description="Input-router mode. Use auto to infer the phase set from supplied context.",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="User-supplied, non-secret analysis context for the selected Gem pipeline.",
    )
    symbol: str | None = Field(default=None, max_length=32)
    direction: str | None = Field(default=None, max_length=16)
    output_contract: str | None = Field(
        default=None,
        max_length=80,
        description="Optional expected final output contract for the orchestrator.",
    )
    return_prompt_only: bool = Field(
        default=False,
        description="Return generated prompts and backend context without calling the provider.",
    )


class GemPipelineResponse(BaseModel):
    status: str = "ok"
    engine: str = "gem10_native"
    provider: str
    requested_mode: str
    mode: str
    selected_phases: list[int]
    selected_gems: list[str]
    allowed_actions: list[str]
    output_contract: str
    used_llm: bool
    decision: str
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    summary: str
    gem_reports: dict[str, dict[str, Any]] = Field(default_factory=dict)
    backend_context: dict[str, Any] = Field(default_factory=dict)
    generated_prompts: dict[str, dict[str, str]] = Field(default_factory=dict)
