from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.academy_policy.actions import ACTION_SPACE_DIMS, ACADEMY_POLICY_SCOUT_NAMES, decode_action
from app.services.academy_policy.state import FEATURE_VERSION, OBSERVATION_SIZE


class AcademyOnnxPolicyRuntime:
    def __init__(self, model_dir: str | Path) -> None:
        self.model_dir = Path(model_dir)
        self.model_id: str | None = None
        self._session: Any | None = None
        self._input_name: str | None = None
        self.last_error: str | None = None

    @property
    def available(self) -> bool:
        return self._session is not None

    def load(self) -> bool:
        try:
            import onnxruntime as ort
        except ImportError:
            self.last_error = "ONNX_RUNTIME_NOT_INSTALLED"
            return False

        manifest_path = self.model_dir / "manifest.json"
        model_path = self.model_dir / "policy.onnx"
        if not manifest_path.exists() or not model_path.exists():
            self.last_error = "ONNX_MODEL_OR_MANIFEST_MISSING"
            return False

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.last_error = "ONNX_MANIFEST_INVALID"
            return False

        if manifest.get("feature_version") != FEATURE_VERSION:
            self.last_error = "ONNX_FEATURE_VERSION_MISMATCH"
            return False
        if manifest.get("observation_size") != OBSERVATION_SIZE:
            self.last_error = "ONNX_OBSERVATION_SIZE_MISMATCH"
            return False
        if tuple(manifest.get("action_space", [])) != ACTION_SPACE_DIMS:
            self.last_error = "ONNX_ACTION_SPACE_MISMATCH"
            return False
        if tuple(manifest.get("scout_names", [])) != ACADEMY_POLICY_SCOUT_NAMES:
            self.last_error = "ONNX_SCOUT_LIST_MISMATCH"
            return False

        try:
            self._session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
            self._input_name = self._session.get_inputs()[0].name
            self.model_id = manifest.get("model_id", model_path.stem)
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = f"ONNX_LOAD_FAILED: {exc}"
            self._session = None
            return False

    def predict_raw_action(self, observation: list[float]) -> list[int]:
        if self._session is None or self._input_name is None:
            raise RuntimeError("ONNX runtime is not loaded")
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("NumPy is required for ONNX policy inference") from exc

        obs = np.asarray([observation], dtype=np.float32)
        output = self._session.run(None, {self._input_name: obs})[0]
        raw = np.asarray(output).reshape(-1)[: len(ACTION_SPACE_DIMS)]
        return [int(value) for value in raw]

    def predict_action(self, observation: list[float]):
        return decode_action(self.predict_raw_action(observation))
