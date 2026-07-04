from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.academy_policy.backtesting.backtest_runner import BacktestRunner
from app.services.academy_policy.backtesting.optimizer import scipy_optimize, vectorbt_grid_search


@pytest.fixture
def mock_dataset():
    index = pd.date_range("2026-06-01 12:00:00", periods=20, freq="1min")
    np.random.seed(42)
    
    df = pd.DataFrame({
        "scout_index": np.random.randint(0, 16, size=20),
        "difficulty": np.random.randint(1, 4, size=20),
        "total_reward": np.random.uniform(-0.5, 1.0, size=20),
        "accuracy": np.random.uniform(0.5, 0.85, size=20),
        "calibration": np.random.uniform(0.5, 0.85, size=20),
        "ab_lift": np.random.uniform(-0.02, 0.05, size=20),
        "close": np.linspace(100.0, 110.0, 20),
    }, index=index)
    
    df["open"] = df["close"] * 0.999
    df["high"] = df["close"] * 1.001
    df["low"] = df["close"] * 0.998
    df["volume"] = 500.0
    
    return df


@pytest.fixture
def initial_params():
    return {
        "target_scout_index": 3,
        "min_reward": 0.1,
        "min_accuracy": 0.5,
        "initial_cash": 10000.0,
    }


@pytest.fixture
def objective_weights():
    return {
        "sharpe": 0.5,
        "drawdown": 0.3,
        "calmar": 0.2,
    }


def test_scipy_optimize_differential_evolution(mock_dataset, initial_params, objective_weights):
    runner = BacktestRunner()
    results = scipy_optimize(
        runner=runner,
        data=mock_dataset,
        initial_params=initial_params,
        weights=objective_weights,
        method="differential_evolution",
        maxiter=2,  # Keep iterations low for testing speed
    )
    
    assert isinstance(results, dict)
    assert "optimal_params" in results
    assert "sharpe_ratio" in results
    assert "max_drawdown" in results
    assert "calmar_ratio" in results
    assert "iterations" in results
    
    assert isinstance(results["optimal_params"], dict)
    assert "min_reward" in results["optimal_params"]
    assert "min_accuracy" in results["optimal_params"]
    
    assert isinstance(results["sharpe_ratio"], float)
    assert isinstance(results["max_drawdown"], float)
    assert isinstance(results["calmar_ratio"], float)
    assert isinstance(results["iterations"], int)


def test_scipy_optimize_minimize(mock_dataset, initial_params, objective_weights):
    runner = BacktestRunner()
    results = scipy_optimize(
        runner=runner,
        data=mock_dataset,
        initial_params=initial_params,
        weights=objective_weights,
        method="minimize",
        maxiter=2,
    )
    
    assert isinstance(results, dict)
    assert "optimal_params" in results
    assert isinstance(results["optimal_params"], dict)


def test_vectorbt_grid_search(mock_dataset):
    param_grid = {
        "min_reward": [0.0, 0.2],
        "min_accuracy": [0.5, 0.7],
    }
    
    results_df = vectorbt_grid_search(mock_dataset, param_grid)
    
    assert isinstance(results_df, pd.DataFrame)
    assert not results_df.empty
    # Expect combination index or rows for parameter sweeps
    assert "sharpe_ratio" in results_df.columns
    assert "max_drawdown" in results_df.columns
    assert "calmar_ratio" in results_df.columns
