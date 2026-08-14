"""C — Position limit per symbol: max 1 position (LONG or SHORT) per pair."""

from __future__ import annotations

import pytest

from app.services.kraken_paper_broker import KrakenPaperBroker


@pytest.fixture
def broker():
    b = KrakenPaperBroker()
    b.reset_paper_account(new_balance=1000.0)
    return b


def test_adding_to_existing_long_position(broker):
    """Buying more of the same symbol should extend the LONG position."""
    broker.place_paper_order("SOLUSD", "BUY", 0.5, "market")
    broker.place_paper_order("SOLUSD", "BUY", 0.5, "market")

    positions = broker.get_positions()["positions"]
    assert len(positions) == 1
    assert positions[0]["volume"] == 1.0
    assert positions[0]["direction"] == "LONG"


def test_long_then_short_flips_position(broker):
    """SHORT after LONG should close LONG and open SHORT (net position)."""
    broker.place_paper_order("SOLUSD", "BUY", 0.5, "market")
    broker.place_paper_order("SOLUSD", "SELL", 0.5, "market")

    positions = broker.get_positions()["positions"]
    assert len(positions) == 0  # Fully closed


def test_long_then_bigger_short_opens_short(broker):
    """Bigger SHORT after LONG should flip to net SHORT."""
    broker.place_paper_order("SOLUSD", "BUY", 0.5, "market")
    broker.place_paper_order("SOLUSD", "SELL", 0.8, "market")

    positions = broker.get_positions()["positions"]
    assert len(positions) == 1
    assert positions[0]["direction"] == "SHORT"
    assert abs(positions[0]["volume"] - 0.3) < 0.001


def test_multiple_symbols_each_get_one_position(broker):
    """Different symbols should each get their own position."""
    broker.place_paper_order("SOLUSD", "BUY", 0.2, "market")
    broker.place_paper_order("ETHUSD", "BUY", 0.01, "market")
    broker.place_paper_order("XRPUSD", "BUY", 5.0, "market")

    positions = broker.get_positions()["positions"]
    assert len(positions) == 3
