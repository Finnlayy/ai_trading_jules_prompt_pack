from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.academy_policy.backtesting.backtest_runner import BacktestRunner


@pytest.fixture
def test_kpi_dataset():
    # 50 rows to have enough data points for backtests
    index = pd.date_range("2026-06-01 12:00:00", periods=50, freq="1min")
    np.random.seed(42)
    
    # Generate mock observations/actions/KPIs
    scout_index = np.random.randint(0, 16, size=50)
    difficulty = np.random.randint(1, 4, size=50)
    total_reward = np.random.uniform(-1.0, 1.5, size=50)
    accuracy = np.random.uniform(0.4, 0.9, size=50)
    calibration = np.random.uniform(0.4, 0.9, size=50)
    ab_lift = np.random.uniform(-0.05, 0.1, size=50)
    
    # Close price for asset (e.g. simulated BTC/USDT price or index)
    close = np.zeros(50)
    close[0] = 100.0
    for i in range(1, 50):
        close[i] = close[i-1] * (1.0 + np.random.uniform(-0.01, 0.012))
        
    df = pd.DataFrame({
        "scout_index": scout_index,
        "difficulty": difficulty,
        "total_reward": total_reward,
        "accuracy": accuracy,
        "calibration": calibration,
        "ab_lift": ab_lift,
        "close": close,
    }, index=index)
    
    # Fill standard OHLCV columns if needed by backtrader
    df["open"] = df["close"] * 0.999
    df["high"] = df["close"] * 1.002
    df["low"] = df["close"] * 0.998
    df["volume"] = 1000.0
    
    return df


@pytest.fixture
def backtest_params():
    return {
        "target_scout_index": 3,
        "min_reward": 0.2,
        "min_accuracy": 0.6,
        "initial_cash": 10000.0,
    }


def test_backtest_runner_initialization():
    runner = BacktestRunner()
    assert runner is not None


@pytest.mark.parametrize("backend", ["backtrader", "vectorbt"])
def test_backends_unified_output(test_kpi_dataset, backtest_params, backend):
    runner = BacktestRunner()
    if backend == "backtrader":
        results = runner.run_backtrader(test_kpi_dataset, backtest_params)
    else:
        results = runner.run_vectorbt(test_kpi_dataset, backtest_params)
        
    # Verify result dictionary structure
    assert isinstance(results, dict)
    for key in ["sharpe_ratio", "max_drawdown", "calmar_ratio", "total_return", "equity_curve", "drawdown_curve", "positions"]:
        assert key in results
        
    assert isinstance(results["sharpe_ratio"], float)
    assert isinstance(results["max_drawdown"], float)
    assert isinstance(results["calmar_ratio"], float)
    assert isinstance(results["total_return"], float)
    
    assert isinstance(results["equity_curve"], pd.Series)
    assert isinstance(results["drawdown_curve"], pd.Series)
    assert isinstance(results["positions"], pd.DataFrame)
    
    # Assert length matches dataset index length
    assert len(results["equity_curve"]) == len(test_kpi_dataset)
    assert len(results["drawdown_curve"]) == len(test_kpi_dataset)


def test_backtrader_fails_gracefully_on_empty_data(backtest_params):
    runner = BacktestRunner()
    empty_df = pd.DataFrame()
    with pytest.raises(ValueError):
        runner.run_backtrader(empty_df, backtest_params)


def test_vectorbt_fails_gracefully_on_empty_data(backtest_params):
    runner = BacktestRunner()
    empty_df = pd.DataFrame()
    with pytest.raises(ValueError):
        runner.run_vectorbt(empty_df, backtest_params)
