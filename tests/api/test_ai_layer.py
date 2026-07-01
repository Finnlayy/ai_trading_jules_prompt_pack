import json

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


@pytest.mark.asyncio
async def test_ai_chat_uses_versioned_system_prompt(tmp_path, monkeypatch):
    chat_dir = tmp_path / "chat"
    chat_dir.mkdir()
    (chat_dir / "v_active.md").write_text("v_test.md\n", encoding="utf-8")
    (chat_dir / "v_test.md").write_text("Versioned chat system prompt.", encoding="utf-8")
    monkeypatch.setattr(ai_layer, "AI_PROMPTS_DIR", tmp_path)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/chat",
            json={
                "message": "Use the mounted setup conservatively.",
                "return_prompt_only": True,
                "strategy_context": "BPRC_PRO",
                "chart_context": {
                    "symbol": "BTCUSDT",
                    "recent_candles": [{"close": idx} for idx in range(20)],
                },
                "bars_count": 10,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["system_prompt"].startswith("Versioned chat system prompt.")
    assert "actual price action" in data["system_prompt"]
    assert "BPRC_PRO" in data["system_prompt"]
    generated_prompt = json.loads(data["generated_prompt"])
    assert len(generated_prompt["chart_context"]["recent_candles"]) == 10
    assert generated_prompt["chart_context"]["recent_candles"][0]["close"] == 10


@pytest.mark.asyncio
async def test_ai_gems_review_prompt_only_routes_pionex_and_redacts_secrets():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/gems/review",
            json={
                "mode": "pionex_deployment",
                "symbol": "BTCUSDT",
                "direction": "LONG",
                "return_prompt_only": True,
                "context": {
                    "pionex_payload": {"signal_type": "uuid"},
                    "api_key": "do-not-send",
                },
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["used_llm"] is False
    assert data["selected_phases"] == [7, 8]
    assert data["selected_gems"] == ["pine_core", "payload_qa"]
    assert data["backend_context"]["input"]["api_key"] == "[REDACTED]"
    assert set(data["generated_prompts"].keys()) == {"pine_core", "payload_qa"}


@pytest.mark.asyncio
async def test_ai_chat_actions_and_context(monkeypatch):
    # Test context enrichment includes system_state
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/chat",
            json={
                "message": "check balance",
                "return_prompt_only": True,
            },
        )
    assert response.status_code == 200
    data = response.json()
    generated_prompt = json.loads(data["generated_prompt"])
    assert "system_state" in generated_prompt
    assert "active_strategy_id" in generated_prompt["system_state"]
    assert "paper_balance" in generated_prompt["system_state"]

    # Test set_strategy action triggers successfully
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/chat",
            json={
                "message": "change strategy to pattern_enhanced",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_action"]["action"] == "set_strategy"
    assert data["recommended_action"]["params"]["strategy_id"] == "pattern_enhanced"
    assert "Active strategy changed to 'pattern_enhanced'" in data["reply"]

    # Test open_trade action triggers successfully
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/chat",
            json={
                "message": "open long HYPEUSDT 2.5 qty",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_action"]["action"] == "open_trade"
    assert data["recommended_action"]["params"]["symbol"] == "HYPEUSDT"
    assert data["recommended_action"]["params"]["direction"] == "LONG"
    assert data["recommended_action"]["params"]["quantity"] == 2.5
    assert "Placed manual LONG order for HYPEUSDT" in data["reply"]

    # Test close_trade action triggers successfully
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/chat",
            json={
                "message": "close trade for HYPEUSDT",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_action"]["action"] == "close_trade"
    assert data["recommended_action"]["params"]["symbol"] == "HYPEUSDT"
    assert "Closed" in data["reply"]

    # Test add_strategy action triggers successfully
    pine_code = '//@version=5\nstrategy("MySuperStrategy")\nplot(close)'
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/chat",
            json={
                "message": f"add strategy MySuperStrategy:\n{pine_code}",
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert data["recommended_action"]["action"] == "add_strategy"
    assert data["recommended_action"]["params"]["name"] == "MySuperStrategy"
    assert "Saved and registered strategy" in data["reply"]

    # Check that it is registered in strategy_registry
    from app.services.strategy_engine import strategy_registry
    assert "MySuperStrategy" in strategy_registry.list_strategies()

    # Clean up file and registry entry to avoid side effects
    from pathlib import Path
    temp_file = Path(__file__).resolve().parents[2] / "app" / "scripts" / "generated_pines" / "MySuperStrategy.pine"
    if temp_file.exists():
        temp_file.unlink()
    strategy_registry.unregister("MySuperStrategy")
