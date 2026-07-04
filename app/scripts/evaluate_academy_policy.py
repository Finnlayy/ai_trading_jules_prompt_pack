from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.scripts.academy_rl_runtime import require_python_311
from app.services.academy_policy.environment import AcademyMetaPolicyEnv


def main() -> None:
    require_python_311()

    parser = argparse.ArgumentParser(description="Evaluate an Academy PPO policy against the environment.")
    parser.add_argument("--model-dir", default="data/academy_policy/models/latest")
    parser.add_argument("--episodes", type=int, default=5)
    args = parser.parse_args()

    from stable_baselines3 import PPO

    model_dir = Path(args.model_dir)
    model = PPO.load(str(model_dir / "policy_sb3.zip"))
    rewards: list[float] = []

    for _ in range(args.episodes):
        env = AcademyMetaPolicyEnv(max_steps=64)
        obs, _ = env.reset()
        episode_reward = 0.0
        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, _ = env.step(action)
            episode_reward += float(reward)
            done = bool(terminated or truncated)
        rewards.append(episode_reward)

    report = {
        "episodes": args.episodes,
        "average_reward": sum(rewards) / len(rewards) if rewards else 0.0,
        "rewards": rewards,
    }
    (model_dir / "evaluation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
