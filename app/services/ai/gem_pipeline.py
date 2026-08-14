from __future__ import annotations

from typing import Any

from app.services.ai.gem_agents import GEM_AGENT_DEFINITIONS, AgentDefinition


LIVE_TRADE_EVALUATION = "live_trade_evaluation"
STRATEGY_REVIEW = "strategy_review"
PIONEX_DEPLOYMENT = "pionex_deployment"
BACKTEST_AREA = "backtest_area"
LEARNING_META_CIRCLE = "learning_meta_circle"

GEM_PIPELINE_MODE_PHASES: dict[str, tuple[int, ...]] = {
    LIVE_TRADE_EVALUATION: (1, 2, 3, 4, 5, 6, 8, 9),
    STRATEGY_REVIEW: (1, 2, 3, 4, 5, 6, 7),
    PIONEX_DEPLOYMENT: (7, 8),
    BACKTEST_AREA: (2, 3, 4, 5, 6, 10),
    LEARNING_META_CIRCLE: (9, 10),
}

GEM_PIPELINE_OUTPUT_CONTRACTS: dict[str, str] = {
    LIVE_TRADE_EVALUATION: "SignalReview",
    STRATEGY_REVIEW: "StrategyReview",
    PIONEX_DEPLOYMENT: "PionexWebhookReadinessReview",
    BACKTEST_AREA: "BacktestLearningReview",
    LEARNING_META_CIRCLE: "LearningMetaReview",
}

GEM_PIPELINE_ALLOWED_ACTIONS: dict[str, tuple[str, ...]] = {
    LIVE_TRADE_EVALUATION: (
        "return_signal_review",
        "request_human_review",
        "write_learning_feedback",
    ),
    STRATEGY_REVIEW: (
        "return_strategy_review",
        "request_missing_assumptions",
        "write_learning_feedback",
    ),
    PIONEX_DEPLOYMENT: (
        "validate_pine_script",
        "validate_pionex_payload_shape",
        "request_human_review",
    ),
    BACKTEST_AREA: (
        "summarize_backtest",
        "identify_regime_fit",
        "write_learning_feedback",
    ),
    LEARNING_META_CIRCLE: (
        "summarize_execution_outcomes",
        "suggest_prompt_or_strategy_adjustments",
        "write_learning_feedback",
    ),
}

_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "passphrase",
    "authorization",
    "signature",
    "webhook_secret",
    "private_key",
)


def redact_secret_context(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return "[DEPTH_LIMIT]"
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            lower = key_str.lower()
            if any(part in lower for part in _SENSITIVE_KEY_PARTS):
                redacted[key_str] = "[REDACTED]"
            else:
                redacted[key_str] = redact_secret_context(item, depth + 1)
        return redacted
    if isinstance(value, list):
        return [redact_secret_context(item, depth + 1) for item in value[:100]]
    if isinstance(value, tuple):
        return [redact_secret_context(item, depth + 1) for item in value[:100]]
    if isinstance(value, str):
        return value if len(value) <= 4000 else value[:4000] + "...[TRUNCATED]"
    return value


class GemInputRouter:
    """Routes variable backend inputs to the Gem phase set they actually need."""

    def resolve_mode(self, requested_mode: str, context: dict[str, Any] | None = None) -> str:
        mode = (requested_mode or "auto").strip().lower()
        if mode in GEM_PIPELINE_MODE_PHASES:
            return mode
        return self._infer_mode(context or {})

    def phase_ids_for_mode(self, mode: str) -> tuple[int, ...]:
        resolved = self.resolve_mode(mode)
        return GEM_PIPELINE_MODE_PHASES[resolved]

    def definitions_for_mode(self, mode: str) -> tuple[AgentDefinition, ...]:
        phase_ids = set(self.phase_ids_for_mode(mode))
        return tuple(
            definition
            for definition in GEM_AGENT_DEFINITIONS
            if definition.phase_id in phase_ids
        )

    def output_contract_for_mode(self, mode: str, override: str | None = None) -> str:
        if override:
            return override
        resolved = self.resolve_mode(mode)
        return GEM_PIPELINE_OUTPUT_CONTRACTS[resolved]

    def allowed_actions_for_mode(self, mode: str) -> tuple[str, ...]:
        resolved = self.resolve_mode(mode)
        return GEM_PIPELINE_ALLOWED_ACTIONS[resolved]

    @staticmethod
    def _infer_mode(context: dict[str, Any]) -> str:
        keys = {str(key).lower() for key in context.keys()}
        text = " ".join(keys)
        explicit = str(context.get("type") or context.get("kind") or context.get("area") or "").lower()
        haystack = f"{explicit} {text}"

        if "live_trade" in haystack or "trade_evaluation" in haystack or "m8" in haystack or "signal" in haystack:
            return LIVE_TRADE_EVALUATION
        if "pionex" in haystack or "webhook" in haystack or "pionex_payload" in haystack:
            return PIONEX_DEPLOYMENT
        if "backtest" in haystack or "equity_curve" in haystack or "optimizer" in haystack:
            return BACKTEST_AREA
        if "learning" in haystack or "outcome" in haystack or "pnl" in haystack or "journal" in haystack:
            return LEARNING_META_CIRCLE
        if "strategy" in haystack or "pinescript" in haystack or "pine_script" in haystack:
            return STRATEGY_REVIEW
        return LIVE_TRADE_EVALUATION
