from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.db.models import AgentLearningEvent, AgentReviewEvent, PaperOutcome, SignalCandidate
from app.services.paper_training_engine import PaperTrainingEngine
from app.main import app


client = TestClient(app)
from app.api.auth import get_current_user

app.dependency_overrides[get_current_user] = lambda: {"email": "test@example.com"}


@pytest.fixture(autouse=True)
def reset_lifecycle_tables():
    with SessionLocal() as db:
        db.query(AgentLearningEvent).delete()
        db.query(AgentReviewEvent).delete()
        db.query(PaperOutcome).delete()
        db.query(SignalCandidate).delete()
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(AgentLearningEvent).delete()
        db.query(AgentReviewEvent).delete()
        db.query(PaperOutcome).delete()
        db.query(SignalCandidate).delete()
        db.commit()


def seed_lifecycle_rows():
    with SessionLocal() as db:
        candidate = SignalCandidate(
            candidate_id="cand-live-BTCUSDT-001",
            signal_id="live-BTCUSDT-001",
            symbol="BTCUSDT",
            timeframe="1h",
            strategy_id="default",
            direction="LONG",
            entry_price=100.0,
            stop_price=95.0,
            target_price=110.0,
            confluence_score=82.0,
            status="paper_closed",
        )
        review = AgentReviewEvent(
            candidate_id="cand-live-BTCUSDT-001",
            signal_id="live-BTCUSDT-001",
            scout_name="technical",
            decision="PROCEED_TO_SIMULATION",
            confidence=0.8,
            provider="mock",
        )
        outcome = PaperOutcome(
            candidate_id="cand-live-BTCUSDT-001",
            trade_id="paper-close-001",
            signal_id="live-BTCUSDT-001",
            symbol="BTCUSDT",
            direction="LONG",
            strategy_id="default",
            timeframe="1h",
            close_reason="TAKE_PROFIT",
            exit_price=110.0,
            pnl=10.0,
            pnl_pct=10.0,
            r_multiple=2.0,
            win=True,
        )
        learning = AgentLearningEvent(
            candidate_id="cand-live-BTCUSDT-001",
            trade_id="paper-close-001",
            signal_id="live-BTCUSDT-001",
            scout_name="technical",
            symbol="BTCUSDT",
            direction="LONG",
            strategy_id="default",
            timeframe="1h",
            was_correct=True,
        )
        db.add_all([candidate, review, outcome, learning])
        db.commit()


def test_lifecycle_summary_exposes_paper_training_counts():
    seed_lifecycle_rows()

    response = client.get("/lifecycle/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["candidates"]["total"] == 1
    assert data["candidates"]["closed"] == 1
    assert data["outcomes"]["total"] == 1
    assert data["outcomes"]["win_rate"] == 1.0
    assert data["learning"]["events"] == 1
    assert data["learning"]["scout_accuracy"]["technical"]["accuracy"] == 1.0


def test_lifecycle_lists_candidates_outcomes_learning_and_reviews():
    seed_lifecycle_rows()

    candidates = client.get("/lifecycle/candidates").json()
    outcomes = client.get("/lifecycle/outcomes").json()
    learning = client.get("/lifecycle/learning").json()
    reviews = client.get("/lifecycle/reviews/cand-live-BTCUSDT-001").json()

    assert candidates["count"] == 1
    assert candidates["items"][0]["status"] == "paper_closed"
    assert outcomes["count"] == 1
    assert outcomes["items"][0]["close_reason"] == "TAKE_PROFIT"
    assert learning["count"] == 1
    assert learning["items"][0]["was_correct"] is True
    assert reviews["count"] == 1
    assert reviews["items"][0]["scout_name"] == "technical"


class FakeLoop:
    def __init__(self) -> None:
        self.is_running = False
        self.is_paused = False

    def start(self) -> None:
        self.is_running = True
        self.is_paused = False

    def stop(self) -> None:
        self.is_running = False
        self.is_paused = False

    def pause(self) -> None:
        self.is_paused = True

    def resume(self) -> None:
        self.is_paused = False

    def get_status(self) -> dict:
        return {
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "active_symbols": ["BTCUSDT"],
            "poll_interval_seconds": 60.0,
            "loop_stats": {"cycles_completed": 0},
        }


class FakeMonitor:
    check_interval_seconds = 5.0

    def __init__(self) -> None:
        self.is_running = False

    def start(self) -> None:
        self.is_running = True

    def stop(self) -> None:
        self.is_running = False


def test_lifecycle_engine_status_and_control(monkeypatch):
    import app.api.lifecycle as lifecycle_api

    fake_engine = PaperTrainingEngine(loop=FakeLoop(), monitor=FakeMonitor())
    monkeypatch.setattr(lifecycle_api, "paper_training_engine", fake_engine)

    started = client.post("/lifecycle/engine/control", json={"action": "start"}).json()
    status = client.get("/lifecycle/engine/status").json()

    assert started["action"] == "start"
    assert status["engine"]["state"] == "running"
    assert status["components"]["autonomous_loop"]["running"] is True
    assert status["components"]["position_monitor"]["running"] is True
    assert status["engine"]["live_trading_enabled"] is False
