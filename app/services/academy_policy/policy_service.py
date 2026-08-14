from __future__ import annotations

import platform
from typing import Any

from app.core.config import (
    ACADEMY_POLICY_BACKEND,
    ACADEMY_POLICY_CYCLE_DECISIONS,
    ACADEMY_POLICY_MODE,
    ACADEMY_POLICY_MODEL_DIR,
)
from app.schemas.academy import (
    AcademyPolicyDecision,
    AcademyPolicyPreviewRequest,
    AcademyPolicyState,
    AcademyPolicyStatus,
)
from app.services.academy_policy.actions import ACTION_SPACE_DIMS, ACADEMY_POLICY_SCOUT_NAMES
from app.services.academy_policy.heuristic import AcademyHeuristicPolicy
from app.services.academy_policy.logging import ACTION_LOG_FILE, append_many_jsonl
from app.services.academy_policy.onnx_runtime import AcademyOnnxPolicyRuntime
from app.services.academy_policy.state import OBSERVATION_SIZE, AcademyPolicyStateBuilder


class AcademyPolicyService:
    def __init__(self) -> None:
        self.state_builder = AcademyPolicyStateBuilder()
        self.heuristic = AcademyHeuristicPolicy()
        self._onnx_runtime: AcademyOnnxPolicyRuntime | None = None
        self.last_fallback_reason: str | None = None

    def build_state(self, training_status: dict[str, Any] | None = None) -> AcademyPolicyState:
        return self.state_builder.build_state(training_status=training_status)

    def plan_cycle(
        self,
        *,
        training_status: dict[str, Any] | None = None,
        count: int | None = None,
    ) -> list[AcademyPolicyDecision]:
        state = self.build_state(training_status)
        decision_count = max(1, min(count or int(ACADEMY_POLICY_CYCLE_DECISIONS), len(ACADEMY_POLICY_SCOUT_NAMES)))
        mode = ACADEMY_POLICY_MODE
        backend = ACADEMY_POLICY_BACKEND

        if mode == "ppo":
            ppo_decision = self._try_ppo_decision(state)
            if ppo_decision:
                return [ppo_decision]
            return self._heuristic_cycle(
                state,
                decision_count,
                mode=mode,
                backend="heuristic",
                fallback_reason=self.last_fallback_reason or "PPO_UNAVAILABLE",
            )

        if mode == "shadow":
            self._try_ppo_decision(state)
            return self._heuristic_cycle(
                state,
                decision_count,
                mode=mode,
                backend="heuristic",
                fallback_reason=self.last_fallback_reason,
            )

        return self._heuristic_cycle(state, decision_count, mode="heuristic", backend="heuristic")

    def preview(self, request: AcademyPolicyPreviewRequest) -> dict[str, Any]:
        decisions = self.plan_cycle(training_status=request.training_status, count=request.count)
        state = self.build_state(request.training_status)
        return {
            "state": state.model_dump(),
            "decisions": [decision.model_dump() for decision in decisions],
            "status": self.get_status().model_dump(),
        }

    def get_status(self) -> AcademyPolicyStatus:
        runtime = self._onnx_runtime
        active_model_id = runtime.model_id if runtime and runtime.available else None
        healthy = ACADEMY_POLICY_MODE in {"heuristic", "shadow"} or active_model_id is not None
        return AcademyPolicyStatus(
            mode=ACADEMY_POLICY_MODE,
            backend=ACADEMY_POLICY_BACKEND,
            healthy=healthy,
            fallback_available=True,
            active_model_id=active_model_id,
            model_dir=ACADEMY_POLICY_MODEL_DIR,
            last_fallback_reason=self.last_fallback_reason,
            scout_count=len(ACADEMY_POLICY_SCOUT_NAMES),
            observation_size=OBSERVATION_SIZE,
            action_space=list(ACTION_SPACE_DIMS),
            python_runtime=platform.python_version(),
        )

    async def log_decisions(self, decisions: list[AcademyPolicyDecision]) -> None:
        await append_many_jsonl(ACTION_LOG_FILE, [decision.model_dump() for decision in decisions])

    def _heuristic_cycle(
        self,
        state: AcademyPolicyState,
        count: int,
        *,
        mode: str,
        backend: str,
        fallback_reason: str | None = None,
    ) -> list[AcademyPolicyDecision]:
        return self.heuristic.plan_cycle(
            state,
            count=count,
            mode=mode,
            backend=backend,
            fallback_reason=fallback_reason,
        )

    def _try_ppo_decision(self, state: AcademyPolicyState) -> AcademyPolicyDecision | None:
        if ACADEMY_POLICY_BACKEND != "onnx":
            self.last_fallback_reason = "PPO_BACKEND_NOT_ACTIVE"
            return None

        runtime = self._onnx_runtime
        if runtime is None:
            runtime = AcademyOnnxPolicyRuntime(ACADEMY_POLICY_MODEL_DIR)
            self._onnx_runtime = runtime
        if not runtime.available and not runtime.load():
            self.last_fallback_reason = runtime.last_error or "ONNX_LOAD_FAILED"
            return None

        try:
            action = runtime.predict_action(state.observation)
        except Exception as exc:
            self.last_fallback_reason = f"ONNX_INFERENCE_FAILED: {exc}"
            return None

        self.last_fallback_reason = None
        return AcademyPolicyDecision(
            mode=ACADEMY_POLICY_MODE,
            backend="onnx",
            source="ppo",
            action=action,
            state_feature_version=state.feature_version,
            model_id=runtime.model_id,
            executed=ACADEMY_POLICY_MODE == "ppo",
        )


academy_policy_service = AcademyPolicyService()
