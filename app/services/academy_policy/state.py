from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.academy import AcademyPolicyState
from app.services.ab_testing import ab_testing
from app.services.academy_curriculum import academy_curriculum
from app.services.academy_policy.actions import ACADEMY_POLICY_SCOUT_NAMES
from app.services.agent_registry import agent_registry
from app.services.confidence_registry import confidence_registry

SCOUT_FEATURES: tuple[str, ...] = (
    "accuracy",
    "recent_accuracy",
    "average_confidence",
    "calibration_score",
    "experience",
    "specialization_score",
    "total_calls",
    "current_streak",
    "curriculum_completion_ratio",
    "curriculum_pass_rate",
    "curriculum_average_confidence",
    "prompt_generation",
    "running_ab_test",
    "ab_lift",
)

GLOBAL_FEATURES: tuple[str, ...] = (
    "diversity_agreement_rate",
    "echo_warning_ratio",
    "divergent_warning_ratio",
    "cycle_count",
    "error_count",
    "night_window_active",
    "average_scout_accuracy",
    "weakest_scout_gap",
)

FEATURE_VERSION = "academy_policy_state_v1"
OBSERVATION_SIZE = len(ACADEMY_POLICY_SCOUT_NAMES) * len(SCOUT_FEATURES) + len(GLOBAL_FEATURES)


def clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


def _norm_count(value: float, cap: float) -> float:
    if cap <= 0:
        return 0.0
    return clamp01(float(value) / cap)


@dataclass(frozen=True)
class _ScoutAggregate:
    accuracy: float = 0.5
    recent_accuracy: float = 0.5
    average_confidence: float = 0.5
    experience: int = 0
    specialization_score: float = 0.0
    calls: int = 0


