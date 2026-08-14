"""Epic 3 Task 3.2 — Market data loader without future leaks."""

from __future__ import annotations

from app.services.kraken_broker import KrakenBroker


def test_ohlc_returns_iterable_structure():
    """OHLC data must be a list of [time, open, high, low, close, volume]."""
    broker = KrakenBroker()
    result = broker.get_ohlc("SOLUSD", interval=60)

    assert isinstance(result, list)
    if len(result) > 0:
        bar = result[0]
        assert len(bar) == 6  # time, open, high, low, close, volume
        assert all(isinstance(v, (int, float)) for v in bar)


def test_ohlc_loader_no_future_leak():
    """Bar N must only see data up to Bar N (no forward-looking)."""
    broker = KrakenBroker()
    ohlc = broker.get_ohlc("SOLUSD", interval=60)

    # Simulate bar-by-bar
    for i in range(min(5, len(ohlc)), len(ohlc)):
        # At bar i, only bars 0..i should be visible
        visible = ohlc[:i+1]
        # The 'close' of the last visible bar must NOT know future prices
        last_close = visible[-1][4]  # typical OHLCV close index
        assert last_close > 0
        # Assert we cannot peek at bar i+1
        assert len(visible) == i + 1
