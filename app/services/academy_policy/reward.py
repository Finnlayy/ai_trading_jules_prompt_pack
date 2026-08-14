from __future__ import annotations

from typing import Any

from app.schemas.academy import AcademyPolicyAction, AcademyPolicyRewardBreakdown


def _clamp(value: float, low: float = -3.0, high: float = 3.0) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


def _metric(metrics: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(metrics.get(key, default))
    except (TypeError, ValueError):
        return default


class AcademyPolicyRewardEngine:
    def calculate(
        self,
        before: dict[str, Any],
        after: dict[str, Any],
        action: AcademyPolicyAction | None = None,
    ) -> AcademyPolicyRewardBreakdown:
        accuracy_delta = _metric(after, "accuracy") - _metric(before, "accuracy")
        calibration_delta = _metric(after, "calibration") - _metric(before, "calibration")
        curriculum_delta = _metric(after, "curriculum_progress") - _metric(before, "curriculum_progress")
        ab_lift = _metric(after, "ab_lift") - _metric(before, "ab_lift")
        specialization_delta = _metric(after, "specialization") - _metric(before, "specialization")
        diversity_health = _metric(after, "diversity_health", _metric(before, "diversity_health", 0.0))
        agreement_rate = _metric(after, "agreement_rate", 0.0)

        echo_penalty = max(0.0, agreement_rate - 0.90)
        divergence_penalty = max(0.0, 0.50 - agreement_rate) if agreement_rate > 0 else 0.0
        regression_penalty = max(0.0, -accuracy_delta)
        invalid_action_penalty = 1.0 if action and action.degraded else 0.0

        total = (
            1.20 * accuracy_delta
            + 0.90 * calibration_delta
            + 0.70 * curriculum_delta
            + 0.60 * ab_lift
            + 0.45 * specialization_delta
            + 0.25 * diversity_health
            - 0.80 * echo_penalty
            - 0.60 * divergence_penalty
            - 0.60 * regression_penalty
            - 0.35 * invalid_action_penalty
        )

        return AcademyPolicyRewardBreakdown(
            accuracy_delta=accuracy_delta,
            calibration_delta=calibration_delta,
            curriculum_delta=curriculum_delta,
            ab_lift=ab_lift,
            specialization_delta=specialization_delta,
            diversity_health=diversity_health,
            echo_penalty=echo_penalty,
            divergence_penalty=divergence_penalty,
            regression_penalty=regression_penalty,
            invalid_action_penalty=invalid_action_penalty,
            total_reward=_clamp(total),
        )
