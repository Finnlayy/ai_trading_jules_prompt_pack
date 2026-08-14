from __future__ import annotations

import sys

import pytest

from app.scripts.academy_rl_runtime import require_python_311
from app.services.academy_policy.actions import (
    ACTION_SPACE_DIMS,
    ACADEMY_POLICY_SCOUT_NAMES,
    decode_action,
)
from app.services.academy_policy.reward import AcademyPolicyRewardEngine
from app.services.academy_policy.state import OBSERVATION_SIZE, AcademyPolicyStateBuilder
from app.services.ai.gem_agents import DEFAULT_AGENT_NAMES


def test_policy_scouts_cover_all_default_agents():
    assert ACADEMY_POLICY_SCOUT_NAMES == DEFAULT_AGENT_NAMES
    assert len(ACADEMY_POLICY_SCOUT_NAMES) == 16
    assert ACTION_SPACE_DIMS[0] == 16


def test_state_builder_creates_stable_232_feature_observation():
    state = AcademyPolicyStateBuilder().build_state(
        {
            "is_night_time": True,
            "cycles_completed": 3,
            "errors_last_5min": 0,
            "diversity": {"agreement_rate": 0.7, "total_evaluations": 10},
        }
    )

    assert state.observation_size == OBSERVATION_SIZE == 232
    assert len(state.observation) == 232
    assert len(state.feature_names) == 232
    assert state.scout_names == list(DEFAULT_AGENT_NAMES)
    assert all(0.0 <= value <= 1.0 for value in state.observation)


def test_action_decoder_degrades_invalid_action_to_safe_defaults():
    action = decode_action([99, 99])

    assert action.degraded is True
    assert action.fallback_reason == "INVALID_ACTION_DEGRADED"
    assert action.scout_name == ACADEMY_POLICY_SCOUT_NAMES[0]
    assert action.drill_profile == "default"
    assert action.prompt_action == "keep"
    assert action.difficulty == 1


def test_reward_engine_rewards_learning_and_penalizes_invalid_actions():
    valid = decode_action([0, 0, 1, 0, 0, 0, 0, 0])
    invalid = decode_action([99])
    engine = AcademyPolicyRewardEngine()

    positive = engine.calculate(
        {"accuracy": 0.50, "calibration": 0.50, "curriculum_progress": 0.20, "agreement_rate": 0.70},
        {
            "accuracy": 0.60,
            "calibration": 0.60,
            "curriculum_progress": 0.30,
            "ab_lift": 0.05,
            "specialization": 0.10,
            "diversity_health": 1.0,
            "agreement_rate": 0.70,
        },
        valid,
    )
    negative = engine.calculate(
        {"accuracy": 0.60, "calibration": 0.60, "curriculum_progress": 0.30, "agreement_rate": 0.95},
        {"accuracy": 0.50, "calibration": 0.50, "curriculum_progress": 0.25, "agreement_rate": 0.95},
        invalid,
    )

    assert positive.total_reward > 0
    assert negative.invalid_action_penalty == 1.0
    assert negative.total_reward < positive.total_reward


def test_rl_scripts_require_python_311(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 14, 0))

    with pytest.raises(SystemExit, match="Academy PPO requires Python 3.11"):
        require_python_311()
