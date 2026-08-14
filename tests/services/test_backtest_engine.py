import pytest
from app.services.backtest_engine import run_bar_by_bar_backtest

def test_no_signals():
    ohlc = [[0, 100, 110, 90, 105, 1000]] * 10
    def rule(i, visible_bars):
        return None

    trades = run_bar_by_bar_backtest(ohlc, rule)
    assert trades == []

def test_buy_signal():
    ohlc = [
        [0, 100, 110, 90, 100, 1000],
    ]
    def rule(i, visible_bars):
        return "BUY"

    trades = run_bar_by_bar_backtest(ohlc, rule, initial_balance=1000.0, fee_pct=0.01)

    assert len(trades) == 1
    assert trades[0]["type"] == "BUY"
    assert trades[0]["price"] == 100
    assert trades[0]["volume"] == 1.0 # 1000 * 0.1 = 100 / 100 = 1.0
    assert trades[0]["fee"] == 1.0 # 100 * 0.01 = 1.0
    assert trades[0]["balance"] == 899.0 # 1000 - 100 - 1.0 = 899.0

def test_sell_signal():
    ohlc = [
        [0, 100, 110, 90, 100, 1000],
    ]
    def rule(i, visible_bars):
        return "SELL"

    trades = run_bar_by_bar_backtest(ohlc, rule, initial_balance=1000.0, fee_pct=0.01)

    assert len(trades) == 1
    assert trades[0]["type"] == "SELL"
    assert trades[0]["price"] == 100
    assert trades[0]["volume"] == 1.0 # 1000 * 0.1 = 100 / 100 = 1.0
    assert trades[0]["fee"] == 1.0 # 100 * 0.01 = 1.0
    assert trades[0]["balance"] == 899.0

def test_position_flip():
    ohlc = [
        [0, 100, 110, 90, 100, 1000], # BUY
        [1, 120, 130, 110, 120, 1000], # SELL
    ]
    def rule(i, visible_bars):
        if i == 0:
            return "BUY"
        elif i == 1:
            return "SELL"
        return None

    trades = run_bar_by_bar_backtest(ohlc, rule, initial_balance=1000.0, fee_pct=0.00)

    assert len(trades) == 3
    # First trade: BUY
    assert trades[0]["type"] == "BUY"
    assert trades[0]["price"] == 100
    assert trades[0]["volume"] == 1.0
    assert trades[0]["balance"] == 900.0 # 1000 - 100

    # Second trade: CLOSE_LONG
    assert trades[1]["type"] == "CLOSE_LONG"
    assert trades[1]["price"] == 120
    assert trades[1]["pnl"] == 20.0 # (120 - 100) * 1.0
    assert trades[1]["balance"] == 920.0 # 900 + 20

    # Third trade: SELL
    assert trades[2]["type"] == "SELL"
    assert trades[2]["price"] == 120
    assert trades[2]["volume"] == round(920.0 * 0.1 / 120, 8) # 920 * 0.1 / 120
    assert trades[2]["balance"] == 828.0 # 920 - 92

def test_visible_bars_no_future_leak():
    ohlc = [
        [0, 100, 110, 90, 100, 1000],
        [1, 101, 111, 91, 101, 1000],
        [2, 102, 112, 92, 102, 1000],
    ]

    seen_bars = []
    def rule(i, visible_bars):
        seen_bars.append(len(visible_bars))
        return None

    run_bar_by_bar_backtest(ohlc, rule)

    assert seen_bars == [1, 2, 3]
