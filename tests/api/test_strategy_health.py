"""Phase C2 — Strategy Health Dashboard backend contract tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.mark.asyncio
async def test_strategies_health_returns_list():
    """GET /strategies/health must return a list of StrategyHealthItem objects."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/strategies/health")

    assert response.status_code == 200, f"Unexpected status: {response.status_code}: {response.text[:200]}"
    data = response.json()
    assert "strategies" in data, "Missing 'strategies' key in response"
    assert "generated_at" in data, "Missing 'generated_at' key in response"

    strategies = data["strategies"]
    assert isinstance(strategies, list), "strategies must be a list"

    if strategies:
        first = strategies[0]
        required_fields = [
            "strategy_id",
            "name",
            "is_active",
            "total_signals",
            "win_rate",
            "profit_factor",
            "avg_pnl_pct",
            "max_drawdown_pct",
            "last_signal_age_seconds",
            "health_score",
            "signal_count_24h",
        ]
        for field in required_fields:
            assert field in first, f"Missing required field: {field}"

        # health_score must be in [0, 100]
        assert 0 <= first["health_score"] <= 100, "health_score out of range"
        # win_rate must be in [0, 1]
        assert 0 <= first["win_rate"] <= 1, "win_rate out of range"


@pytest.mark.asyncio
async def test_strategies_health_has_active_flag():
    """At least one strategy must be marked active (matching the registry)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/strategies/health")

    assert response.status_code == 200
    data = response.json()
    strategies = data.get("strategies", [])

    if strategies:
        active_count = sum(1 for s in strategies if s.get("is_active"))
        assert active_count == 1, f"Expected exactly 1 active strategy, got {active_count}"


@pytest.mark.asyncio
async def test_strategies_health_active_strategy_has_last_switch():
    """The active strategy should include last_switch timestamp."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/strategies/health")

    assert response.status_code == 200
    data = response.json()
    strategies = data.get("strategies", [])

    for s in strategies:
        if s.get("is_active"):
            # last_switch may be null if never switched, but the field must exist
            assert "last_switch" in s, "Active strategy missing last_switch field"
