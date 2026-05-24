"""
K2.6 Native Sub-Agent Swarm Abstraction Layer

Kimi K2.6 supports up to 300 parallel sub-agents via native tools:
    - create_subagent(name, system_prompt)
    - assign_task(agent_name, task_prompt)
    - get_agent_result(agent_name)

These tools are available in Kimi Code CLI environments but NOT exposed through
standard OpenAI-compatible chat completion endpoints. This module provides an
abstraction that lets us swap between:

    1. OpenAI-compatible parallel LLM calls (current — works with Moonshot/OpenAI/Gemini)
    2. Native K2.6 sub-agent orchestration (future — when tools are available)

To switch implementations, set AI_SWARM_MODE=native in your environment.
"""

from __future__ import annotations

import os
import json
import asyncio
from abc import ABC, abstractmethod
from typing import Any


class SwarmAgent(ABC):
    """Abstract base for a single scout/agent in the swarm."""

    @abstractmethod
    async def review(self, task_prompt: str) -> str:
        """Run the agent on a task and return its text response."""
        ...


class OpenAICompatibleAgent(SwarmAgent):
    """
    Agent backed by a standard async LLM call.
    This is the current production implementation.
    """

    def __init__(self, name: str, system_prompt: str, call_llm) -> None:
        self.name = name
        self.system_prompt = system_prompt
        self._call_llm = call_llm

    async def review(self, task_prompt: str) -> str:
        return await self._call_llm(prompt=task_prompt, system=self.system_prompt)


class NativeK2Agent(SwarmAgent):
    """
    Placeholder for native K2.6 sub-agent.
    When create_subagent / assign_task are available in the runtime,
    replace the body of review() with actual tool calls.

    Example (pseudo-code for when tools are available):

        async def review(self, task_prompt: str) -> str:
            # create_subagent is a Kimi Code CLI tool
            await create_subagent(name=self.name, system_prompt=self.system_prompt)
            await assign_task(agent=self.name, prompt=task_prompt)
            # Poll or await result
            return await get_agent_result(self.name)
    """

    def __init__(self, name: str, system_prompt: str) -> None:
        self.name = name
        self.system_prompt = system_prompt

    async def review(self, task_prompt: str) -> str:
        # FALLBACK: when native tools are not available, raise to force the
        # orchestrator to use the OpenAI-compatible path.
        raise RuntimeError(
            "Native K2.6 sub-agent tools (create_subagent/assign_task) are not "
            "available in this runtime. Use OpenAICompatibleAgent instead."
        )


class SwarmOrchestrator(ABC):
    """Abstract base for multi-agent orchestration."""

    @abstractmethod
    async def run_scouts(self, scouts: dict[str, SwarmAgent], task_payload: dict[str, Any]) -> dict[str, str]:
        """Run all scouts in parallel and return their reports."""
        ...


class ParallelOrchestrator(SwarmOrchestrator):
    """
    Runs all scouts concurrently using asyncio.gather.
    Works with any SwarmAgent implementation.
    """

    async def run_scouts(self, scouts: dict[str, SwarmAgent], task_payload: dict[str, Any]) -> dict[str, str]:
        names = list(scouts.keys())
        tasks = [scouts[name].review(json.dumps(task_payload)) for name in names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        reports: dict[str, str] = {}
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                reports[name] = f"ERROR: {result}"
            else:
                reports[name] = str(result)
        return reports


class SwarmFactory:
    """
    Factory that builds the correct agent + orchestrator combo
    based on AI_SWARM_MODE environment variable.
    """

    MODE = os.getenv("AI_SWARM_MODE", "openai").strip().lower()

    @classmethod
    def create_agent(cls, name: str, system_prompt: str, call_llm=None) -> SwarmAgent:
        if cls.MODE == "native":
            return NativeK2Agent(name=name, system_prompt=system_prompt)
        return OpenAICompatibleAgent(name=name, system_prompt=system_prompt, call_llm=call_llm)

    @classmethod
    def create_orchestrator(cls) -> SwarmOrchestrator:
        return ParallelOrchestrator()

    @classmethod
    def is_native(cls) -> bool:
        return cls.MODE == "native"
