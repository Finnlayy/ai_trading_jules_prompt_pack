from __future__ import annotations

import os
import tempfile
import numpy as np
import pandas as pd
import pytest

from app.services.academy_policy.backtesting.visualizer import (
    plot_equity_curve,
    plot_drawdown,
    plot_kpi_time_series,
    plot_reward_history,
    plot_parameter_heatmap,
    plot_reward_distribution,
    plot_kpi_correlation,
)


@pytest.fixture
def visualization_data():
    index = pd.date_range("2026-06-01", periods=30, freq="D")
    np.random.seed(42)
    
    equity = pd.Series(np.linspace(10000.0, 12000.0, 30), index=index)
    benchmark = pd.Series(np.linspace(10000.0, 11000.0, 30), index=index)
    drawdown = pd.Series(np.random.uniform(-5.0, 0.0, 30), index=index)
    
    kpis = pd.DataFrame({
        "accuracy": np.random.uniform(0.5, 0.9, 30),
        "calibration": np.random.uniform(0.5, 0.9, 30),
        "ab_lift": np.random.uniform(-0.02, 0.08, 30),
    }, index=index)
    
    rewards = pd.Series(np.random.uniform(-1.0, 2.0, 30), index=index)
    
    scout_activations = [
        (pd.Timestamp("2026-06-05"), 3),
        (pd.Timestamp("2026-06-15"), 5),
        (pd.Timestamp("2026-06-25"), 2),
    ]
    
    opt_results = pd.DataFrame({
        "min_reward": np.repeat([0.0, 0.1, 0.2], 3),
        "min_accuracy": np.tile([0.5, 0.6, 0.7], 3),
        "sharpe_ratio": np.random.uniform(0.5, 2.0, 9),
    })
    
    # 16 scouts KPIs
    scout_kpis = pd.DataFrame(
        np.random.rand(30, 16),
        index=index,
        columns=[f"scout_{i}" for i in range(16)]
    )
    
    return {
        "equity": equity,
        "benchmark": benchmark,
        "drawdown": drawdown,
        "kpis": kpis,
        "rewards": rewards,
        "scout_activations": scout_activations,
        "opt_results": opt_results,
        "scout_kpis": scout_kpis,
    }


def test_plot_equity_curve(visualization_data):
    fig = plot_equity_curve(
        equity=visualization_data["equity"],
        benchmark=visualization_data["benchmark"],
        figsize=(8, 4),
        dpi=80
    )
    assert fig is not None

    # Test saving
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "equity.png")
        plot_equity_curve(
            equity=visualization_data["equity"],
            benchmark=visualization_data["benchmark"],
            save_path=save_path
        )
        assert os.path.exists(save_path)


def test_plot_drawdown(visualization_data):
    fig = plot_drawdown(
        drawdown=visualization_data["drawdown"],
        figsize=(8, 4),
        dpi=80
    )
    assert fig is not None


def test_plot_kpi_time_series(visualization_data):
    fig = plot_kpi_time_series(
        kpi_df=visualization_data["kpis"],
        scout_activations=visualization_data["scout_activations"],
        figsize=(10, 5),
        dpi=80
    )
    assert fig is not None


def test_plot_reward_history(visualization_data):
    fig = plot_reward_history(
        rewards=visualization_data["rewards"],
        figsize=(8, 4),
        dpi=80
    )
    assert fig is not None


def test_plot_parameter_heatmap(visualization_data):
    fig = plot_parameter_heatmap(
        results_df=visualization_data["opt_results"],
        x_col="min_reward",
        y_col="min_accuracy",
        metric_col="sharpe_ratio",
        figsize=(6, 5),
        dpi=80
    )
    assert fig is not None


def test_plot_reward_distribution(visualization_data):
    # Mock dataframe of rewards per scout name
    rewards_df = pd.DataFrame({
        "scout_name": np.repeat([f"scout_{i}" for i in range(4)], 20),
        "reward": np.random.normal(0.5, 0.2, 80)
    })
    fig = plot_reward_distribution(
        rewards_df=rewards_df,
        figsize=(8, 5),
        dpi=80
    )
    assert fig is not None


def test_plot_kpi_correlation(visualization_data):
    fig = plot_kpi_correlation(
        kpis_df=visualization_data["scout_kpis"],
        figsize=(10, 8),
        dpi=80
    )
    assert fig is not None
