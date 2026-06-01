import pytest
from app.services.performance_calculator import PerformanceCalculator, PerformanceMetrics

@pytest.fixture
def calculator():
    return PerformanceCalculator()

def test_empty_trades(calculator):
    metrics = calculator.calculate_metrics([])
    assert isinstance(metrics, PerformanceMetrics)
    assert metrics.total_trades == 0
    assert metrics.winning_trades == 0
    assert metrics.losing_trades == 0
    assert metrics.total_pnl == 0.0

def test_extract_pnl():
    # Test dictionary with result pnl
    entry1 = {"result": {"pnl": 10.5}}
    assert PerformanceCalculator._extract_pnl(entry1) == 10.5

    # Test dictionary with simulated_fill pnl
    entry2 = {"simulated_fill": {"pnl": -5.2}}
    assert PerformanceCalculator._extract_pnl(entry2) == -5.2

    # Test dictionary without pnl
    entry3 = {"result": {"other": "value"}}
    assert PerformanceCalculator._extract_pnl(entry3) is None

    # Test empty dict
    entry4 = {}
    assert PerformanceCalculator._extract_pnl(entry4) is None

def test_calculate_metrics(calculator):
    # Mock some trades as dicts with 'result' containing 'pnl'
    trades = [
        {"result": {"pnl": 50.0}},
        {"result": {"pnl": 30.0}},
        {"result": {"pnl": -20.0}},
        {"result": {"pnl": -10.0}},
        {"result": {"pnl": 0.0}} # A break-even trade
    ]
    metrics = calculator.calculate_metrics(trades)
    assert isinstance(metrics, PerformanceMetrics)
    assert metrics.total_trades == 5
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 2
    assert metrics.winrate_pct == 40.0

    # 80 / 30 = 2.6666... -> 2.667
    assert metrics.profit_factor == 2.667

    # Total pnl = 50 + 30 - 20 - 10 = 50. Expectancy = 50 / 5 = 10.0
    assert metrics.expectancy == 10.0
    assert metrics.total_pnl == 50.0
    assert metrics.avg_winner == 40.0 # (50+30)/2
    assert metrics.avg_loser == -15.0 # (-20-10)/2
    assert metrics.largest_winner == 50.0
    assert metrics.largest_loser == -20.0

def test_calculate_equity_curve_data(calculator):
    trades = [
        {"result": {"pnl": 10.0}},
        {"result": {"pnl": -5.0}},
        {"result": {"pnl": 15.0}}
    ]
    data = calculator.calculate_equity_curve_data(trades)
    assert isinstance(data, list)
    assert len(data) == 4 # Includes the 0.0 starting point
    assert data[0] == {"trade_idx": 0, "equity": 0.0}
    assert data[1] == {"trade_idx": 1, "equity": 10.0}
    assert data[2] == {"trade_idx": 2, "equity": 5.0}
    assert data[3] == {"trade_idx": 3, "equity": 20.0}

def test_sharpe_ratio():
    returns = [0.01, 0.02, -0.01, 0.005, -0.005]
    # Simple check that it computes without errors and returns a float
    sharpe = PerformanceCalculator._sharpe(returns, risk_free_rate=0.0)
    assert isinstance(sharpe, float)
    assert sharpe > 0 # Since mean is slightly positive (0.02/5)

    # Test empty returns
    assert PerformanceCalculator._sharpe([]) == 0.0

def test_sortino_ratio():
    returns = [0.01, 0.02, -0.01, 0.005, -0.005]
    # Simple check that it computes without errors and returns a float
    sortino = PerformanceCalculator._sortino(returns)
    assert isinstance(sortino, float)
    assert sortino > 0

    # Test empty returns
    assert PerformanceCalculator._sortino([]) == 0.0

    # Test returns with no downside (should be inf if average is > 0)
    assert PerformanceCalculator._sortino([0.01, 0.02]) == float("inf")

def test_calculate_max_drawdown():
    # Equity curve starting at 0, goes up to 100, drops to 50, goes to 120
    equity_curve = [0.0, 100.0, 50.0, 60.0]
    pct, start_idx, end_idx = PerformanceCalculator._calculate_max_drawdown(equity_curve)

    # Drop from 100 to 50 is a 50% drawdown
    assert pct == 50.0
    assert start_idx == 1 # Index of 100
    assert end_idx == 2 # Index of 50

    # Test flat or always increasing equity curve
    pct2, _, _ = PerformanceCalculator._calculate_max_drawdown([0.0, 10.0, 20.0])
    assert pct2 == 0.0
