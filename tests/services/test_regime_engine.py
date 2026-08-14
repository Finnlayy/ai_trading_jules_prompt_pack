import pytest
from unittest.mock import patch

from app.services.regime_engine import RegimeEngine, RegimeEnum, SignalModeEnum

# Pytest fixture for RegimeEngine
@pytest.fixture
def engine():
    return RegimeEngine(allow_rw1_signals=False)

@pytest.fixture
def engine_allow_rw1():
    return RegimeEngine(allow_rw1_signals=True)

# --- classify() Tests ---

@patch("app.services.regime_engine.run_battery")
def test_classify_error(mock_run_battery, engine):
    """Test when run_battery returns an error (e.g., insufficient data)."""
    mock_run_battery.return_value = {"error": "Insufficient returns"}

    result = engine.classify([100.0, 101.0])

    assert result["regime"] == RegimeEnum.UNKNOWN
    assert result["signal_mode"] == SignalModeEnum.FULL_SUITE
    assert result["confidence"] == 0.0
    assert "error" in result["battery"]


@patch("app.services.regime_engine.run_battery")
def test_classify_rw1(mock_run_battery, engine):
    """Test classification of RW1 (Strong Efficient)."""
    mock_run_battery.return_value = {
        "summary": {
            "uncorrelated": True,
            "predictable": False,
            "random_sequence": True,
            "vol_clustering": False
        },
        "hurst": {"value": 0.5}
    }

    result = engine.classify([100.0] * 50)

    assert result["regime"] == RegimeEnum.RW1
    assert result["signal_mode"] == SignalModeEnum.NO_SIGNALS
    assert result["confidence"] == 0.9

@patch("app.services.regime_engine.run_battery")
def test_classify_rw1_allow_signals(mock_run_battery, engine_allow_rw1):
    """Test classification of RW1 with allow_rw1_signals=True."""
    mock_run_battery.return_value = {
        "summary": {
            "uncorrelated": True,
            "predictable": False,
            "random_sequence": True,
            "vol_clustering": False
        },
        "hurst": {"value": 0.5}
    }

    result = engine_allow_rw1.classify([100.0] * 50)

    assert result["regime"] == RegimeEnum.RW1
    assert result["signal_mode"] == SignalModeEnum.MR_ONLY
    assert result["confidence"] == 0.9

@patch("app.services.regime_engine.run_battery")
def test_classify_rw3(mock_run_battery, engine):
    """Test classification of RW3 (Heteroskedastic/Vol clustering)."""
    mock_run_battery.return_value = {
        "summary": {
            "uncorrelated": True,
            "predictable": False,
            "random_sequence": True,
            "vol_clustering": True
        },
        "hurst": {"value": 0.5}
    }

    result = engine.classify([100.0] * 50)

    assert result["regime"] == RegimeEnum.RW3
    assert result["signal_mode"] == SignalModeEnum.VOL_BREAKOUT
    assert result["confidence"] == 0.8

@patch("app.services.regime_engine.run_battery")
def test_classify_inefficient_trend(mock_run_battery, engine):
    """Test classification of Inefficient Trend (hurst > 0.55)."""
    mock_run_battery.return_value = {
        "summary": {
            "uncorrelated": False,  # Not uncorrelated -> Inefficient
            "predictable": False,
            "random_sequence": True,
            "vol_clustering": False
        },
        "hurst": {"value": 0.7}
    }

    result = engine.classify([100.0] * 50)

    assert result["regime"] == RegimeEnum.INEFFICIENT_TREND
    assert result["signal_mode"] == SignalModeEnum.TREND_ONLY
    # confidence = min(0.95, 0.6 + abs(0.7 - 0.5)) = 0.8
    assert result["confidence"] == 0.8

@patch("app.services.regime_engine.run_battery")
def test_classify_inefficient_mr(mock_run_battery, engine):
    """Test classification of Inefficient Mean Reversion (hurst < 0.45)."""
    mock_run_battery.return_value = {
        "summary": {
            "uncorrelated": False,  # Not uncorrelated -> Inefficient
            "predictable": False,
            "random_sequence": True,
            "vol_clustering": False
        },
        "hurst": {"value": 0.3}
    }

    result = engine.classify([100.0] * 50)

    assert result["regime"] == RegimeEnum.INEFFICIENT_MR
    assert result["signal_mode"] == SignalModeEnum.MR_ONLY
    # confidence = min(0.95, 0.6 + abs(0.3 - 0.5)) = 0.8
    assert result["confidence"] == 0.8

