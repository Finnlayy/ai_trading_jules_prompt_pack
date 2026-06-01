import pytest
import numpy as np
from app.services.statistical_battery import (
    hurst_rs,
    ljung_box,
    variance_ratio,
    runs_test,
    arch_test,
    run_battery,
)

# Fixtures for generating test data
@pytest.fixture
def random_walk_prices():
    """Generates a random walk price series."""
    np.random.seed(42)
    returns = np.random.normal(0, 0.01, 1000)
    prices = 100 * np.exp(np.cumsum(returns))
    return prices

@pytest.fixture
def trending_prices():
    """Generates a strongly trending price series."""
    np.random.seed(42)
    # Positive drift
    returns = np.random.normal(0.005, 0.01, 1000)
    prices = 100 * np.exp(np.cumsum(returns))
    return prices

@pytest.fixture
def mean_reverting_prices():
    """Generates a mean-reverting price series (Ornstein-Uhlenbeck)."""
    np.random.seed(42)
    prices = [100.0]
    mean = 100.0
    theta = 0.5 # Higher reversion speed to ensure clear < 0.5 Hurst
    sigma = 1.0 # Volatility
    for _ in range(999):
        # dx = theta * (mu - x) * dt + sigma * dW
        dp = theta * (mean - prices[-1]) + np.random.normal(0, sigma)
        prices.append(prices[-1] + dp)
    return np.array(prices)

@pytest.fixture
def random_returns():
    """Generates pure random returns."""
    np.random.seed(42)
    return np.random.normal(0, 0.01, 1000)

@pytest.fixture
def autocorrelated_returns():
    """Generates autocorrelated returns (AR(1) process)."""
    np.random.seed(42)
    returns = [0.0]
    phi = 0.8 # Strong positive autocorrelation
    for _ in range(999):
        ret = phi * returns[-1] + np.random.normal(0, 0.01)
        returns.append(ret)
    return np.array(returns)

@pytest.fixture
def volatility_clustered_returns():
    """Generates returns with volatility clustering (GARCH-like or strong chunks)."""
    np.random.seed(42)
    returns = []
    # Alternate between low and high volatility regimes, with longer chunks
    for i in range(10):
        if i % 2 == 0:
            returns.extend(np.random.normal(0, 0.001, 200)) # Low vol
        else:
            returns.extend(np.random.normal(0, 0.05, 200))  # High vol
    return np.array(returns)


# ─── 1. HURST R/S ANALYSIS TESTS ──────────────────────────────────────────────

def test_hurst_rs_short_sequence():
    """Test Hurst returns 0.5 for short sequences (< 20 returns -> < 21 prices)."""
    prices = np.linspace(100, 110, 20)
    assert hurst_rs(prices) == 0.5

def test_hurst_rs_random_walk(random_walk_prices):
    """Test Hurst exponent is around 0.5 for a random walk."""
    h = hurst_rs(random_walk_prices)
    # Allow some wiggle room due to finite sample size
    assert 0.40 <= h <= 0.60

def test_hurst_rs_trending(trending_prices):
    """Test Hurst exponent is > 0.5 for trending series."""
    h = hurst_rs(trending_prices)
    assert h > 0.55

def test_hurst_rs_mean_reverting(mean_reverting_prices):
    """Test Hurst exponent is < 0.5 for mean-reverting series."""
    h = hurst_rs(mean_reverting_prices)
    # With stronger mean reversion, this should be clearly < 0.5
    assert h < 0.5


# ─── 2. LJUNG-BOX Q-TEST TESTS ────────────────────────────────────────────────

def test_ljung_box_short_sequence():
    """Test Ljung-Box returns default values for short sequences."""
    returns = np.random.normal(0, 0.01, 10) # n < lags + 5 (10 + 5 = 15)
    res = ljung_box(returns)
    assert res["q_stat"] == 0.0
    assert res["p_value"] == 1.0
    assert res["reject_h0"] is False

def test_ljung_box_random_returns(random_returns):
    """Test Ljung-Box does not reject H0 for random returns."""
    res = ljung_box(random_returns)
    assert res["reject_h0"] is False

