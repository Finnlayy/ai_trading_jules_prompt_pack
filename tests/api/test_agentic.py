import time
import pytest
from fastapi.testclient import TestClient
import json
from app.api.agentic import router
from fastapi import FastAPI
from app.db import get_db, SessionLocal, Base, engine
from app.db.models import AgenticRun, AgentReviewEvent
from app.services.agentic_reasoning import AgenticState, agentic_reasoning
from app.schemas.ai_review import SignalReview

app = FastAPI()
app.include_router(router, prefix="/agentic")
client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    # Base.metadata.drop_all(bind=engine)


def test_get_swarm_state():
    test_id = f"test_run_{int(time.time()*1000)}"
    with SessionLocal() as db:
        run = AgenticRun(
            run_id=test_id,
            symbol="BTCUSDT",
            status="planning_completed",
            audit_trace_json=json.dumps({"swarm_commentary": "Test commentary"})
        )
        db.add(run)

        event1 = AgentReviewEvent(
            candidate_id=test_id,
            scout_name="Technical",
            decision="PROCEED",
            confidence=0.9,
            reasons_json=json.dumps(["BULLISH_TREND"]),
            model="gpt-4o"
        )
        event2 = AgentReviewEvent(
            candidate_id=test_id,
            scout_name="Risk",
            decision="HOLD",
            confidence=0.5,
            reasons_json=json.dumps(["VOLATILE"]),
            model="gpt-4o"
        )
        db.add(event1)
        db.add(event2)
        db.commit()

    response = client.get(f"/agentic/swarm-state/{test_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == test_id
    assert data["symbol"] == "BTCUSDT"
    assert len(data["votes"]) == 2
    assert data["commentary"] == "Test commentary"


def test_generate_swarm_commentary():
    # Test the standalone helper
    class MockPerception:
        class Regime:
            market_regime = "Bullish"
            volatility = "Low"
        regime = Regime()

    state = AgenticState(run_id="test")
    state.perception = MockPerception()
    state.scout_reviews = {
        "Tech": {"decision": "PROCEED"},
        "Risk": {"decision": "PROCEED"}
    }
    class MockSignal:
        direction = "LONG"
    state.signal = MockSignal()

    commentary = agentic_reasoning._generate_swarm_commentary(state)
    assert "Unanimous Swarm conviction" in commentary
