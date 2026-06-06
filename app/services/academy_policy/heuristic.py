from __future__ import annotations

from app.schemas.academy import AcademyPolicyDecision, AcademyPolicyState
from app.services.academy_policy.actions import (
    ACADEMY_POLICY_SCOUT_NAMES,
    DRILL_PROFILES,
    default_raw_action,
    decode_action,
)
from app.services.ai.gem_agents import get_agent_definition


class AcademyHeuristicPolicy:
    def plan_cycle(
        self,
        state: AcademyPolicyState,
        *,
        count: int,
        mode: str,
        backend: str,
        fallback_reason: str | None = None,
    ) -> list[AcademyPolicyDecision]:
        decisions: list[AcademyPolicyDecision] = []
        scout_count = len(ACADEMY_POLICY_SCOUT_NAMES)
        for offset in range(max(1, count)):
            scout_index = offset % scout_count
            raw_action = self._raw_action_for_scout(scout_index, state)
            action = decode_action(raw_action)
            decisions.append(
                AcademyPolicyDecision(
                    mode=mode,
                    backend=backend,
                    source="heuristic",
                    action=action,
                    state_feature_version=state.feature_version,
                    fallback_reason=fallback_reason,
                    metadata={"coverage_offset": offset},
                )
            )
        return decisions

    def _raw_action_for_scout(self, scout_index: int, state: AcademyPolicyState) -> list[int]:
        raw = default_raw_action(scout_index)
        scout_name = ACADEMY_POLICY_SCOUT_NAMES[scout_index]
        definition = get_agent_definition(scout_name)
        drill_type = definition.drill_type if definition else "default"
        raw[1] = DRILL_PROFILES.index(drill_type) if drill_type in DRILL_PROFILES else 0

        base = scout_index * 14
        recent_accuracy = state.observation[base + 1] if len(state.observation) > base + 1 else 0.5
        completion = state.observation[base + 8] if len(state.observation) > base + 8 else 0.0
        pass_rate = state.observation[base + 9] if len(state.observation) > base + 9 else 0.0

        if recent_accuracy < 0.45:
            raw[2] = 0
            raw[4] = 1
            raw[5] = 1
        elif completion > 0.80 and pass_rate > 0.70:
            raw[2] = 2
            raw[4] = 2
            raw[5] = 2
        else:
            raw[2] = 1
            raw[4] = 0
            raw[5] = 0

        return raw
