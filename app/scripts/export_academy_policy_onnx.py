from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.scripts.academy_rl_runtime import require_python_311
from app.services.academy_policy.actions import ACTION_SPACE_DIMS, ACADEMY_POLICY_SCOUT_NAMES
from app.services.academy_policy.state import FEATURE_VERSION, OBSERVATION_SIZE


def main() -> None:
    require_python_311()

    parser = argparse.ArgumentParser(description="Export an Academy PPO SB3 policy to ONNX.")
    parser.add_argument("--model-dir", default="data/academy_policy/models/latest")
    parser.add_argument("--output-dir", default="data/academy_policy/models/active")
    args = parser.parse_args()

    import torch
    from stable_baselines3 import PPO

    source_dir = Path(args.model_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model = PPO.load(str(source_dir / "policy_sb3.zip"))

    class OnnxablePolicy(torch.nn.Module):
        def __init__(self, policy):
            super().__init__()
            self.policy = policy

        def forward(self, observation):
            actions, _, _ = self.policy(observation, deterministic=True)
            return actions

    onnx_policy = OnnxablePolicy(model.policy)
    dummy = torch.zeros((1, OBSERVATION_SIZE), dtype=torch.float32)
    onnx_path = output_dir / "policy.onnx"
    torch.onnx.export(
        onnx_policy,
        dummy,
        str(onnx_path),
        input_names=["observation"],
        output_names=["raw_action"],
        opset_version=17,
        dynamo=False,
    )

    manifest = json.loads((source_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(
        {
            "backend": "onnx",
            "feature_version": FEATURE_VERSION,
            "observation_size": OBSERVATION_SIZE,
            "action_space": list(ACTION_SPACE_DIMS),
            "scout_names": list(ACADEMY_POLICY_SCOUT_NAMES),
            "onnx_path": str(onnx_path),
        }
    )
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
