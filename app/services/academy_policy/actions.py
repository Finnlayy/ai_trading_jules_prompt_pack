from __future__ import annotations

from collections.abc import Sequence

from app.schemas.academy import AcademyPolicyAction
from app.services.ai.gem_agents import DEFAULT_AGENT_NAMES

ACADEMY_POLICY_SCOUT_NAMES: tuple[str, ...] = tuple(DEFAULT_AGENT_NAMES)

DRILL_PROFILES: tuple[str, ...] = (
    "default",
    "pattern_recognition",
    "sentiment_analysis",
    "crisis_detection",
    "regime_identification",
    "execution_quality",
    "correlation_risk",
    "market_quality",
    "strategy_code_review",
    "payload_validation",
)
PROMPT_ACTIONS: tuple[str, ...] = (
    "keep",
    "create_candidate",
    "start_ab_test",
    "promote_winner",
    "rollback_loser",
)
CURRICULUM_ACTIONS: tuple[str, ...] = (
    "hold",
    "remediate",
    "advance_if_ready",
    "repeat_weak_topic",
)
SAMPLING_STRATEGIES: tuple[str, ...] = (
    "balanced",
    "weak_first",
    "specialist_first",
    "diversity_first",
)
AB_ALLOCATIONS: tuple[str, ...] = ("fifty_fifty", "favor_a", "favor_b")
EVOLUTION_ACTIONS: tuple[str, ...] = ("none", "propose_evolution", "quarantine_prompt")

ACTION_SPACE_DIMS: tuple[int, ...] = (
    len(ACADEMY_POLICY_SCOUT_NAMES),
    len(DRILL_PROFILES),
    4,
    len(PROMPT_ACTIONS),
    len(CURRICULUM_ACTIONS),
    len(SAMPLING_STRATEGIES),
    len(AB_ALLOCATIONS),
    len(EVOLUTION_ACTIONS),
)


def default_raw_action(scout_index: int = 0) -> list[int]:
    safe_index = max(0, min(len(ACADEMY_POLICY_SCOUT_NAMES) - 1, scout_index))
    return [safe_index, 0, 0, 0, 0, 0, 0, 0]


def _read_index(raw: Sequence[int], position: int, limit: int) -> tuple[int, bool]:
    try:
        value = int(raw[position])
    except (IndexError, TypeError, ValueError):
        return 0, True
    if value < 0 or value >= limit:
        return 0, True
    return value, False


def decode_action(raw_action: Sequence[int]) -> AcademyPolicyAction:
    degraded = len(raw_action) != len(ACTION_SPACE_DIMS)
    padded = list(raw_action[: len(ACTION_SPACE_DIMS)])
    while len(padded) < len(ACTION_SPACE_DIMS):
        padded.append(0)

    indexes: list[int] = []
    for pos, limit in enumerate(ACTION_SPACE_DIMS):
        idx, invalid = _read_index(padded, pos, limit)
        degraded = degraded or invalid
        indexes.append(idx)

    fallback_reason = "INVALID_ACTION_DEGRADED" if degraded else None
    scout_index = indexes[0]
    drill_profile = DRILL_PROFILES[indexes[1]]

    return AcademyPolicyAction(
        raw_action=[int(value) for value in padded],
        scout_index=scout_index,
        scout_name=ACADEMY_POLICY_SCOUT_NAMES[scout_index],
        drill_profile=drill_profile,
        difficulty=indexes[2] + 1,
        prompt_action=PROMPT_ACTIONS[indexes[3]],
        curriculum_action=CURRICULUM_ACTIONS[indexes[4]],
        sampling_strategy=SAMPLING_STRATEGIES[indexes[5]],
        ab_allocation=AB_ALLOCATIONS[indexes[6]],
        evolution_action=EVOLUTION_ACTIONS[indexes[7]],
        degraded=degraded,
        fallback_reason=fallback_reason,
    )
