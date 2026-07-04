import pytest
import time
import asyncio
from app.services.ai.gem_agents import DEFAULT_AGENT_NAMES
from app.services.training_loop import TrainingLoopService

@pytest.mark.asyncio
async def test_training_loop_performance():
    loop = TrainingLoopService()

    start_time = time.time()

    # Run 10 all-scout cycles.
    for _ in range(10):
        await loop.trigger_manual_cycle()

    end_time = time.time()
    duration = end_time - start_time

    expected_drills = len(DEFAULT_AGENT_NAMES) * 10

    # Ensure the all-16 Academy policy loop remains comfortably above
    # the throughput requirement of 1000 drills in under 5 minutes.
    # The requirement is 1000 drills in under 5 minutes, which is roughly 3.3 drills per second.
    assert expected_drills / duration > 3.3
    assert duration < 15.0
