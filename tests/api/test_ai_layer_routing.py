import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app as fastapi_app
from app.api import ai_layer
from app.services.ai_layer_memory import AILayerMemoryStore
import app.api.live_trading as live_trading

@pytest.fixture(autouse=True)
def isolated_ai_memory(tmp_path, monkeypatch):
    store = AILayerMemoryStore(filepath=str(tmp_path / "ai_layer_memory.json"))
    monkeypatch.setattr(ai_layer, "ai_layer_memory_instance", store)
    monkeypatch.setattr(ai_layer, "AI_PROVIDER", "mock")
    yield

@pytest.mark.asyncio
async def test_chat_routes_run_backtest(monkeypatch):
    called = []
    async def fake_run_backtest(req):
        called.append(req)
        return {
            "status": "success",
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "signals_generated": 2,
            "executed": 1,
            "rejected": 1,
            "results": []
        }
    
    import app.api.backtest_runner
    monkeypatch.setattr(app.api.backtest_runner, "run_backtest", fake_run_backtest)

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/chat",
            json={"message": "Please run a backtest for BTCUSDT with 300 bars"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["recommended_action"]["action"] == "run_backtest"
    assert data["recommended_action"]["params"]["symbol"] == "BTCUSDT"
    assert data["recommended_action"]["params"]["bars"] == 300
    assert "[Action Executed: run_backtest]" in data["reply"]
    assert len(called) == 1
    assert called[0].symbol == "BTCUSDT"
    assert called[0].bars == 300


@pytest.mark.asyncio
async def test_chat_routes_trigger_drill(monkeypatch):
    called = 0
    async def fake_trigger_manual_cycle():
        nonlocal called
        called += 1

    import app.services.training_loop
    monkeypatch.setattr(app.services.training_loop.training_loop, "trigger_manual_cycle", fake_trigger_manual_cycle)

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/chat",
            json={"message": "Please trigger manual drill for technical scout"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["recommended_action"]["action"] == "trigger_drill"
    assert "[Action Executed: trigger_drill]" in data["reply"]
    assert called == 1


@pytest.mark.asyncio
async def test_chat_routes_start_stop_training(monkeypatch):
    start_called = 0
    stop_called = 0
    async def fake_start():
        nonlocal start_called
        start_called += 1
        return {"started": True}
    
    async def fake_stop():
        nonlocal stop_called
        stop_called += 1

    import app.services.training_loop
    monkeypatch.setattr(app.services.training_loop.training_loop, "start", fake_start)
    monkeypatch.setattr(app.services.training_loop.training_loop, "stop", fake_stop)

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        res_start = await ac.post("/ai/chat", json={"message": "start training loop"})
        res_stop = await ac.post("/ai/chat", json={"message": "stop training"})

    assert res_start.status_code == 200
    data_start = res_start.json()
    assert data_start["recommended_action"]["action"] == "start_training"
    assert "[Action Executed: start_training]" in data_start["reply"]
    assert start_called == 1

    assert res_stop.status_code == 200
    data_stop = res_stop.json()
    assert data_stop["recommended_action"]["action"] == "stop_training"
    assert "[Action Executed: stop_training]" in data_stop["reply"]
    assert stop_called == 1


@pytest.mark.asyncio
async def test_chat_routes_reset_memory(monkeypatch):
    called = 0
    def fake_reset():
        nonlocal called
        called += 1
        return {}

    monkeypatch.setattr(ai_layer.ai_layer_memory_instance, "reset", fake_reset)

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        response = await ac.post("/ai/chat", json={"message": "reset memory"})

    assert response.status_code == 200
    data = response.json()
    assert data["recommended_action"]["action"] == "reset_memory"
    assert "[Action Executed: reset_memory]" in data["reply"]
    assert called == 1


@pytest.mark.asyncio
async def test_chat_routes_toggle_emergency(monkeypatch):
    live_trading._emergency_halt_until = None

    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        response_halt = await ac.post("/ai/chat", json={"message": "emergency stop active"})
        assert live_trading._emergency_halt_until is not None

        response_lift = await ac.post("/ai/chat", json={"message": "disable emergency halt"})
        assert live_trading._emergency_halt_until is None

    assert response_halt.status_code == 200
    data_halt = response_halt.json()
    assert data_halt["recommended_action"]["action"] == "toggle_emergency"
    assert data_halt["recommended_action"]["params"]["active"] is True
    assert "[Action Executed: toggle_emergency]" in data_halt["reply"]

    assert response_lift.status_code == 200
    data_lift = response_lift.json()
    assert data_lift["recommended_action"]["action"] == "toggle_emergency"
    assert data_lift["recommended_action"]["params"]["active"] is False
    assert "[Action Executed: toggle_emergency]" in data_lift["reply"]
