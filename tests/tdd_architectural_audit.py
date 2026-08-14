"""TDD Architectural Audit — Cross-Boundary Integration Tests.

Phase 1: RED — Expose structural disconnects between API/UI, AI-Layer,
Event Bus, and Database layers.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture(autouse=True)
def reset_audit_state(tmp_path, monkeypatch):
    """Reset global singletons before each audit test."""
    from app.services.live_fill_tracker import live_fill_tracker
    from app.services.dashboard_sse import dashboard_sse_manager
    from app.services.autonomous_loop import autonomous_loop_instance
    from app.services.portfolio_circuit_breaker import circuit_breaker_instance
    from app.api.orchestrator import reset_broker

    # Ensure DB tables exist for repository tests
    from app.db import Base, engine
    Base.metadata.create_all(bind=engine)

    # Reset live fill tracker
    live_fill_tracker.reset()

    # Disconnect all SSE clients and clear event log
    for client_id in list(dashboard_sse_manager._client_ids):
        dashboard_sse_manager.disconnect(client_id)
    dashboard_sse_manager._event_log.clear()

    # Reset emergency halt
    from app.api import live_trading as lt
    lt._emergency_halt_until = None

    # Stop loop
    autonomous_loop_instance.stop()
    autonomous_loop_instance.is_running = False
    autonomous_loop_instance.is_paused = False

    # Reset circuit breaker
    circuit_breaker_instance.reset()

    # Reset broker
    reset_broker()

    yield

    live_fill_tracker.reset()
    for client_id in list(dashboard_sse_manager._client_ids):
        dashboard_sse_manager.disconnect(client_id)
    dashboard_sse_manager._event_log.clear()
    lt._emergency_halt_until = None
    autonomous_loop_instance.stop()


# ---------------------------------------------------------------------------
# Audit Vector 1 — Singleton & Global State Cohesion
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_emergency_halt_propagates_to_signal_pipeline():
    """RED: Emergency stop must block trades in the deep signal pipeline, not just pause the loop."""
    from app.api.orchestrator import process_signal
    from app.schemas.m8_payload import M8Payload

    # Trigger emergency halt via API (outermost layer)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/live/emergency-stop",
            json={"reason": "Audit test halt", "close_open_positions": False, "halt_duration_minutes": 10},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    # Now fire a signal through the deep pipeline (innermost layer)
    payload = M8Payload(
        signal_id="audit-001",
        symbol="BTCUSDT",
        timeframe="1h",
        direction="LONG",
        timestamp=datetime.now(timezone.utc).isoformat(),
        entry_price=50000.0,
        stop_price=48000.0,
        target_price=54000.0,
        confluence_score=85.0,
        crisis_score=10.0,
        mc_dispersion=2.0,
        spread=5.0,
    )

    result = await process_signal(payload)

    # Assert: the deep pipeline must respect the emergency halt
    assert result["final_decision"] == "REJECTED", (
        f"Expected REJECTED due to emergency halt, got {result['final_decision']}"
    )
    assert "EMERGENCY_HALT" in (result.get("reject_reason") or ""), (
        f"Expected EMERGENCY_HALT in reject_reason, got {result.get('reject_reason')}"
    )


# ---------------------------------------------------------------------------
# Audit Vector 2 — Event Bus & Queue Routing
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_event_bus_captures_events_without_connected_clients():
    """RED: Events fired from deep inside the AI layer must be captured even without SSE clients."""
    from app.services.dashboard_sse import dashboard_sse_manager, SSEEvent

    # Pre-condition: no SSE clients connected
    assert dashboard_sse_manager.client_count == 0, (
        f"Expected 0 clients, got {dashboard_sse_manager.client_count}"
    )

    # Simulate an event fired from deep inside the AI layer
    event = SSEEvent(
        event_type="crisis",
        payload={"level": "CRITICAL", "source": "ai_audit", "reason": "AI detected anomaly"},
    )
    dashboard_sse_manager.broadcast(event)

    # Assert: there is a centralized event log that captured the event
    assert hasattr(dashboard_sse_manager, "_event_log"), (
        "Structural disconnect: DashboardSSEManager has no persistent event log. "
        "Events are silently dropped when no client is connected."
    )
    assert len(dashboard_sse_manager._event_log) == 1, (
        f"Expected 1 logged event, got {getattr(dashboard_sse_manager, '_event_log', [])}"
    )
    logged = dashboard_sse_manager._event_log[0]
    assert logged.payload == event.payload
    assert logged.event_type == "crisis"


# ---------------------------------------------------------------------------
# Audit Vector 3 — Database & Memory Synchronization
# ---------------------------------------------------------------------------
def test_db_close_syncs_to_live_fill_tracker():
    """RED: Closing a position in DB must invalidate the in-memory cache."""
    from app.services.live_fill_tracker import live_fill_tracker, FillData, PositionIntent
    from app.db import SessionLocal
    from app.db.repository import PositionRepository

    # 1. Create an open position via the tracker (memory + DB)
    intent = PositionIntent(
        trade_id="audit-pos-001",
        symbol="BTCUSDT",
        direction="LONG",
        entry_price=50000.0,
        stop_price=48000.0,
        target_price=54000.0,
        size=None,
        strategy_id=None,
        decision="PROCEED_TO_SIMULATION",
    )
    live_fill_tracker.record_intent(intent)
    live_fill_tracker.record_fill(
        trade_id="audit-pos-001",
        fill_data=FillData(
            entry_price=50000.0,
            fill_time=datetime.now(timezone.utc),
            size=0.1,
            side="LONG",
            fees=0.5,
            slippage=0.2,
        ),
    )

    # Verify pre-condition: position is open in memory
    pre = live_fill_tracker.get_position("audit-pos-001")
    assert pre is not None, "Pre-condition failed: position not in tracker"

    # 2. Simulate Web UI directly closing the trade in the database
    db = SessionLocal()
    repo = PositionRepository(db)
    repo.close("audit-pos-001", exit_price=51000.0, realized_pnl=100.0)
    db.close()

    # 3. Assert: the in-memory cache reflects the DB state
    post = live_fill_tracker.get_position("audit-pos-001")
    assert post is None, (
        "Structural disconnect: live_fill_tracker still holds a position that was closed in DB. "
        f"Expected None, got {post}"
    )
