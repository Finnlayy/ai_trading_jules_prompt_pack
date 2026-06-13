from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_runs():
    response = client.get("/agentic/runs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_review_signal():
    req_data = {
        "signal_id": "test_signal_123",
        "symbol": "BTCUSD",
        "direction": "LONG",
        "entry_price": 50000.0,
        "timeframe": "1m"
    }
    response = client.post("/agentic/review-signal", json=req_data)
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert "review" in data
    assert data["review"]["decision"] == "PROCEED_TO_SIMULATION"
