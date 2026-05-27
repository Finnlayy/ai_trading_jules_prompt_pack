import pytest
from app.services.training_drills import TrainingDrillsService

@pytest.fixture
def drills_service():
    return TrainingDrillsService()

@pytest.mark.asyncio
async def test_generate_drills(drills_service):
    drills = drills_service.generate_drills("technical", count=3)
    assert len(drills) == 3
    for drill in drills:
        assert drill.drill_type == "pattern_recognition"
        assert drill.scout_target == "technical"
        assert "confluence_score" in drill.scenario_data

@pytest.mark.asyncio
async def test_evaluate_drill(drills_service, tmp_path):
    # Mock registry file path
    import app.services.agent_registry
    app.services.agent_registry.CAREER_LOG_FILE = tmp_path / "test.jsonl"

    drill = drills_service.generate_random_drill("sentiment")
    # Provide the exact expected outcome to force a CORRECT result
    result = await drills_service.evaluate_drill(drill, drill.expected_outcome, 0.9)

    assert result.is_correct is True
    assert result.scout_name == "sentiment"
    assert result.confidence == 0.9
