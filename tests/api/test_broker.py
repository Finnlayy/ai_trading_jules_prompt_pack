import pytest
from fastapi.testclient import TestClient
from app.api.broker import router as broker_router
from app.api.autonomous_loop import router as loop_router
from fastapi import FastAPI
from app.schemas.live_trading import UnifiedBrokerState
from app.schemas.autonomous_loop import LoopControlRequest

app = FastAPI()
app.include_router(broker_router, prefix="/broker")
app.include_router(loop_router, prefix="/autonomous")
client = TestClient(app)

def test_get_unified_state():
    response = client.get("/broker/unified-state")
    assert response.status_code == 200
    data = response.json()
    assert "broker_name" in data
    assert "balance" in data
    assert data["balance"] > 0

def test_manual_veto():
    response = client.post("/broker/manual-veto", json={"signal_id": "test_123", "action": "VETO"})
    assert response.status_code == 200
    assert response.json()["action"] == "VETO"

def test_toggle_loop():
    response = client.post("/autonomous/toggle", json={"action": "stop"})
    assert response.status_code == 200
    assert response.json()["state"] == "stopped"

    import app.services.autonomous_loop as al
    al.AUTONOMOUS_LOOP_ENABLED = True
    response = client.post("/autonomous/toggle", json={"action": "start"})
    assert response.status_code == 200
    assert response.json()["state"] == "running"
