import pytest
import numpy as np

from app.services.statistical_battery import (
    hurst_rs,
    ljung_box,
    variance_ratio,
    runs_test,
    arch_test,
    run_battery
)

def test_hurst_rs_random_walk():
    np.random.seed(42)
    prices = np.exp(np.cumsum(np.random.normal(0, 0.01, 1000)))
    h = hurst_rs(prices)
    # Random walk should have Hurst around 0.5
    assert 0.4 <= h <= 0.6

def test_hurst_rs_trending():
    np.random.seed(42)
    # create a trending series
    prices = np.exp(np.cumsum(np.random.normal(0.01, 0.01, 1000)))
    h = hurst_rs(prices)
    assert h > 0.55

def test_hurst_rs_mean_reverting():
    np.random.seed(42)
    # create an artificially mean reverting series
    returns = np.zeros(1000)
    for i in range(1, 1000):
        returns[i] = -0.5 * returns[i-1] + np.random.normal(0, 0.01)
    prices = np.exp(np.cumsum(returns))
    h = hurst_rs(prices)
    assert h < 0.5

def test_hurst_rs_insufficient_data():
    h = hurst_rs([1.0, 1.1, 1.2])
    assert h == 0.5

def test_ljung_box_independent():
    np.random.seed(42)
    returns = np.random.normal(0, 0.01, 100)
    res = ljung_box(returns)
    assert not res["reject_h0"]
    assert res["p_value"] > 0.05

def test_ljung_box_autocorrelated():
    np.random.seed(42)
    returns = np.zeros(100)
    for i in range(1, 100):
        returns[i] = 0.8 * returns[i-1] + np.random.normal(0, 0.01)
    res = ljung_box(returns)
    assert res["reject_h0"]
    assert res["p_value"] < 0.05

def test_ljung_box_insufficient_data():
    res = ljung_box([0.01, -0.01, 0.02])
    assert res["reject_h0"] == False
    assert res["q_stat"] == 0.0

def test_variance_ratio_random():
    np.random.seed(42)
    returns = np.random.normal(0, 0.01, 100)
    res = variance_ratio(returns)
    for k in res:
        assert not res[k]["predictable"]

def test_variance_ratio_predictable():
    np.random.seed(42)
    returns = np.zeros(100)
    for i in range(1, 100):
        returns[i] = 0.5 * returns[i-1] + np.random.normal(0, 0.01)
    res = variance_ratio(returns)
    # The first horizons should be predictable
    assert any(res[k]["predictable"] for k in res)

def test_runs_test_random():
    np.random.seed(42)
    returns = np.random.normal(0, 0.01, 100)
    res = runs_test(returns)
    assert not res["reject_h0"]

def test_runs_test_non_random():
    np.random.seed(42)
    # Alternating positive/negative runs
    returns = np.array([0.01, -0.01] * 50)
    res = runs_test(returns)
    assert res["reject_h0"]

def test_runs_test_insufficient_data():
    res = runs_test([0.01, -0.01, 0.02])
    assert res["reject_h0"] == False
    assert res["n_runs"] == 0

def test_arch_test_no_clustering():
    np.random.seed(42)
    returns = np.random.normal(0, 0.01, 500)
    res = arch_test(returns)
    assert not res["reject_h0"]

def test_arch_test_clustering():
    np.random.seed(42)
    # A simple structural break in volatility creates clustering that the arch test catches easily
    returns = np.zeros(2000)
    returns[:1000] = np.random.normal(0, 0.01, 1000)
    returns[1000:] = np.random.normal(0, 0.1, 1000)
    res = arch_test(returns)
    assert res["reject_h0"]

def test_arch_test_insufficient_data():
    res = arch_test([0.01, -0.01, 0.02])
    assert res["reject_h0"] == False
    assert res["f_stat"] == 0.0

def test_run_battery_integration():
    np.random.seed(42)
    prices = np.exp(np.cumsum(np.random.normal(0, 0.01, 500)))
    res = run_battery(prices)
    assert "error" not in res
    assert "hurst" in res
    assert "ljung_box" in res
    assert "variance_ratio" in res
    assert "runs_test" in res
    assert "arch_test" in res
    assert "summary" in res

def test_run_battery_insufficient_data():
    res = run_battery([1.0, 1.1, 1.2])
    assert "error" in res
    assert res["error"] == "Need at least 50 prices"
