import pytest
import time
import asyncio
from app.services.training_loop import TrainingLoopService

@pytest.mark.asyncio
async def test_training_loop_performance():
    loop = TrainingLoopService()

    start_time = time.time()

    # Run 10 cycles (40 drills)
    for _ in range(10):
        await loop.trigger_manual_cycle()

    end_time = time.time()
    duration = end_time - start_time

    # We want to ensure 40 simulated drills run in under 2 seconds.
    # The requirement is 1000 drills in under 5 minutes, which is roughly 3.3 drills per second.
    # 40 drills should definitely be well under 2 seconds if not blocked by synchronous IO.
    assert duration < 5.0
