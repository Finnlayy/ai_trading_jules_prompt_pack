import asyncio
import json
from datetime import datetime, timezone
import pytest
from app.services.dashboard_sse import DashboardSSEManager, SSEEvent, dashboard_sse_manager


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton instance before each test."""
    # Resetting the internal state
    dashboard_sse_manager._queues.clear()
    dashboard_sse_manager._client_ids.clear()
    dashboard_sse_manager._event_log.clear()


def test_sse_event_serialization():
    """Test that SSEEvent formats correctly to SSE string."""
    event = SSEEvent(event_type="trade", payload={"id": 1, "price": 50000})
    sse_string = event.to_sse_string()

    assert sse_string.startswith("data: ")
    assert sse_string.endswith("\n\n")

    # Extract the JSON part and verify
    json_str = sse_string[6:-2]
    data = json.loads(json_str)

    assert data["type"] == "trade"
    assert data["payload"] == {"id": 1, "price": 50000}
    assert "timestamp" in data

def test_manager_singleton():
    """Test that DashboardSSEManager operates as a singleton."""
    manager1 = DashboardSSEManager()
    manager2 = DashboardSSEManager()

    assert manager1 is manager2
    assert manager1 is dashboard_sse_manager

@pytest.mark.asyncio
async def test_connect_disconnect():
    """Test connecting and disconnecting clients."""
    client_id = "test_client_1"

    # Should be empty initially
    assert dashboard_sse_manager.client_count == 0

    # We can't await the connect function fully because it runs an infinite loop.
    # Instead, we just get the generator
    generator = dashboard_sse_manager.connect(client_id)

    # Let's create a background task to consume the generator
    async def consume(gen):
        try:
            async for _ in gen:
                pass
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(consume(generator))

    # Yield control to allow the generator to start
    await asyncio.sleep(0.01)

    assert dashboard_sse_manager.client_count == 1
    assert client_id in dashboard_sse_manager._client_ids

    # Disconnect
    dashboard_sse_manager.disconnect(client_id)
    assert dashboard_sse_manager.client_count == 0
    assert client_id not in dashboard_sse_manager._client_ids

    task.cancel()

@pytest.mark.asyncio
async def test_broadcast():
    """Test broadcasting an event to a connected client."""
    client_id = "test_client_broadcast"
    generator = dashboard_sse_manager.connect(client_id)

    # Task to consume one event
    async def get_one_event():
        return await anext(generator)

    task = asyncio.create_task(get_one_event())

    # Yield control to allow connect to initialize
    await asyncio.sleep(0.01)

    # Broadcast an event
    event = SSEEvent(event_type="metrics", payload={"cpu": 50})
    dashboard_sse_manager.broadcast(event)

    # The task should complete with the yielded event
    result = await asyncio.wait_for(task, timeout=1.0)

    assert "metrics" in result
    assert "cpu" in result

    dashboard_sse_manager.disconnect(client_id)

@pytest.mark.asyncio
async def test_broadcast_queue_full():
    """Test broadcasting when a client queue is full."""
    client_id = "test_client_full"
    generator = dashboard_sse_manager.connect(client_id)

    # Task to consume ONE event just to initialize the generator and create the queue
    async def init_gen():
        try:
            await anext(generator)
        except asyncio.CancelledError:
            pass

    task = asyncio.create_task(init_gen())

    # Yield control to allow connect to initialize
    await asyncio.sleep(0.05)

    # Now that the queue exists but is no longer being actively polled (the task got 1 item and finished),
    # let's fill it up.
    for i in range(100):
        dashboard_sse_manager.broadcast_alert(f"Alert {i}")

    # Queue is now full (maxsize=100) and hasn't been drained.
    # The 101st broadcast should trigger QueueFull logic
    # and drop the oldest event
    dashboard_sse_manager.broadcast_alert("Alert 100")

    task.cancel()
    dashboard_sse_manager.disconnect(client_id)

def test_broadcast_helpers():
    """Test all specific broadcast helper functions."""
    # We just want to ensure they call broadcast correctly and don't raise errors
    # By intercepting the broadcast method or just checking the event log

    dashboard_sse_manager.broadcast_trade_update({"trade_id": "T1"})
    assert dashboard_sse_manager._event_log[-1].event_type == "trade"
    assert dashboard_sse_manager._event_log[-1].payload == {"trade_id": "T1"}

    dashboard_sse_manager.broadcast_position_update([{"symbol": "BTC"}])
    assert dashboard_sse_manager._event_log[-1].event_type == "position"
    assert dashboard_sse_manager._event_log[-1].payload == {"positions": [{"symbol": "BTC"}]}

    dashboard_sse_manager.broadcast_metrics_update({"pnl": 100})
    assert dashboard_sse_manager._event_log[-1].event_type == "metrics"
    assert dashboard_sse_manager._event_log[-1].payload == {"pnl": 100}

    dashboard_sse_manager.broadcast_alert("Danger!", "critical")
    assert dashboard_sse_manager._event_log[-1].event_type == "alert"
    assert dashboard_sse_manager._event_log[-1].payload == {"message": "Danger!", "level": "critical"}

    dashboard_sse_manager.broadcast_heartbeat()
    assert dashboard_sse_manager._event_log[-1].event_type == "heartbeat"
    assert dashboard_sse_manager._event_log[-1].payload == {"status": "alive"}
