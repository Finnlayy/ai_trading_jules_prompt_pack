from __future__ import annotations

from typing import Any

from app.services.academy_policy.actions import ACTION_SPACE_DIMS, decode_action
from app.services.academy_policy.reward import AcademyPolicyRewardEngine
from app.services.academy_policy.state import OBSERVATION_SIZE, AcademyPolicyStateBuilder

try:
    import gymnasium as gym
    import numpy as np
    from gymnasium import spaces

    GYMNASIUM_AVAILABLE = True
except ImportError:
    gym = None
    np = None
    spaces = None
    GYMNASIUM_AVAILABLE = False


class AcademyMetaPolicyEnv(gym.Env if GYMNASIUM_AVAILABLE else object):
    metadata = {"render_modes": []}

    def __init__(self, max_steps: int = 64, training_status: dict[str, Any] | None = None) -> None:
        if not GYMNASIUM_AVAILABLE:
            raise RuntimeError("Gymnasium and NumPy are required for AcademyMetaPolicyEnv")
        self.max_steps = max_steps
        self.training_status = training_status or {}
        self.state_builder = AcademyPolicyStateBuilder()
        self.reward_engine = AcademyPolicyRewardEngine()
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(OBSERVATION_SIZE,), dtype=np.float32)
        self.action_space = spaces.MultiDiscrete(list(ACTION_SPACE_DIMS))
        self._step_count = 0
        self._mastery_score = 0.0

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self._step_count = 0
        self._mastery_score = 0.0
        observation = self._observation()
        return observation, {"feature_version": "academy_policy_state_v1"}

    def step(self, action):
        decoded = decode_action([int(value) for value in action])
        before = self._metrics()
        self._step_count += 1
        if not decoded.degraded:
            self._mastery_score = min(1.0, self._mastery_score + 0.01 * decoded.difficulty)
        after = self._metrics()
        reward = self.reward_engine.calculate(before, after, decoded)
        terminated = self._mastery_score >= 1.0
        truncated = self._step_count >= self.max_steps
        return self._observation(), reward.total_reward, terminated, truncated, {
            "action": decoded.model_dump(),
            "reward": reward.model_dump(),
            "step_count": self._step_count,
            "mastery_score": self._mastery_score,
        }

    def _observation(self):
        state = self.state_builder.build_state(self.training_status)
        obs = np.asarray(state.observation, dtype=np.float32)
        if self._mastery_score > 0:
            obs = obs.copy()
            obs[-2] = min(1.0, obs[-2] + self._mastery_score * 0.05)
        return obs

    def _metrics(self) -> dict[str, float]:
        state = self.state_builder.build_state(self.training_status)
        observation = state.observation
        average_accuracy = observation[-2] if len(observation) >= 2 else 0.5
        agreement_rate = observation[-8] if len(observation) >= 8 else 0.0
        diversity_health = 1.0 - abs(0.70 - agreement_rate)
        return {
            "accuracy": min(1.0, average_accuracy + self._mastery_score * 0.05),
            "calibration": min(1.0, average_accuracy + self._mastery_score * 0.03),
            "curriculum_progress": self._mastery_score,
            "ab_lift": self._mastery_score * 0.05,
            "specialization": self._mastery_score * 0.05,
            "diversity_health": max(0.0, diversity_health),
            "agreement_rate": agreement_rate,
        }
