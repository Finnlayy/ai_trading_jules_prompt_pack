"""Epic 3 Task 3.4 — Delta analysis: backtest vs. real trades."""

from __future__ import annotations

from app.services.delta_analyzer import compare_backtest_vs_real


def test_delta_analyzer_detects_slippage():
    """Backtest price vs. real fill price must show slippage delta."""
    backtest_trade = {
        "type": "BUY",
        "bar_index": 10,
        "price": 80.00,
        "volume": 0.5,
    }
    real_trade = {
        "trade_id": "paper_abc",
        "symbol": "SOLUSD",
        "direction": "LONG",
        "fill_price": 80.15,
        "volume": 0.5,
    }

    delta = compare_backtest_vs_real(backtest_trade, real_trade)

    assert delta["slippage"] == 0.15  # 80.15 - 80.00
    assert abs(delta["slippage_pct"] - 0.1875) < 0.01  # (0.15 / 80.00) * 100


def test_delta_analyzer_detects_volume_mismatch():
    """Different volumes between backtest and real must be flagged."""
    backtest_trade = {"type": "BUY", "price": 80.00, "volume": 1.0}
    real_trade = {"trade_id": "paper_abc", "fill_price": 80.00, "volume": 0.5}

    delta = compare_backtest_vs_real(backtest_trade, real_trade)

    assert delta["volume_mismatch"] is True
    assert delta["volume_delta"] == -0.5
