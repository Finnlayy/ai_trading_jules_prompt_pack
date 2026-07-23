import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.confidence_registry import confidence_registry
from app.api.auth import get_current_user

client = TestClient(app)

app.dependency_overrides[get_current_user] = lambda: {'email': 'test@example.com'}


@pytest.fixture(autouse=True)
def reset_registry():
    confidence_registry.reset_all()
    yield
    confidence_registry.reset_all()


def test_get_confidence_stats_empty():
    response = client.get("/confidence/stats")
    assert response.status_code == 200
    assert response.json() == {}


def test_get_symbol_confidence():
    confidence_registry.record_signal_review("BTCUSDT", confluence=80.0, crisis=10.0, direction="LONG")
    response = client.get("/confidence/stats/BTCUSDT")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTCUSDT"
    assert data["total_signals"] == 1
    assert data["avg_confluence"] == 80.0


def test_get_symbol_context():
    confidence_registry.record_trade_outcome("BTCUSDT", "LONG", pnl_pct=2.0, rr=2.0, win=True)
    response = client.get("/confidence/context/BTCUSDT?direction=LONG")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTCUSDT"
    assert data["direction"] == "LONG"
    assert "100% win rate" in data["context"]


def test_reset_symbol():
    confidence_registry.record_signal_review("BTCUSDT", confluence=80.0, crisis=10.0, direction="LONG")
    response = client.post("/confidence/reset/BTCUSDT")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert confidence_registry.get_symbol_stats("BTCUSDT").total_signals == 0


def test_reset_all():
    confidence_registry.record_signal_review("BTCUSDT", confluence=80.0, crisis=10.0, direction="LONG")
    confidence_registry.record_signal_review("ETHUSDT", confluence=75.0, crisis=12.0, direction="SHORT")
    response = client.post("/confidence/reset")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert confidence_registry.get_symbol_stats("BTCUSDT").total_signals == 0
    assert confidence_registry.get_symbol_stats("ETHUSDT").total_signals == 0
