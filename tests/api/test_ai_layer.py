import pytest
from httpx import ASGITransport, AsyncClient

from app.api import ai_layer
from app.main import app
from app.services.ai_layer_memory import AILayerMemoryStore


@pytest.fixture(autouse=True)
def isolated_ai_memory(tmp_path, monkeypatch):
    store = AILayerMemoryStore(filepath=str(tmp_path / "ai_layer_memory.json"))
    monkeypatch.setattr(ai_layer, "ai_layer_memory_instance", store)
    monkeypatch.setattr(ai_layer, "AI_PROVIDER", "mock")
    yield


@pytest.mark.asyncio
async def test_ai_profile_endpoint_returns_default_profile():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/ai/profile")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["profile"]["risk_tolerance"] == "moderate"
    assert "deterministic risk gates" in data["behavior_prompt"]


@pytest.mark.asyncio
async def test_ai_chat_updates_local_profile_memory():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/chat",
            json={"message": "Please be more conservative and require confluence 90."},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["used_llm"] is False
    assert data["profile"]["risk_tolerance"] == "conservative"
    assert data["profile"]["min_confluence_preference"] == 90.0
    assert len(data["memory"]) >= 2
