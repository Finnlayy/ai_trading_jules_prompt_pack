from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.academy import router
from app.schemas.academy import CareerEntry
from app.services.agent_registry import agent_registry


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
