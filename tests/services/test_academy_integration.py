import pytest
import asyncio
from app.services.ai.gem_agents import DEFAULT_AGENT_NAMES
from app.services.training_loop import TrainingLoopService

@pytest.mark.asyncio
async def test_training_loop_manual_cycle():
    loop = TrainingLoopService()
    await loop.trigger_manual_cycle()

    status = loop.get_status()
    assert len(status["recent_drills"]) == len(DEFAULT_AGENT_NAMES)
    assert {row["scout_name"] for row in status["recent_drills"]} == set(DEFAULT_AGENT_NAMES)
    assert status["diversity"]["total_evaluations"] == 1
    assert status["policy"]["scout_count"] == len(DEFAULT_AGENT_NAMES)

    # Run a few more cycles to trigger diversity updates
    await loop.trigger_manual_cycle()
    await loop.trigger_manual_cycle()

    status = loop.get_status()
    assert status["diversity"]["total_evaluations"] == 3


@pytest.mark.asyncio
async def test_training_loop_start_runs_initial_cycle():
    loop = TrainingLoopService()

    result = await loop.start()
    try:
        status = loop.get_status()
        assert result["started"] is True
        assert status["is_running"] is True
        assert status["cycles_completed"] == 1
        assert len(status["recent_drills"]) == len(DEFAULT_AGENT_NAMES)
    finally:
        await loop.stop()

    assert loop.get_status()["is_running"] is False
