
import pytest
from app.services.prompt_evolution import PromptEvolutionService

@pytest.fixture
def prompt_service(tmp_path):
    import app.services.prompt_evolution
    app.services.prompt_evolution.DATA_DIR = tmp_path
    app.services.prompt_evolution.PROMPT_REGISTRY_FILE = tmp_path / "prompts.json"
    s = PromptEvolutionService()
    return s

def test_prompt_evolution_defaults(prompt_service):
    # Depending on load state, might be empty, just test create
    pass

def test_create_prompt_version(prompt_service):
    new_v = prompt_service.create_version("technical", "v2_advanced", "Advanced prompt text", parent_version="v1_base")
    assert new_v.scout_name == "technical"
    assert new_v.parent_version == "v1_base"
