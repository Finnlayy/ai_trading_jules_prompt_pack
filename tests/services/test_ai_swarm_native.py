import pytest
from unittest.mock import AsyncMock

from app.services.ai_swarm_native import (
    OpenAICompatibleAgent,
    NativeK2Agent,
    ParallelOrchestrator,
    SwarmFactory,
)


@pytest.mark.asyncio
async def test_openai_compatible_agent_calls_llm():
    mock_llm = AsyncMock(return_value="scout report text")
    agent = OpenAICompatibleAgent(name="test", system_prompt="be a test", call_llm=mock_llm)
    result = await agent.review("task prompt")
    assert result == "scout report text"
    mock_llm.assert_awaited_once()
    _, kwargs = mock_llm.call_args
    assert kwargs["prompt"] == "task prompt"
    assert kwargs["system"] == "be a test"


@pytest.mark.asyncio
async def test_native_k2_agent_raises_when_tools_unavailable():
    agent = NativeK2Agent(name="test", system_prompt="be a test")
    with pytest.raises(RuntimeError, match="Native K2.6 sub-agent tools"):
        await agent.review("task prompt")


@pytest.mark.asyncio
async def test_parallel_orchestrator_runs_all_scouts():
    orchestrator = ParallelOrchestrator()
    agent_a = OpenAICompatibleAgent(name="a", system_prompt="sys_a", call_llm=AsyncMock(return_value="result_a"))
    agent_b = OpenAICompatibleAgent(name="b", system_prompt="sys_b", call_llm=AsyncMock(return_value="result_b"))

    scouts = {"scout_a": agent_a, "scout_b": agent_b}
    reports = await orchestrator.run_scouts(scouts, {"symbol": "BTCUSDT"})

    assert reports["scout_a"] == "result_a"
    assert reports["scout_b"] == "result_b"


@pytest.mark.asyncio
async def test_parallel_orchestrator_handles_errors_gracefully():
    orchestrator = ParallelOrchestrator()

    async def fail(*args, **kwargs):
        raise ValueError("boom")

    agent_ok = OpenAICompatibleAgent(name="ok", system_prompt="sys", call_llm=AsyncMock(return_value="ok"))
    agent_fail = OpenAICompatibleAgent(name="fail", system_prompt="sys", call_llm=fail)

    scouts = {"ok": agent_ok, "fail": agent_fail}
    reports = await orchestrator.run_scouts(scouts, {})

    assert reports["ok"] == "ok"
    assert "ERROR" in reports["fail"]


def test_swarm_factory_defaults_to_openai():
    agent = SwarmFactory.create_agent("test", "sys", call_llm=AsyncMock())
    assert isinstance(agent, OpenAICompatibleAgent)
    assert not SwarmFactory.is_native()
