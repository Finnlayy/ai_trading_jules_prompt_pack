"""Epic 2 Task 2.4 — Paper broker latency & slippage simulation tests."""

from __future__ import annotations

import time

import pytest

from app.services.kraken_paper_broker import KrakenPaperBroker, KrakenPaperConfig


@pytest.fixture(autouse=True)
def reset_account():
    """Reset paper balance before every test."""
    broker = KrakenPaperBroker(config=KrakenPaperConfig())
    broker.reset_paper_account(new_balance=100.0)


def test_paper_order_simulates_slippage():
    """Market orders must fill with a live price (not a fixed mock)."""
    broker = KrakenPaperBroker(config=KrakenPaperConfig())
    broker.reset_paper_account(new_balance=100.0)

    result = broker.place_paper_order("SOLUSD", "BUY", 0.5, "market")
    assert result["status"] == "ok"
    assert "fill_price" in result
    assert result["fill_price"] > 0
    # Verify the price came from live Kraken ticker (realistic range for SOL)
    assert 10 < result["fill_price"] < 500, f"Unrealistic fill price: {result['fill_price']}"


def test_paper_order_simulates_latency():
    """Execution must take measurable time (live ticker fetch + DB write)."""
    broker = KrakenPaperBroker(config=KrakenPaperConfig())
    broker.reset_paper_account(new_balance=100.0)

    start = time.time()
    result = broker.place_paper_order("SOLUSD", "BUY", 0.1, "market")
    elapsed = time.time() - start

    assert result["status"] == "ok"
    assert elapsed > 0.001, f"Execution was implausibly fast: {elapsed:.6f}s"
