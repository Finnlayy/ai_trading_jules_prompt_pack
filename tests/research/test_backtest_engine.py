"""Epic 3 Task 3.3 — Backtest engine with Pine Script v6 rules."""

from __future__ import annotations

from app.services.backtest_engine import run_bar_by_bar_backtest
from app.services.kraken_broker import KrakenBroker


def test_backtest_generates_trade_array():
    """A simple strategy must produce a trade array."""
    broker = KrakenBroker()
    ohlc = broker.get_ohlc("SOLUSD", interval=60)

    # Simple rule: BUY when close > open, SELL when close < open
    def simple_rule(bar_index, bars):
        bar = bars[bar_index]
        if bar[4] > bar[1]:  # close > open
            return "BUY"
        elif bar[4] < bar[1]:  # close < open
            return "SELL"
        return None

    trades = run_bar_by_bar_backtest(ohlc, simple_rule, initial_balance=1000)

    assert isinstance(trades, list)
    if len(ohlc) > 2:
        assert len(trades) > 0


def test_backtest_no_future_leak():
    """The rule must NEVER receive bars beyond current index."""
    broker = KrakenBroker()
    ohlc = broker.get_ohlc("SOLUSD", interval=60)

    peek_detected = []

    def spy_rule(bar_index, bars):
        if bar_index + 1 < len(ohlc):
            try:
                _ = bars[bar_index + 1]
                peek_detected.append(bar_index)
            except IndexError:
                pass
        return None

    run_bar_by_bar_backtest(ohlc, spy_rule, initial_balance=1000)
    assert len(peek_detected) == 0, f"Future leak detected at bars: {peek_detected}"
