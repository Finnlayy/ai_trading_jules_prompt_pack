"""Webhook Consumer — background task that reads signals from the async queue
and executes them via the Kraken Paper Broker.

This connects Epic 2.3 (async signal queue) to Epic 1 (paper trading)
for fully autonomous webhook-driven trading.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.api.webhook_signal import signal_queue
from app.services.kraken_paper_broker import KrakenPaperBroker

logger = logging.getLogger(__name__)

# Module-level singleton
_consumer_task: asyncio.Task | None = None


class WebhookConsumer:
    """Consumes signals from the webhook queue and executes paper orders."""

    def __init__(self, broker: KrakenPaperBroker | None = None) -> None:
        self.broker = broker
        self.is_running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self.is_running:
            return
        if self.broker is None:
            self.broker = KrakenPaperBroker()
        self.is_running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("WebhookConsumer started")

    def stop(self) -> None:
        self.is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("WebhookConsumer stopped")

    async def _consume_loop(self) -> None:
        """Main consumer loop: block on queue, execute paper orders."""
        while self.is_running:
            try:
                # Wait for next signal (non-blocking with timeout for graceful shutdown)
                signal = await asyncio.wait_for(signal_queue.get(), timeout=1.0)
                await self._execute_signal(signal)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("WebhookConsumer error processing signal: %s", exc)

    async def _execute_signal(self, signal: dict[str, Any]) -> None:
        """Convert a queued signal into a paper order."""
        symbol = signal.get("symbol", "")
        direction = signal.get("direction", "BUY")
        volume = signal.get("volume", 0.1)

        if not symbol:
            logger.warning("Skipping signal without symbol: %s", signal)
            return

        try:
            result = self.broker.place_paper_order(
                symbol=symbol,
                direction=direction,
                volume=float(volume),
                order_type="market",
            )
            if result.get("status") == "ok":
                logger.info(
                    "Paper order executed: %s %s %s @ %s (balance=%s)",
                    direction, volume, symbol,
                    result.get("fill_price"),
                    result.get("balance_after"),
                )
            else:
                logger.warning("Paper order rejected: %s", result.get("error"))
        except Exception as exc:
            logger.error("Failed to execute paper order for signal %s: %s", signal.get("signal_id"), exc)


# Singleton instance
webhook_consumer_instance = WebhookConsumer()