def test_ljung_box_autocorrelated(autocorrelated_returns):
    """Test Ljung-Box rejects H0 for autocorrelated returns."""
    res = ljung_box(autocorrelated_returns)
    assert res["reject_h0"] is True


# ─── 3. VARIANCE RATIO TEST TESTS ─────────────────────────────────────────────

def test_variance_ratio_random(random_returns):
    """Test Variance Ratio is close to 1.0 for random returns."""
    res = variance_ratio(random_returns, horizons=(2, 4))
    for k, v in res.items():
        # VR shouldn't be statistically different from 1 (z_stat < 1.96)
        assert not v["predictable"]
        assert 0.8 <= v["vr"] <= 1.2

def test_variance_ratio_trending(autocorrelated_returns):
    """Test Variance Ratio > 1.0 for positively autocorrelated (trending) returns."""
    res = variance_ratio(autocorrelated_returns, horizons=(2, 4))
    for k, v in res.items():
        assert v["vr"] > 1.1 # Should be > 1
        assert v["predictable"] is True

def test_variance_ratio_mean_reverting(mean_reverting_prices):
    """Test Variance Ratio < 1.0 for mean-reverting returns."""
    returns = np.diff(np.log(mean_reverting_prices))
    res = variance_ratio(returns, horizons=(2, 4))
    for k, v in res.items():
        # Even with theta=0.5, VR might be closer to 0.95. Let's just check < 1
        assert v["vr"] < 1.0


# ─── 4. RUNS TEST TESTS ───────────────────────────────────────────────────────

def test_runs_test_short_sequence():
    """Test Runs test handles short sequences safely."""
    returns = np.random.normal(0, 0.01, 15)
    res = runs_test(returns)
    assert res["n_runs"] == 0
    assert res["reject_h0"] is False

def test_runs_test_random(random_returns):
    """Test Runs test does not reject H0 for random sequences."""
    res = runs_test(random_returns)
    assert res["reject_h0"] is False

def test_runs_test_trending():
    """Test Runs test rejects H0 for non-random (trending) sequences."""
    # A sequence with very few runs (long stretches of pos/neg)
    returns = np.concatenate([np.ones(50), -np.ones(50), np.ones(50), -np.ones(50)])
    res = runs_test(returns)
    assert res["reject_h0"] is True


# ─── 5. ARCH TEST TESTS ───────────────────────────────────────────────────────

def test_arch_test_short_sequence():
    """Test ARCH test handles short sequences safely."""
    returns = np.random.normal(0, 0.01, 10)
    res = arch_test(returns, lags=5)
    assert res["f_stat"] == 0.0
    assert res["reject_h0"] is False

def test_arch_test_constant_vol(random_returns):
    """Test ARCH test does not reject H0 for constant volatility."""
    res = arch_test(random_returns)
    assert res["reject_h0"] is False

def test_arch_test_volatility_clustering(volatility_clustered_returns):
    """Test ARCH test rejects H0 for volatility clustering."""
    res = arch_test(volatility_clustered_returns)
    assert res["reject_h0"] is True


# ─── FULL BATTERY TESTS ───────────────────────────────────────────────────────

def test_run_battery_short_sequence():
    """Test full battery handles short sequences."""
    prices = np.linspace(100, 110, 30)
    res = run_battery(prices)
    assert "error" in res

def test_run_battery_happy_path(random_walk_prices):
    """Test full battery runs successfully on valid data."""
    res = run_battery(random_walk_prices)

    assert "hurst" in res
    assert "value" in res["hurst"]
    assert "interpretation" in res["hurst"]

    assert "ljung_box" in res
    assert "variance_ratio" in res
    assert "runs_test" in res
    assert "arch_test" in res

    assert "summary" in res
    assert "uncorrelated" in res["summary"]
    assert "predictable" in res["summary"]
    assert "random_sequence" in res["summary"]
    assert "vol_clustering" in res["summary"]
    assert "memory" in res["summary"]
