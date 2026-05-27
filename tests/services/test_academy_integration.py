import pytest
import asyncio
from app.services.training_loop import TrainingLoopService

@pytest.mark.asyncio
async def test_training_loop_manual_cycle():
    loop = TrainingLoopService()
    await loop.trigger_manual_cycle()

    status = loop.get_status()
    assert len(status["recent_drills"]) == 6  # 6 default scouts generated
    assert status["diversity"]["total_evaluations"] == 1

    # Run a few more cycles to trigger diversity updates
    await loop.trigger_manual_cycle()
    await loop.trigger_manual_cycle()

    status = loop.get_status()
    assert status["diversity"]["total_evaluations"] == 3
