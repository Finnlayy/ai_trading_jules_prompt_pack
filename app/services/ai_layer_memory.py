from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.schemas.ai_layer import AIBehaviorProfile, AIChatMessage, utc_now


class AILayerMemoryStore:
    def __init__(self, filepath: str = "logs/ai_layer_memory.json") -> None:
        self.filepath = Path(filepath)
        # Cache the state in memory to prevent synchronous file I/O on every property access
        self._cache = None

    def _default_state(self) -> dict[str, Any]:
        return {
            "profile": AIBehaviorProfile().model_dump(),
            "memory": [],
        }

    def _load_state(self) -> dict[str, Any]:
        if self._cache is not None:
            return self._cache

        if not self.filepath.exists():
            self._cache = self._default_state()
            return self._cache

        try:
            data = json.loads(self.filepath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            self._cache = self._default_state()
            return self._cache

        state = self._default_state()
        state.update(data if isinstance(data, dict) else {})
        self._cache = state
        return self._cache

    def _save_state(self, state: dict[str, Any]) -> None:
        self._cache = state
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.filepath.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def get_profile(self) -> AIBehaviorProfile:
        return AIBehaviorProfile(**self._load_state()["profile"])

    def get_memory(self) -> list[AIChatMessage]:
        messages = self._load_state().get("memory", [])
        return [AIChatMessage(**message) for message in messages[-40:]]

    def update_profile(self, patch: dict[str, Any]) -> AIBehaviorProfile:
        current = self.get_profile().model_dump()
        allowed = set(AIBehaviorProfile.model_fields.keys())
        current.update({key: value for key, value in patch.items() if key in allowed})
        current["updated_at"] = utc_now()
        profile = AIBehaviorProfile(**current)

        state = self._load_state()
        state["profile"] = profile.model_dump()
        self._save_state(state)
        return profile

    def append_message(self, role: str, content: str) -> list[AIChatMessage]:
        state = self._load_state()
        messages = state.get("memory", [])
        messages.append(AIChatMessage(role=role, content=content).model_dump())
        state["memory"] = messages[-80:]
        self._save_state(state)
        return self.get_memory()

    def reset(self) -> dict[str, Any]:
        state = self._default_state()
        self._save_state(state)
        return state

    def behavior_prompt(self) -> str:
        profile = self.get_profile()
        return (
            "User AI behavior profile for signal review only:\n"
            f"- trading_style: {profile.trading_style}\n"
            f"- risk_tolerance: {profile.risk_tolerance}\n"
            f"- preferred_symbols: {', '.join(profile.preferred_symbols) or 'none'}\n"
            f"- blocked_symbols: {', '.join(profile.blocked_symbols) or 'none'}\n"
            f"- max_risk_pct: {profile.max_risk_pct if profile.max_risk_pct is not None else 'unset'}\n"
            f"- min_confluence_preference: {profile.min_confluence_preference if profile.min_confluence_preference is not None else 'unset'}\n"
            f"- notes: {profile.notes or 'none'}\n"
            f"- guardrails: {'; '.join(profile.guardrails)}\n"
            "These preferences may influence AI review confidence, reason codes, and human-review flags, "
            "but they must never override deterministic risk gates or directly authorize execution."
        )


ai_layer_memory_instance = AILayerMemoryStore()
