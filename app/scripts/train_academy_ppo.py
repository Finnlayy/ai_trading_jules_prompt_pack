from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from app.scripts.academy_rl_runtime import require_python_311
from app.services.academy_policy.actions import ACTION_SPACE_DIMS, ACADEMY_POLICY_SCOUT_NAMES
from app.services.academy_policy.environment import AcademyMetaPolicyEnv
from app.services.academy_policy.state import FEATURE_VERSION, OBSERVATION_SIZE


def main() -> None:
    require_python_311()

    parser = argparse.ArgumentParser(description="Train the Academy PPO meta-policy.")
    parser.add_argument("--timesteps", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="data/academy_policy/models/latest")
    args = parser.parse_args()

    from stable_baselines3 import PPO

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    env = AcademyMetaPolicyEnv(max_steps=64)
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        n_steps=256,
        batch_size=64,
        gamma=0.97,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        seed=args.seed,
        verbose=1,
    )
    model.learn(total_timesteps=args.timesteps)
    model_path = output_dir / "policy_sb3.zip"
    model.save(str(model_path))

    manifest = {
        "model_id": str(uuid4()),
        "backend": "stable-baselines3",
        "feature_version": FEATURE_VERSION,
        "observation_size": OBSERVATION_SIZE,
        "action_space": list(ACTION_SPACE_DIMS),
        "scout_names": list(ACADEMY_POLICY_SCOUT_NAMES),
        "timesteps": args.timesteps,
        "seed": args.seed,
        "model_path": str(model_path),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
