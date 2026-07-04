from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.academy import router
from app.schemas.academy import CareerEntry
from app.services.agent_registry import agent_registry
from app.services.training_loop import training_loop


def test_deploy_agent_endpoint_creates_local_agent(monkeypatch):
    original_identities = dict(agent_registry._identities)

    try:
        monkeypatch.setattr(agent_registry, "save_registry", lambda: None)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/academy/agents/deploy",
            json={
                "name": "test-ui-agent",
                "archetype": "Analyst",
                "personality_vector": {"analytical": 0.7},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "created"
        assert data["agent"]["name"] == "test-ui-agent"
        assert agent_registry.get_identity("test-ui-agent") is not None
    finally:
        agent_registry._identities = original_identities


def test_deploy_agent_endpoint_rejects_duplicate_names(monkeypatch):
    original_identities = dict(agent_registry._identities)

    try:
        monkeypatch.setattr(agent_registry, "save_registry", lambda: None)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        first = client.post("/academy/agents/deploy", json={"name": "duplicate-ui-agent"})
        second = client.post("/academy/agents/deploy", json={"name": "duplicate-ui-agent"})

        assert first.status_code == 200
        assert second.status_code == 409
    finally:
        agent_registry._identities = original_identities


def test_recent_agent_careers_endpoint(monkeypatch):
    monkeypatch.setattr(
        agent_registry,
        "get_recent_career_events",
        lambda limit=50, event_type=None: [
            CareerEntry(
                scout_name="technical",
                event_type="prediction_result",
                details={
                    "symbol": "BTCUSDT",
                    "strategy_id": "default",
                    "is_correct": True,
                    "outcome_source": "live_paper",
                },
            )
        ],
    )

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/academy/agents/careers/recent?limit=10&event_type=prediction_result")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["career"][0]["scout_name"] == "technical"
    assert data["career"][0]["details"]["outcome_source"] == "live_paper"


def test_academy_status_endpoint_returns_live_training_loop_state():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    expected = training_loop.get_status()

    response = client.get("/academy/status")

    assert response.status_code == 200
    assert response.json() == expected


def test_academy_policy_status_endpoint():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/academy/policy/status")

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] in {"shadow", "heuristic", "ppo"}
    assert data["fallback_available"] is True
    assert data["scout_count"] == 16
    assert data["observation_size"] == 232


def test_academy_policy_preview_endpoint():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post(
        "/academy/policy/preview",
        json={
            "count": 2,
            "training_status": {
                "is_night_time": True,
                "cycles_completed": 1,
                "diversity": {"agreement_rate": 0.7, "total_evaluations": 1},
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["state"]["observation_size"] == 232
    assert len(data["decisions"]) == 2
