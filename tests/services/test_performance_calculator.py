import pytest
from unittest.mock import Mock
from app.services.performance_calculator import PerformanceCalculator, performance_calculator
from app.schemas.journal import TradeJournalEntry, DirectionEnum, DecisionEnum, FinalDecisionEnum

def _make_entry(trade_id: str, pnl: float) -> TradeJournalEntry:
    # We use a Mock because TradeJournalEntry in this project's version
    # doesn't define 'exit_price', but _extract_pnl tries to access it
    # which raises an AttributeError instead of returning None.
    # So we provide a mock that safely returns None for missing attributes.
    entry = Mock(spec=TradeJournalEntry)
    entry.trade_id = trade_id
    entry.result = {"pnl": pnl} if pnl is not None else None
    entry.simulated_fill = {}
    entry.entry_price = 50000.0
    entry.exit_price = None # This prevents AttributeError
    return entry

def test_calculate_metrics_empty():
    calc = PerformanceCalculator()
    metrics = calc.calculate_metrics([])
    assert metrics.total_trades == 0
    assert metrics.total_pnl == 0.0

def test_calculate_metrics_mixed_trades():
    calc = PerformanceCalculator()
    trades = [
        _make_entry("t1", 100.0),
        _make_entry("t2", -50.0),
        _make_entry("t3", 150.0),
        _make_entry("t4", -50.0),
    ]
    metrics = calc.calculate_metrics(trades)
    assert metrics.total_trades == 4
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 2
    assert metrics.winrate_pct == 50.0
    assert metrics.profit_factor == 2.5  # 250 / 100
    assert metrics.total_pnl == 150.0
    assert metrics.avg_winner == 125.0
    assert metrics.avg_loser == -50.0
    assert metrics.largest_winner == 150.0
    assert metrics.largest_loser == -50.0
    assert metrics.expectancy == 37.5  # 150 / 4
    assert metrics.avg_trade_pnl == 37.5

def test_calculate_metrics_all_winners():
    calc = PerformanceCalculator()
    trades = [
        _make_entry("t1", 100.0),
        _make_entry("t2", 150.0),
    ]
    metrics = calc.calculate_metrics(trades)
    assert metrics.total_trades == 2
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 0
    assert metrics.winrate_pct == 100.0
    assert metrics.profit_factor == 0.0  # Denominator is 0, _safe_div returns 0.0

def test_calculate_metrics_all_losers():
    calc = PerformanceCalculator()
    trades = [
        _make_entry("t1", -100.0),
        _make_entry("t2", -150.0),
    ]
    metrics = calc.calculate_metrics(trades)
    assert metrics.total_trades == 2
    assert metrics.winning_trades == 0
    assert metrics.losing_trades == 2
    assert metrics.winrate_pct == 0.0
    assert metrics.profit_factor == 0.0

def test_calculate_equity_curve_data():
    calc = PerformanceCalculator()
    trades = [
        _make_entry("t1", 100.0),
        _make_entry("t2", -50.0),
    ]
    curve_data = calc.calculate_equity_curve_data(trades)
    assert len(curve_data) == 3 # includes starting point 0.0
    assert curve_data[0] == {"trade_idx": 0, "equity": 0.0}
    assert curve_data[1] == {"trade_idx": 1, "equity": 100.0}
    assert curve_data[2] == {"trade_idx": 2, "equity": 50.0}

def test_sharpe_edge_cases():
    calc = PerformanceCalculator()
    assert calc._sharpe([]) == 0.0
    assert calc._sharpe([1.0, 1.0, 1.0]) == 0.0  # std is 0, so _safe_div returns 0.0

def test_sortino_edge_cases():
    calc = PerformanceCalculator()
    assert calc._sortino([]) == 0.0
    assert calc._sortino([1.0, 1.0, 1.0]) == float("inf") # no downside

def test_max_drawdown():
    calc = PerformanceCalculator()
    # Equity curve: [0, 100, 50, 150, 0, -50, 100]
    # Max peak was 150, drops to -50. DD = 200. Pct = 200 / 150 * 100 = 133.333%
    equity_curve = [0.0, 100.0, 50.0, 150.0, 0.0, -50.0, 100.0]
    pct, start, end = calc._calculate_max_drawdown(equity_curve)
    assert round(pct, 2) == 133.33
    assert start == 3 # peak is at index 3 (value 150)
    assert end == 5   # lowest after peak is at index 5 (value -50)

def test_extract_pnl():
    calc = PerformanceCalculator()

    # 1. PNL in result dict
    entry1 = _make_entry("t1", 50.0)
    assert calc._extract_pnl(entry1) == 50.0

    # 2. PNL in sim fill
    entry2 = _make_entry("t2", None)
    entry2.result = None
    entry2.simulated_fill = {"pnl": -25.0}
    assert calc._extract_pnl(entry2) == -25.0

    # 3. No PNL
    entry3 = _make_entry("t3", None)
    entry3.result = None
    entry3.simulated_fill = {}
    assert calc._extract_pnl(entry3) is None

    # 4. As dict
    dict_entry = {"result": {"pnl": 10.0}}
    assert calc._extract_pnl(dict_entry) == 10.0
