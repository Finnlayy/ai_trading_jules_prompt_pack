"""End-to-end: Webhook signal → async consumer → paper order execution."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os

from fastapi.testclient import TestClient

# Patch config BEFORE importing app
import app.core.config as _config
_config.WEBHOOK_SECRET = "test-secret-do-not-use"

from app.main import app
from app.api.webhook_signal import signal_queue
from app.services.kraken_paper_broker import KrakenPaperBroker
from app.services.webhook_consumer import WebhookConsumer

client = TestClient(app)


def _sign(payload: str, secret: str = "test-secret-do-not-use") -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def test_webhook_signal_queued_and_executable():
    """A signal sent to /api/webhook/signal lands in queue and can be consumed."""
    # Clear any stale signals
    while not signal_queue.empty():
        signal_queue.get_nowait()

    payload = json.dumps({
        "symbol": "SOLUSD",
        "direction": "BUY",
        "price": 80.0,
        "volume": 0.5,
    })
    headers = {
        "X-Signature": _sign(payload),
        "Content-Type": "application/json",
    }
    response = client.post("/api/webhook/signal", data=payload, headers=headers)
    assert response.status_code == 200

    # The signal must be in the queue
    assert not signal_queue.empty(), "Signal was not queued"
    signal = signal_queue.get_nowait()
    assert signal["symbol"] == "SOLUSD"
    assert signal["direction"] == "BUY"


def test_consumer_executes_paper_order_from_signal():
    """WebhookConsumer must turn a queued signal into a paper trade."""
    broker = KrakenPaperBroker()
    broker.reset_paper_account(new_balance=100.0)

    # Seed a signal directly into the queue
    signal_queue.put_nowait({
        "signal_id": "test_sig_001",
        "symbol": "SOLUSD",
        "direction": "BUY",
        "volume": 0.3,
        "price": 80.0,
    })

    # Create consumer with our broker
    consumer = WebhookConsumer(broker=broker)

    # Run one iteration of the consume loop manually
    async def _run_once():
        signal = await asyncio.wait_for(signal_queue.get(), timeout=2.0)
        await consumer._execute_signal(signal)

    asyncio.run(_run_once())

    # Verify a trade was created
    history = broker.get_paper_history()
    assert history["count"] >= 1
    trade = history["trades"][0]
    assert trade["symbol"] == "SOLUSD"
    assert trade["direction"] == "LONG"

    # Balance must have decreased
    bal = broker.get_wallet_balances()
    assert bal["balance"] < 100.0