class AcademyPolicyStateBuilder:
    def __init__(self, scout_names: tuple[str, ...] = ACADEMY_POLICY_SCOUT_NAMES) -> None:
        self.scout_names = scout_names

    @property
    def feature_names(self) -> list[str]:
        names: list[str] = []
        for scout_name in self.scout_names:
            names.extend(f"{scout_name}.{feature}" for feature in SCOUT_FEATURES)
        names.extend(f"global.{feature}" for feature in GLOBAL_FEATURES)
        return names

    def build_state(self, training_status: dict[str, Any] | None = None) -> AcademyPolicyState:
        training_status = training_status or {}
        observation: list[float] = []
        accuracies: list[float] = []
        confidence_dump = confidence_registry.dump()
        ab_tests = ab_testing.get_all()

        for scout_name in self.scout_names:
            features = self._scout_features(scout_name, confidence_dump, ab_tests)
            observation.extend(features)
            accuracies.append(features[0])

        observation.extend(self._global_features(training_status, accuracies))
        observation = [clamp01(value) for value in observation]

        return AcademyPolicyState(
            feature_version=FEATURE_VERSION,
            scout_names=list(self.scout_names),
            feature_names=self.feature_names,
            observation=observation,
            observation_size=len(observation),
            metadata={"expected_observation_size": OBSERVATION_SIZE},
        )

    def _scout_features(self, scout_name: str, confidence_dump: dict[str, Any], ab_tests: list[Any]) -> list[float]:
        identity = agent_registry.get_identity(scout_name)
        aggregate = self._confidence_aggregate(scout_name, confidence_dump)
        curriculum = academy_curriculum.get_all_for_scout(scout_name)

        total_required = sum(max(progress.required_drills, 0) for progress in curriculum)
        total_completed = sum(max(progress.completed_drills, 0) for progress in curriculum)
        total_passed = sum(max(progress.passed_drills, 0) for progress in curriculum)
        curriculum_conf = self._weighted_curriculum_confidence(curriculum)

        identity_accuracy = identity.accuracy if identity and identity.total_calls > 0 else 0.5
        accuracy = aggregate.accuracy if aggregate.calls > 0 else identity_accuracy
        avg_confidence = aggregate.average_confidence
        calibration = 1.0 - abs(accuracy - avg_confidence)
        total_calls = aggregate.calls or (identity.total_calls if identity else 0)
        experience = aggregate.experience or total_calls
        current_streak = identity.current_streak if identity else 0
        prompt_generation = identity.generation if identity else 1
        running_ab, ab_lift = self._ab_features(scout_name, ab_tests)

        return [
            clamp01(accuracy),
            clamp01(aggregate.recent_accuracy if aggregate.calls > 0 else identity_accuracy),
            clamp01(avg_confidence),
            clamp01(calibration),
            _norm_count(experience, 1000.0),
            clamp01(aggregate.specialization_score),
            _norm_count(total_calls, 1000.0),
            _norm_count(current_streak, 50.0),
            clamp01(total_completed / total_required) if total_required else 0.0,
            clamp01(total_passed / total_completed) if total_completed else 0.0,
            clamp01(curriculum_conf),
            _norm_count(prompt_generation, 20.0),
            1.0 if running_ab else 0.0,
            clamp01(ab_lift),
        ]

    def _confidence_aggregate(self, scout_name: str, dumped: dict[str, Any]) -> _ScoutAggregate:
        calls = 0
        correct = 0
        confidence_sum = 0.0
        experience = 0
        specialization_sum = 0.0
        recent_results: list[bool] = []

        for symbol_data in dumped.values():
            stats = symbol_data.get("scout_stats", {}).get(scout_name)
            if not stats:
                continue
            scout_calls = int(stats.get("calls", 0) or 0)
            calls += scout_calls
            correct += int(stats.get("correct_calls", 0) or 0)
            confidence_sum += float(stats.get("avg_confidence", 0.5) or 0.5) * scout_calls
            experience += int(stats.get("experience", 0) or 0)
            specialization_sum += float(stats.get("specialization_score", 0.0) or 0.0) * max(scout_calls, 1)
            recent_results.extend(bool(value) for value in stats.get("last_5_results", [])[-5:])

        if calls <= 0:
            return _ScoutAggregate()

        accuracy = correct / calls
        recent = sum(recent_results) / len(recent_results) if recent_results else accuracy
        avg_confidence = confidence_sum / calls if calls else 0.5
        specialization = specialization_sum / max(calls, 1)

        return _ScoutAggregate(
            accuracy=accuracy,
            recent_accuracy=recent,
            average_confidence=avg_confidence,
            experience=experience,
            specialization_score=specialization,
            calls=calls,
        )

    def _weighted_curriculum_confidence(self, curriculum: list[Any]) -> float:
        total_completed = sum(max(progress.completed_drills, 0) for progress in curriculum)
        if total_completed <= 0:
            return 0.0
        weighted = sum(progress.average_confidence * max(progress.completed_drills, 0) for progress in curriculum)
        return weighted / total_completed

    def _ab_features(self, scout_name: str, ab_tests: list[Any]) -> tuple[bool, float]:
        tests = [test for test in ab_tests if test.scout_name == scout_name]
        if not tests:
            return False, 0.0
        running = any(test.status == "running" for test in tests)
        latest = tests[-1]
        acc_a = latest.correct_a / latest.calls_a if latest.calls_a else 0.0
        acc_b = latest.correct_b / latest.calls_b if latest.calls_b else 0.0
        return running, max(0.0, acc_b - acc_a)

    def _global_features(self, training_status: dict[str, Any], accuracies: list[float]) -> list[float]:
        diversity = training_status.get("diversity", {}) if isinstance(training_status, dict) else {}
        total_evaluations = float(diversity.get("total_evaluations", 0) or 0)
        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0.5
        weakest = min(accuracies) if accuracies else 0.5

        return [
            clamp01(float(diversity.get("agreement_rate", 0.0) or 0.0)),
            _norm_count(float(diversity.get("high_agreement_warnings", 0) or 0), max(total_evaluations, 1.0)),
            _norm_count(float(diversity.get("low_agreement_warnings", 0) or 0), max(total_evaluations, 1.0)),
            _norm_count(float(training_status.get("cycles_completed", 0) or 0), 1000.0),
            _norm_count(float(training_status.get("errors_last_5min", 0) or 0), 20.0),
            1.0 if training_status.get("is_night_time") else 0.0,
            clamp01(avg_accuracy),
            clamp01(avg_accuracy - weakest),
        ]
