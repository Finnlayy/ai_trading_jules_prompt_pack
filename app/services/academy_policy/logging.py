from __future__ import annotations

import asyncio
from pathlib import Path
from app.core.utils import append_jsonl_async
from typing import Any

ACTION_LOG_FILE = Path("logs/academy_policy_actions.jsonl")
REWARD_LOG_FILE = Path("logs/academy_policy_rewards.jsonl")
EPISODE_LOG_FILE = Path("logs/academy_policy_episodes.jsonl")


async def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    await append_jsonl_async(str(path), payload)


async def append_many_jsonl(path: Path, payloads: list[dict[str, Any]]) -> None:
    if not payloads:
        return

    def _write() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            import json

            for payload in payloads:
                handle.write(json.dumps(payload, default=str) + "\n")

    await asyncio.to_thread(_write)
