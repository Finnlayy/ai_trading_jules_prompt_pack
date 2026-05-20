import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.risk_engine import risk_engine_instance

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_state():
    risk_engine_instance.trades_today = 0
    risk_engine_instance.last_trade_bar = -1
    risk_engine_instance.current_bar = 0

def test_full_pipeline_proceed():
    payload = {
        "signal_id": "sig-pipe-1",
        "symbol": "BTCUSD",
        "timeframe": "1h",
        "direction": "LONG",
        "timestamp": "2026-05-20T10:00:00Z",
        "entry_price": 50000.0,
        "stop_price": 48000.0,
        "target_price": 54000.0,
        "confluence_score": 85.5,
        "crisis_score": 10.0,
        "mc_dispersion": 1.5,
        "spread": 10.0
    }
    response = client.post("/webhook/m8", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["result"]["signal_id"] == "sig-pipe-1"
    assert data["result"]["final_decision"] == "EXECUTED_SIM"
    assert data["result"]["reject_reason"] is None

def test_full_pipeline_reject():
    payload = {
        "signal_id": "sig-pipe-2",
        "symbol": "BTCUSD",
        "timeframe": "1h",
        "direction": "LONG",
        "timestamp": "2026-05-20T10:00:00Z",
        "entry_price": 50000.0,
        "stop_price": 48000.0,
        "target_price": 54000.0,
        "confluence_score": 85.5,
        "crisis_score": 35.0, # High crisis score triggers AI reject and Risk Engine reject
        "mc_dispersion": 1.5,
        "spread": 10.0
    }
    response = client.post("/webhook/m8", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["result"]["final_decision"] == "REJECTED"
    assert data["result"]["reject_reason"] in ["HIGH_CRISIS", "AI_REJECT", "AI_HUMAN_REVIEW_REQUIRED"]
