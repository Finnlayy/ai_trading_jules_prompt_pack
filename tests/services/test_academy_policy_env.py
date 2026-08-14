from __future__ import annotations

import pytest

from app.services.academy_policy.environment import GYMNASIUM_AVAILABLE


@pytest.mark.skipif(not GYMNASIUM_AVAILABLE, reason="Gymnasium is only installed in the Python 3.11 RL venv")
def test_academy_meta_policy_env_reset_and_step():
    from app.services.academy_policy.environment import AcademyMetaPolicyEnv

    env = AcademyMetaPolicyEnv(max_steps=2)
    observation, info = env.reset(seed=42)
    assert observation.shape == env.observation_space.shape
    assert info["feature_version"] == "academy_policy_state_v1"

    action = env.action_space.sample()
    next_observation, reward, terminated, truncated, step_info = env.step(action)
    assert next_observation.shape == env.observation_space.shape
    assert isinstance(float(reward), float)
    assert terminated in {True, False}
    assert truncated in {True, False}
    assert "reward" in step_info
