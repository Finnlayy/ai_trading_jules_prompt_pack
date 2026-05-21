"""
Pure-Python Statistical Test Battery for Regime Detection.
No scipy dependency — uses only numpy + stdlib math.

Tests:
  1. Hurst R/S Analysis          — long-term memory
  2. Ljung-Box Q-Test            — serial autocorrelation
  3. Variance Ratio Test         — return predictability
  4. Runs Test                   — non-random sequences
  5. ARCH Test                   — volatility clustering
"""

from __future__ import annotations

import math
from typing import List, Sequence, Dict

import numpy as np


def _autocorr(x: np.ndarray, lag: int) -> float:
    """Autocorrelation at given lag."""
    n = len(x)
    if lag >= n:
        return 0.0
    x_mean = np.mean(x)
    c0 = np.sum((x - x_mean) ** 2) / n
    if c0 == 0:
        return 0.0
    c_lag = np.sum((x[:-lag] - x_mean) * (x[lag:] - x_mean)) / n
    return c_lag / c0


# ─── 1. HURST R/S ANALYSIS ────────────────────────────────────────────────────

def hurst_rs(prices: Sequence[float], max_lag: int = 100) -> float:
    """
    Hurst Exponent via Rescaled Range (R/S) Analysis.
    H > 0.5  → persistent (trending)
    H = 0.5  → random walk
    H < 0.5  → anti-persistent (mean-reverting)
    """
    returns = np.diff(np.log(np.maximum(prices, 1e-12)))
    n = len(returns)
    if n < 20:
        return 0.5

    lags = []
    rs_values = []

    # Use lag sizes from 10 up to max_lag, geometrically spaced
    for lag in range(10, min(max_lag, n // 4) + 1, max(1, (min(max_lag, n // 4) - 10) // 20)):
        chunks = n // lag
        if chunks < 2:
            continue

        rs_list = []
        for i in range(chunks):
            chunk = returns[i * lag : (i + 1) * lag]
            mean_chunk = np.mean(chunk)
            cumdev = np.cumsum(chunk - mean_chunk)
            r = np.max(cumdev) - np.min(cumdev)
            s = np.std(chunk, ddof=1)
            if s > 1e-12:
                rs_list.append(r / s)

        if rs_list:
            lags.append(math.log(lag))
            rs_values.append(math.log(np.mean(rs_list)))

    if len(lags) < 3:
        return 0.5

    # Linear regression: log(R/S) = a + H * log(lag)
    x = np.array(lags)
    y = np.array(rs_values)
    n_pts = len(x)
    x_mean, y_mean = np.mean(x), np.mean(y)
    ss_xy = np.sum((x - x_mean) * (y - y_mean))
    ss_xx = np.sum((x - x_mean) ** 2)
    if ss_xx == 0:
        return 0.5
    hurst = ss_xy / ss_xx
    return float(np.clip(hurst, 0.0, 1.0))


# ─── 2. LJUNG-BOX Q-TEST ──────────────────────────────────────────────────────

def ljung_box(returns: Sequence[float], lags: int = 10) -> Dict[str, float]:
    """
    Ljung-Box Q-test for serial autocorrelation.
    H0: returns are independently distributed (no autocorrelation).
    """
    r = np.array(returns)
    n = len(r)
    if n < lags + 5:
        return {"q_stat": 0.0, "p_value": 1.0, "reject_h0": False}

    q_stat = 0.0
    for k in range(1, lags + 1):
        rho = _autocorr(r, k)
        q_stat += (rho ** 2) / (n - k)
    q_stat *= n * (n + 2)

    # Approximate p-value using chi-squared with 'lags' degrees of freedom
    # p = 1 - CDF_chi2(q_stat, lags)
    # Wilson-Hilferty approximation for chi2 CDF:
    p_value = _chi2_cdf_approx(q_stat, lags)

    # Critical value at 5% for lags df
    critical = _chi2_critical(lags, 0.05)

    return {
        "q_stat": float(round(q_stat, 4)),
        "p_value": float(round(1.0 - p_value, 4)),
        "critical_5pct": float(round(critical, 4)),
        "reject_h0": bool(q_stat > critical),  # True = autocorrelation detected
        "lags": int(lags),
    }


def _chi2_cdf_approx(x: float, df: int) -> float:
    """Wilson-Hilferty approximation for chi2 CDF."""
    if x <= 0:
        return 0.0
    z = math.pow(x / df, 1.0 / 3.0) - (1.0 - 2.0 / (9.0 * df))
    z /= math.sqrt(2.0 / (9.0 * df))
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _chi2_critical(df: int, alpha: float) -> float:
    """Approximate chi2 critical value."""
    # For df >= 10, use normal approximation
    if df >= 10:
        z = 1.645 if alpha == 0.05 else 2.326 if alpha == 0.01 else 1.282
        return df * (1.0 - 2.0 / (9.0 * df) + z * math.sqrt(2.0 / (9.0 * df))) ** 3
    # Small df table (approximate)
    table_5pct = {1: 3.84, 2: 5.99, 3: 7.81, 4: 9.49, 5: 11.07,
                  6: 12.59, 7: 14.07, 8: 15.51, 9: 16.92, 10: 18.31}
    return table_5pct.get(df, df * 1.5)


# ─── 3. VARIANCE RATIO TEST ───────────────────────────────────────────────────

def variance_ratio(returns: Sequence[float], horizons: Sequence[int] = (2, 4, 8, 16)) -> Dict[str, Dict]:
    """
    Variance Ratio Test for multiple horizons.
    VR(k) ≈ 1  → random walk
    VR(k) > 1  → positive autocorrelation (momentum)
    VR(k) < 1  → negative autocorrelation (mean-reversion)
    """
    r = np.array(returns)
    n = len(r)
    var_1 = np.var(r, ddof=1)
    if var_1 == 0:
        return {f"k{h}": {"vr": 1.0, "z_stat": 0.0} for h in horizons}

    results = {}
    for k in horizons:
        if k >= n // 2:
            continue
        # k-period returns
        k_returns = np.array([np.sum(r[i:i+k]) for i in range(0, n - k + 1, k)])
        var_k = np.var(k_returns, ddof=1)
        vr = (var_k / k) / var_1 if var_1 > 0 else 1.0

        # Z-statistic (Lo-MacKinlay)
        # z = (VR(k) - 1) / sqrt(phi(k))
        m = (n - k + 1) // k
        phi = 2.0 * (2.0 * k - 1.0) * (k - 1.0) / (3.0 * k * n) if n > 0 else 1.0
        z_stat = (vr - 1.0) / math.sqrt(max(phi, 1e-12))

        results[f"k{k}"] = {
            "vr": float(round(float(vr), 4)),
            "z_stat": float(round(float(z_stat), 4)),
            "predictable": bool(abs(z_stat) > 1.96),  # 5% significance
        }
    return results


# ─── 4. RUNS TEST ─────────────────────────────────────────────────────────────

def runs_test(returns: Sequence[float]) -> Dict[str, float]:
    """
    Runs Test: detects non-random sequences of positive/negative returns.
    H0: returns are random (independent).
    """
    r = np.array(returns)
    n = len(r)
    if n < 20:
        return {"n_runs": 0, "expected_runs": 0.0, "z_stat": 0.0, "reject_h0": False}

    # Binary sequence: 1 = positive, 0 = negative
    signs = (r > 0).astype(int)
    n_pos = int(np.sum(signs))
    n_neg = n - n_pos

    if n_pos == 0 or n_neg == 0:
        return {"n_runs": 1, "expected_runs": 1.0, "z_stat": 0.0, "reject_h0": False}

    # Count runs
    n_runs = 1
    for i in range(1, n):
        if signs[i] != signs[i - 1]:
            n_runs += 1

    # Expected runs under H0
    expected = (2.0 * n_pos * n_neg) / n + 1.0
    variance = (2.0 * n_pos * n_neg * (2.0 * n_pos * n_neg - n)) / (n ** 2 * (n - 1.0))

    if variance <= 0:
        z_stat = 0.0
    else:
        z_stat = (n_runs - expected) / math.sqrt(variance)

    return {
        "n_runs": int(n_runs),
        "expected_runs": float(round(expected, 2)),
        "z_stat": float(round(z_stat, 4)),
        "reject_h0": bool(abs(z_stat) > 1.96),
    }


# ─── 5. ARCH TEST ─────────────────────────────────────────────────────────────

def arch_test(returns: Sequence[float], lags: int = 5) -> Dict[str, float]:
    """
    ARCH Test: regress squared returns on lagged squared returns.
    H0: no ARCH effects (no volatility clustering).
    """
    r = np.array(returns)
    n = len(r)
    if n < lags + 10:
        return {"f_stat": 0.0, "r_squared": 0.0, "reject_h0": False}

    # Squared returns (demeaned)
    e2 = (r - np.mean(r)) ** 2

    # Prepare lagged matrix
    y = e2[lags:]
    X = np.zeros((len(y), lags))
    for i in range(lags):
        X[:, i] = e2[lags - 1 - i : n - 1 - i]

    # OLS: y = X @ beta
    # beta = (X'X)^-1 X'y
    XtX = X.T @ X
    if np.linalg.det(XtX) < 1e-12:
        return {"f_stat": 0.0, "r_squared": 0.0, "reject_h0": False}

    beta = np.linalg.inv(XtX) @ (X.T @ y)
    y_pred = X @ beta
    y_mean = np.mean(y)

    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y_mean) ** 2)
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    # F-statistic = (R²/k) / ((1-R²)/(n-k-1))
    k = lags
    n_obs = len(y)
    if r_squared >= 1.0 or n_obs <= k + 1:
        f_stat = 0.0
    else:
        f_stat = (r_squared / k) / ((1.0 - r_squared) / (n_obs - k - 1.0))

    # Approximate critical F at 5%
    critical_f = 2.0 + 0.5 * k  # rough approximation

    return {
        "f_stat": float(round(float(f_stat), 4)),
        "r_squared": float(round(float(r_squared), 4)),
        "critical_f": float(round(critical_f, 4)),
        "reject_h0": bool(f_stat > critical_f),  # True = ARCH detected
        "lags": int(lags),
    }


