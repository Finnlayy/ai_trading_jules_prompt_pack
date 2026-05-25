"""
Dashboard SSE Manager — Server-Sent Events for real-time frontend updates.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Set


@dataclass
class SSEEvent:
    event_type: str  # "trade", "position", "metrics", "alert", "heartbeat"
    payload: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_sse_string(self) -> str:
        return f"data: {json.dumps({'type': self.event_type, 'payload': self.payload, 'timestamp': self.timestamp})}\n\n"


class DashboardSSEManager:
    """Manages SSE connections and broadcasts events to all clients."""

    _instance: DashboardSSEManager | None = None

    def __new__(cls) -> DashboardSSEManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._queues: Dict[str, asyncio.Queue[SSEEvent]] = {}
        self._client_ids: Set[str] = set()

    async def connect(self, client_id: str) -> AsyncGenerator[str, None]:
        """Yield SSE-formatted strings for a client."""
        queue: asyncio.Queue[SSEEvent] = asyncio.Queue(maxsize=100)
        self._queues[client_id] = queue
        self._client_ids.add(client_id)
        try:
            while True:
                event = await queue.get()
                yield event.to_sse_string()
        finally:
            self.disconnect(client_id)

    def disconnect(self, client_id: str) -> None:
        self._queues.pop(client_id, None)
        self._client_ids.discard(client_id)

    def broadcast(self, event: SSEEvent) -> None:
        """Send an event to all connected clients."""
        for client_id in list(self._client_ids):
            queue = self._queues.get(client_id)
            if queue is None:
                continue
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest event if queue is full
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass

    def broadcast_trade_update(self, payload: dict[str, Any]) -> None:
        self.broadcast(SSEEvent(event_type="trade", payload=payload))

    def broadcast_position_update(self, positions: list[dict]) -> None:
        self.broadcast(SSEEvent(event_type="position", payload={"positions": positions}))

    def broadcast_metrics_update(self, metrics: dict[str, Any]) -> None:
        self.broadcast(SSEEvent(event_type="metrics", payload=metrics))

    def broadcast_alert(self, message: str, level: str = "warning") -> None:
        self.broadcast(
            SSEEvent(
                event_type="alert",
                payload={"message": message, "level": level},
            )
        )

    def broadcast_heartbeat(self) -> None:
        self.broadcast(
            SSEEvent(
                event_type="heartbeat",
                payload={"status": "alive"},
            )
        )

    @property
    def client_count(self) -> int:
        return len(self._client_ids)


# Global singleton
dashboard_sse_manager = DashboardSSEManager()
