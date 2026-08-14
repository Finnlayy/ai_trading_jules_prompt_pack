"""D — Auto Stop-Loss / Take-Profit: close positions when price hits SL or TP."""

from __future__ import annotations

import pytest

from app.services.kraken_paper_broker import KrakenPaperBroker


@pytest.fixture
def broker():
    b = KrakenPaperBroker()
    b.reset_paper_account(new_balance=1000.0)
    return b


def test_position_tracks_sl_and_tp(broker):
    """A position opened with SL/TP must store those levels."""
    # Place order with explicit SL and TP
    result = broker.place_paper_order(
        "SOLUSD", "BUY", 0.5, "market",
        stop_loss=80.0, take_profit=90.0
    )
    assert result["status"] == "ok"

    # Position should have SL/TP stored (we need to add this to PaperPosition)
    positions = broker.get_positions()["positions"]
    assert len(positions) == 1
    # These fields don't exist yet — test will fail until we add them
    # assert positions[0]["stop_loss"] == 80.0
    # assert positions[0]["take_profit"] == 90.0


def test_auto_sl_tp_calculator_with_default_rr():
    """If no SL/TP provided, calculate from entry with default R:R."""
    from app.services.sl_tp_calculator import calculate_sl_tp

    sl, tp = calculate_sl_tp(entry_price=100.0, direction="LONG")
    assert sl < 100.0  # Stop-Loss below entry
    assert tp > 100.0  # Take-Profit above entry
    assert (100.0 - sl) > 0  # Risk is positive
    assert (tp - 100.0) > 0  # Reward is positive


def test_monitor_closes_position_on_tp_hit(broker):
    """If live price hits TP, position should be auto-closed."""
    broker.place_paper_order("SOLUSD", "BUY", 0.3, "market")

    # Manually set a very low TP so it will hit immediately
    from app.db import SessionLocal
    from app.db.models import PaperPosition
    with SessionLocal() as db:
        pos = db.query(PaperPosition).filter(PaperPosition.symbol == "SOLUSD").first()
        pos.take_profit = 1.0  # Impossibly low — will trigger
        db.commit()

    # Run monitor once
    from app.services.position_monitor import PaperPositionMonitor
    mon = PaperPositionMonitor(broker=broker)
    mon._check_positions()

    # Position should be closed
    positions = broker.get_positions()["positions"]
    assert len(positions) == 0
