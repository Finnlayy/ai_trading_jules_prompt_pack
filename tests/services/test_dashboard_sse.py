import asyncio
import json
from unittest.mock import patch, MagicMock

import pytest

from app.services.dashboard_sse import SSEEvent, DashboardSSEManager

@pytest.fixture
def manager():
    # Force a new instance for tests to avoid state leakage
    DashboardSSEManager._instance = None
    return DashboardSSEManager()

def test_sse_event_formatting():
    event = SSEEvent(event_type="trade", payload={"id": 123}, timestamp="2024-01-01T00:00:00Z")
    sse_string = event.to_sse_string()

    assert sse_string.startswith("data: ")
    assert sse_string.endswith("\n\n")

    # Parse the json payload inside the string
    json_data = json.loads(sse_string[6:-2])
    assert json_data["type"] == "trade"
    assert json_data["payload"] == {"id": 123}
    assert json_data["timestamp"] == "2024-01-01T00:00:00Z"

def test_manager_singleton():
    manager1 = DashboardSSEManager()
    manager2 = DashboardSSEManager()
    assert manager1 is manager2

@pytest.mark.asyncio
async def test_manager_connect_disconnect(manager):
    assert manager.client_count == 0

    # connect returns an AsyncGenerator. We need to iterate it or step into it to initialize the queue.
    client_id = "test_client_1"
    gen = manager.connect(client_id)

    # The queue isn't created until the generator actually starts yielding
    # We can use an asyncio.Task to run it in the background or step it manually
    # For a generator, simply requesting the first item sets up the try/finally block up to the yield

    async def consume_one():
        try:
            await anext(gen)
        except StopAsyncIteration:
            pass

    task = asyncio.create_task(consume_one())

    # Yield to event loop to allow connect to set up queue
    await asyncio.sleep(0.01)

    assert manager.client_count == 1
    assert client_id in manager._client_ids
    assert client_id in manager._queues

    # Now disconnect
    manager.disconnect(client_id)
    assert manager.client_count == 0
    assert client_id not in manager._client_ids
    assert client_id not in manager._queues

    task.cancel()

@pytest.mark.asyncio
async def test_broadcast(manager):
    client_id = "test_client_1"
    gen = manager.connect(client_id)

    async def consume():
        async for event in gen:
            return event

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01) # let connect set up the queue

    event = SSEEvent(event_type="test", payload={"msg": "hello"})
    manager.broadcast(event)

    # Wait for the client to receive the broadcasted event
    received_str = await asyncio.wait_for(task, timeout=1.0)

    assert event in manager._event_log

    json_data = json.loads(received_str[6:-2])
    assert json_data["type"] == "test"
    assert json_data["payload"] == {"msg": "hello"}

    manager.disconnect(client_id)

def test_broadcast_specific_types(manager):
    client_id = "test_client_1"
    manager._client_ids.add(client_id)
    queue = asyncio.Queue(maxsize=100)
    manager._queues[client_id] = queue

    manager.broadcast_trade_update({"trade_id": 1})
    assert manager._event_log[-1].event_type == "trade"
    assert manager._event_log[-1].payload == {"trade_id": 1}

    manager.broadcast_position_update([{"symbol": "BTC"}])
    assert manager._event_log[-1].event_type == "position"
    assert manager._event_log[-1].payload == {"positions": [{"symbol": "BTC"}]}

    manager.broadcast_metrics_update({"pnl": 100})
    assert manager._event_log[-1].event_type == "metrics"
    assert manager._event_log[-1].payload == {"pnl": 100}

    manager.broadcast_alert("danger", "error")
    assert manager._event_log[-1].event_type == "alert"
    assert manager._event_log[-1].payload == {"message": "danger", "level": "error"}

    manager.broadcast_heartbeat()
    assert manager._event_log[-1].event_type == "heartbeat"
    assert manager._event_log[-1].payload == {"status": "alive"}

def test_broadcast_queue_full(manager):
    client_id = "test_client_1"
    manager._client_ids.add(client_id)
    queue = asyncio.Queue(maxsize=2) # Small queue for test
    manager._queues[client_id] = queue

    event1 = SSEEvent(event_type="test1", payload={})
    event2 = SSEEvent(event_type="test2", payload={})
    event3 = SSEEvent(event_type="test3", payload={})

    manager.broadcast(event1)
    manager.broadcast(event2)
    # Queue is now full (maxsize=2)

    # This should drop event1 and push event3
    manager.broadcast(event3)

    assert queue.qsize() == 2
    assert queue.get_nowait() == event2
    assert queue.get_nowait() == event3
