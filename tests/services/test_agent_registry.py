import pytest
import asyncio
from app.services.agent_registry import AgentRegistryService
from app.schemas.academy import CareerEntry

@pytest.fixture
def registry(tmp_path):
    import app.services.agent_registry
    app.services.agent_registry.DATA_DIR = tmp_path
    app.services.agent_registry.CAREER_LOG_FILE = tmp_path / "agent_careers.jsonl"
    app.services.agent_registry.REGISTRY_FILE = tmp_path / "agent_registry.json"

    registry = AgentRegistryService()
    return registry

@pytest.mark.asyncio
async def test_agent_registry_defaults(registry):
    identities = registry.get_all_identities()
    assert len(identities) >= 4
    names = [i.name for i in identities]
    assert "technical" in names
    assert "sentiment" in names

@pytest.mark.asyncio
async def test_agent_registry_log_career_event_and_badges(registry):
    tech_scout = registry.get_identity("technical")
    assert tech_scout.total_calls == 0
    assert len(tech_scout.badges) == 0

    # Simulate 10 successful calls to trigger Apprentice and Streak badges
    for i in range(10):
        entry = CareerEntry(
            scout_name="technical",
            event_type="prediction_result",
            details={"is_correct": True}
        )
        await registry.log_career_event(entry)

    # Reload or check in-memory
    tech_scout = registry.get_identity("technical")
    assert tech_scout.total_calls == 10
    assert tech_scout.correct_calls == 10
    assert tech_scout.accuracy == 1.0
    assert tech_scout.current_streak == 10

    badge_names = [b.name for b in tech_scout.badges]
    assert "Apprentice" in badge_names
    assert "Streak" in badge_names
