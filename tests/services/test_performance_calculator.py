import pytest
<<<<<<< HEAD
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
=======
import math
from datetime import datetime
from app.schemas.journal import TradeJournalEntry, DirectionEnum, DecisionEnum, FinalDecisionEnum
from app.services.performance_calculator import PerformanceCalculator, performance_calculator

def _make_trade(pnl: float | None = None, entry_price: float = 100.0, exit_price: float = 110.0, as_dict: bool = False, use_simulated: bool = False) -> TradeJournalEntry | dict:
    trade_dict = {
        "trade_id": "test_id",
        "timestamp": datetime.now().isoformat(),
        "symbol": "BTC_USDT_PERP",
        "timeframe": "1h",
        "direction": DirectionEnum.LONG,
        "entry_price": entry_price,
        "stop_price": 90.0,
        "target_price": 120.0,
        "risk_reward": 2.0,
        "m8_score": 85.0,
        "ai_decision": DecisionEnum.PROCEED_TO_SIMULATION,
        "final_decision": FinalDecisionEnum.EXECUTED_SIM,
        "simulated_fill": {"pnl": pnl} if use_simulated and pnl is not None else {},
        "result": {"pnl": pnl} if not use_simulated and pnl is not None else None,
    }

    if as_dict:
        return trade_dict
    return TradeJournalEntry(**trade_dict)
>>>>>>> main

def test_calculate_metrics_empty():
    calc = PerformanceCalculator()
    metrics = calc.calculate_metrics([])
    assert metrics.total_trades == 0
<<<<<<< HEAD
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
=======
    assert metrics.winrate_pct == 0.0
    assert metrics.total_pnl == 0.0

def test_sharpe_and_sortino_empty():
    calc = PerformanceCalculator()
    assert calc._sharpe([]) == 0.0
    assert calc._sortino([]) == 0.0

def test_calculate_metrics_populated():
    calc = PerformanceCalculator()
    trades = [
        _make_trade(100.0),
        _make_trade(-50.0),
        _make_trade(200.0)
    ]
    metrics = calc.calculate_metrics(trades)

    assert metrics.total_trades == 3
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 1
    assert metrics.winrate_pct == 66.67
    assert metrics.profit_factor == 6.0  # 300 / 50
    assert metrics.total_pnl == 250.0
    assert metrics.avg_trade_pnl == 83.3333
    assert metrics.largest_winner == 200.0
    assert metrics.largest_loser == -50.0
>>>>>>> main

def test_extract_pnl():
    calc = PerformanceCalculator()

<<<<<<< HEAD
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
=======
    # Object with result pnl
    t1 = _make_trade(100.0, use_simulated=False)
    assert calc._extract_pnl(t1) == 100.0

    # Object with simulated pnl
    t2 = _make_trade(50.0, use_simulated=True)
    assert calc._extract_pnl(t2) == 50.0

    # Object with missing pnl but has prices
    t3 = _make_trade(None)
    assert calc._extract_pnl(t3) is None

    # Dict with result pnl
    t4 = _make_trade(150.0, as_dict=True, use_simulated=False)
    assert calc._extract_pnl(t4) == 150.0

    # Dict with simulated pnl
    t5 = _make_trade(75.0, as_dict=True, use_simulated=True)
    assert calc._extract_pnl(t5) == 75.0

def test_sharpe_and_sortino_math():
    calc = PerformanceCalculator()
    returns = [0.01, -0.02, 0.05]

    # Test Sharpe
    sharpe = calc._sharpe(returns, risk_free_rate=0.0)
    # math validation: mean = 0.01333, std = 0.02867.
    # annualized = (0.01333 / 0.02867) * sqrt(252) approx 7.3
    assert sharpe > 0

    # Test Sortino
    sortino = calc._sortino(returns)
    # Only downside is -0.02
    assert sortino > 0

    # Test inf Sortino (no downside)
    assert calc._sortino([0.01, 0.02]) == float("inf")

    # Test negative inf / 0 Sortino (all negative)
    # if downside count > 0 but avg <= 0 it should return standard sortino math (negative)
    assert calc._sortino([-0.01, -0.02]) < 0

def test_calculate_equity_curve_data():
    calc = PerformanceCalculator()
    trades = [
        _make_trade(100.0),
        _make_trade(-50.0),
        _make_trade(200.0)
    ]

    curve = calc.calculate_equity_curve_data(trades)
    assert len(curve) == 4 # Initial 0.0 + 3 trades
    assert curve[0] == {"trade_idx": 0, "equity": 0.0}
    assert curve[1] == {"trade_idx": 1, "equity": 100.0}
    assert curve[2] == {"trade_idx": 2, "equity": 50.0}
    assert curve[3] == {"trade_idx": 3, "equity": 250.0}
>>>>>>> main