# ─── FULL BATTERY ─────────────────────────────────────────────────────────────

def run_battery(prices: Sequence[float]) -> Dict:
    """
    Run the complete statistical test battery on a price series.
    Returns structured results for regime classification.
    """
    prices_arr = np.array(prices)
    if len(prices_arr) < 50:
        return {"error": "Need at least 50 prices"}

    returns = np.diff(np.log(np.maximum(prices_arr, 1e-12)))
    if len(returns) < 20:
        return {"error": "Insufficient returns"}

    hurst = hurst_rs(prices_arr)
    lb = ljung_box(returns)
    vr = variance_ratio(returns)
    rt = runs_test(returns)
    arch = arch_test(returns)

    return {
        "hurst": {"value": float(round(hurst, 4)), "interpretation": _hurst_interp(hurst)},
        "ljung_box": lb,
        "variance_ratio": vr,
        "runs_test": rt,
        "arch_test": arch,
        "summary": {
            "uncorrelated": bool(not lb["reject_h0"]),  # LB doesn't reject = uncorrelated
            "predictable": bool(any(v.get("predictable", False) for v in vr.values())),
            "random_sequence": bool(not rt["reject_h0"]),
            "vol_clustering": bool(arch["reject_h0"]),
            "memory": float(hurst),
        }
    }


def _hurst_interp(h: float) -> str:
    if h > 0.55:
        return "persistent (trending)"
    elif h < 0.45:
        return "anti-persistent (mean-reverting)"
    else:
        return "random walk"