@patch("app.services.regime_engine.run_battery")
def test_classify_rw2_inefficient_middle_hurst(mock_run_battery, engine):
    """Test fallback to RW2 when inefficient but hurst is near 0.5."""
    mock_run_battery.return_value = {
        "summary": {
            "uncorrelated": False,
            "predictable": False,
            "random_sequence": True,
            "vol_clustering": False
        },
        "hurst": {"value": 0.5}  # between 0.45 and 0.55
    }

    result = engine.classify([100.0] * 50)

    assert result["regime"] == RegimeEnum.RW2
    assert result["signal_mode"] == SignalModeEnum.FULL_SUITE
    assert result["confidence"] == 0.7

@patch("app.services.regime_engine.run_battery")
def test_classify_rw2_predictable(mock_run_battery, engine):
    """Test RW2 when uncorrelated but predictable."""
    mock_run_battery.return_value = {
        "summary": {
            "uncorrelated": True,
            "predictable": True,
            "random_sequence": True,
            "vol_clustering": False
        },
        "hurst": {"value": 0.5}
    }

    result = engine.classify([100.0] * 50)

    assert result["regime"] == RegimeEnum.RW2
    assert result["signal_mode"] == SignalModeEnum.FULL_SUITE
    assert result["confidence"] == 0.7

@patch("app.services.regime_engine.run_battery")
def test_classify_rw2_fallback(mock_run_battery, engine):
    """Test final fallback to RW2 when other conditions aren't met."""
    mock_run_battery.return_value = {
        "summary": {
            "uncorrelated": True,
            "predictable": False,
            "random_sequence": False, # random_sequence=False forces fallback
            "vol_clustering": False
        },
        "hurst": {"value": 0.5}
    }

    result = engine.classify([100.0] * 50)

    assert result["regime"] == RegimeEnum.RW2
    assert result["signal_mode"] == SignalModeEnum.FULL_SUITE
    assert result["confidence"] == 0.5


# --- should_trade() Tests ---

@patch.object(RegimeEngine, "classify")
def test_should_trade_no_signals(mock_classify, engine):
    """Test should_trade when signal mode is NO_SIGNALS."""
    mock_classify.return_value = {
        "regime": RegimeEnum.RW1,
        "signal_mode": SignalModeEnum.NO_SIGNALS,
        "confidence": 0.9,
    }

    result = engine.should_trade([100.0] * 50)

    assert result["trade_allowed"] is False
    assert result["regime"] == RegimeEnum.RW1
    assert result["signal_mode"] == SignalModeEnum.NO_SIGNALS
    assert result["confidence"] == 0.9
    assert result["reason"] == "Market is strongly efficient — no edge available"

@patch.object(RegimeEngine, "classify")
def test_should_trade_trend_only(mock_classify, engine):
    """Test should_trade when signal mode allows trading."""
    mock_classify.return_value = {
        "regime": RegimeEnum.INEFFICIENT_TREND,
        "signal_mode": SignalModeEnum.TREND_ONLY,
        "confidence": 0.85,
    }

    result = engine.should_trade([100.0] * 50)

    assert result["trade_allowed"] is True
    assert result["regime"] == RegimeEnum.INEFFICIENT_TREND
    assert result["signal_mode"] == SignalModeEnum.TREND_ONLY
    assert result["confidence"] == 0.85
    assert result["reason"] == "Persistent memory detected — trend following"

@patch.object(RegimeEngine, "classify")
def test_should_trade_unknown_regime(mock_classify, engine):
    """Test should_trade when regime is UNKNOWN."""
    mock_classify.return_value = {
        "regime": RegimeEnum.UNKNOWN,
        "signal_mode": SignalModeEnum.FULL_SUITE,
        "confidence": 0.0,
    }

    result = engine.should_trade([100.0] * 50)

    assert result["trade_allowed"] is True  # FULL_SUITE permits trading
    assert result["regime"] == RegimeEnum.UNKNOWN
    assert result["reason"] == "Insufficient data for classification"
