"""Phase 1 RED — Backend contract tests for the 8-point batch.

These tests assert the *expected* API contracts that are currently unimplemented.
They must all fail (RED) before implementation begins.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


# ---------------------------------------------------------------------------
# Bug 1 — AI Chat Payload Crash (>20k chars must not 500)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ai_chat_large_payload_rejected_gracefully():
    """RED: Oversized chat payloads must return 422 (validation) or 413, never 500."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/ai/chat",
            json={
                "message": "A" * 25_000,
                "chart_context": {
                    "recent_candles": [],
                    "indicators": {"rsi": [70.0] * 1000},
                },
                "bars_count": 300,
            },
        )
    # 422 = Pydantic validation rejection (graceful), 413 = explicit too-large
    assert response.status_code in {200, 413, 422}, (
        f"Expected graceful rejection (200/413/422), got {response.status_code}: {response.text[:200]}"
    )
    if response.status_code == 200:
        data = response.json()
        assert "truncated" in data or len(data.get("reply", "")) < 25_000, (
            "200 response must indicate truncation"
        )


# ---------------------------------------------------------------------------
# Bug 2 — Orphaned Error Logs (backend contract)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_loop_stats_exposes_error_history():
    """RED: Autonomous loop errors must be fetchable via /loop/stats."""
    from app.services.autonomous_loop import autonomous_loop_instance

    # Inject 5 synthetic errors
    for i in range(5):
        autonomous_loop_instance._health.stats.record_error(f"audit-error-{i}")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/loop/stats")

    print("RESPONSE STATUS:", response.status_code)
    print("RESPONSE BODY:", response.text[:500])
    assert response.status_code == 200
    data = response.json()
    error_history = data.get("error_history", [])
    assert len(error_history) == 5, (
        f"Expected 5 errors in history, got {len(error_history)}"
    )
    for i in range(5):
        assert any(f"audit-error-{i}" in str(e) for e in error_history), (
            f"Missing audit-error-{i} in error_history"
        )


# ---------------------------------------------------------------------------
# Bug 5 — Live/Sim Toggle & Trade List (backend contract)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_live_trades_endpoint_returns_execution_mode():
    """RED: GET /live/trades must include execution_mode and formatted dates."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/live/trades?limit=10")
    assert response.status_code == 200
    data = response.json()
    trades = data.get("trades", [])
    if trades:
        first = trades[0]
        assert "execution_mode" in first, "Missing execution_mode in trade response"
        assert "entry_price" in first, "Missing entry_price"
        assert "exit_price" in first, "Missing exit_price"
        assert "pnl" in first, "Missing pnl"
        assert "timestamp" in first, "Missing timestamp"
        ts = first["timestamp"]
        assert ":" in ts, f"Timestamp not formatted as dd:mm:yy : hh:mm: {ts}"


# ---------------------------------------------------------------------------
# Bug 6 — Missing Agent Metrics (backend contract)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_agent_registry_returns_metrics():
    """RED: Agent registry endpoint must expose confidence_level and experience_level."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/academy/agents/registry")
    assert response.status_code == 200
    data = response.json()
    agents = data.get("agents", [])
    if agents:
        first = agents[0]
        assert "confidence_level" in first, "Agent registry missing confidence_level"
        assert "experience_level" in first, "Agent registry missing experience_level"


def test_scout_identity_schema_has_metrics():
    """RED: ScoutIdentity must include confidence_level and experience_level fields."""
    from app.schemas.academy import ScoutIdentity
    scout = ScoutIdentity(
        name="test-scout",
        archetype="Analyst",
        personality_vector={"analytical": 0.9},
    )
    data = scout.model_dump()
    assert "confidence_level" in data, "ScoutIdentity missing confidence_level field"
    assert "experience_level" in data, "ScoutIdentity missing experience_level field"


# ---------------------------------------------------------------------------
# Bug 8 — Backtest Chart Integration (backend contract)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_backtest_response_contains_entry_exit_coordinates(monkeypatch):
    """RED: POST /backtest/run must return explicit entry/exit markers per signal."""
    from app.services.signal_generator import signal_generator_instance
    from app.schemas.m8_payload import M8Payload
    from datetime import datetime, timezone

    # Mock generate_payloads to avoid slow network IO
    def _mock_generate(*, symbol, timeframe, bars, min_confluence=None):
        return [
            M8Payload(
                signal_id="bt-1",
                symbol="BTCUSDT",
                timeframe="1h",
                direction="LONG",
                intent="ENTRY",
                timestamp=datetime.now(timezone.utc).isoformat(),
                entry_price=50000.0,
                stop_price=48000.0,
                target_price=54000.0,
                confluence_score=85.0,
                crisis_score=5.0,
                mc_dispersion=1.0,
                spread=2.0,
            )
        ]

    monkeypatch.setattr(signal_generator_instance, "generate_payloads", _mock_generate)

    # Mock AI review to avoid provider errors
    from app.api import orchestrator as orch_module
    from app.services.ai_mock import MockAIReviewLayer
    original_ai = getattr(orch_module, "ai_review_instance", None)
    orch_module.ai_review_instance = MockAIReviewLayer()

    payload = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "strategy_id": "default",
        "start_date": "2026-01-01",
        "end_date": "2026-01-15",
        "initial_balance": 10000,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/backtest/run", json=payload)

    # Restore AI review instance
    if original_ai is not None:
        orch_module.ai_review_instance = original_ai

    if response.status_code != 200:
        assert False, f"Backtest returned {response.status_code}: {response.text[:1000]}"
    assert response.status_code == 200
    data = response.json()
    results = data.get("results", [])
    if results:
        first = results[0]
        assert "entry" in first, "Missing entry coordinate in backtest result"
        assert "exit" in first, "Missing exit coordinate in backtest result"
