"""Tests for the Strategy Engine and Registry."""

from __future__ import annotations

import pytest

from app.services.strategy_engine import (
    BaseStrategy,
    CISDStrategy,
    PatternEnhancedStrategy,
    StrategyRegistry,
    StrategyScore,
    strategy_registry,
)
from app.services.cisd_scorer import Candle as CISDCandle


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_registry():
    """Reset the singleton registry before every test."""
    strategy_registry.reset()
    yield
    strategy_registry.reset()


@pytest.fixture
def sample_bars():
    """Generate 100 synthetic candles."""
    bars = []
    base = 100.0
    for i in range(100):
        o = base + (i % 5) * 0.1
        c = o + (i % 3) * 0.1
        h = max(o, c) + 0.2
        l = min(o, c) - 0.2
        v = 1000.0 + i * 10
        bars.append(CISDCandle(ts=i * 60_000, o=o, h=h, l=l, c=c, v=v))
    return bars


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

def test_strategy_registry_singleton():
    reg1 = StrategyRegistry()
    reg2 = StrategyRegistry()
    assert reg1 is reg2


def test_default_strategies_loaded_after_reset():
    strategy_registry.reset()
    assert "default" in strategy_registry.list_strategies()
    assert "pattern_enhanced" in strategy_registry.list_strategies()


def test_get_active_strategy_default():
    strat = strategy_registry.get_active_strategy()
    assert strat.strategy_id == "default"
    assert isinstance(strat, CISDStrategy)


def test_switch_strategy():
    strategy_registry.set_active_strategy("pattern_enhanced")
    assert strategy_registry.active_strategy_id == "pattern_enhanced"
    assert strategy_registry.last_switch is not None


def test_switch_to_unknown_strategy_raises():
    with pytest.raises(KeyError):
        strategy_registry.set_active_strategy("nonexistent")


def test_unregister_non_default():
    strategy_registry.register(CISDStrategy(strategy_id="custom_cisd"))
    strategy_registry.unregister("custom_cisd")
    assert "custom_cisd" not in strategy_registry.list_strategies()


def test_cannot_unregister_default():
    with pytest.raises(ValueError):
        strategy_registry.unregister("default")


def test_strategy_switch_persists_to_disk():
    strategy_registry.set_active_strategy("pattern_enhanced")
    # Simulate new registry instance reading persisted file
    fresh = StrategyRegistry.__new__(StrategyRegistry)
    fresh._initialized = False
    fresh.__init__()
    # Note: because singleton is shared, this just validates persist path exists
    assert strategy_registry._persist_path.exists()


# ---------------------------------------------------------------------------
# CISD Strategy tests
# ---------------------------------------------------------------------------

def test_cisd_strategy_scores_bars(sample_bars):
    strat = CISDStrategy()
    scores = strat.score_bars(sample_bars)
    assert len(scores) == len(sample_bars)
    for s in scores:
        assert s.direction in ("LONG", "SHORT", "NEUTRAL")
        assert 0.0 <= s.confluence_score <= 100.0
        assert 0.0 <= s.confidence <= 1.0


def test_cisd_strategy_metadata():
    strat = CISDStrategy()
    meta = strat.get_metadata()
    assert meta.strategy_id == "default"
    assert meta.strategy_type == "cisd"


# ---------------------------------------------------------------------------
# Pattern Enhanced Strategy tests
# ---------------------------------------------------------------------------

def test_pattern_enhanced_strategy_combines_scores(sample_bars):
    strat = PatternEnhancedStrategy()
    scores = strat.score_bars(sample_bars)
    assert len(scores) == len(sample_bars)
    for s in scores:
        assert s.direction in ("LONG", "SHORT", "NEUTRAL")
        assert 0.0 <= s.confluence_score <= 100.0
        assert "pattern_type" in s.metadata or "cisd_confluence" in s.metadata


def test_pattern_enhanced_metadata():
    strat = PatternEnhancedStrategy()
    meta = strat.get_metadata()
    assert meta.strategy_type == "pattern_enhanced"


def test_pattern_enhanced_invalid_weights():
    with pytest.raises(ValueError):
        PatternEnhancedStrategy(cisd_weight=1.5, pattern_weight=0.5)


# ---------------------------------------------------------------------------
# Base strategy ABC
# ---------------------------------------------------------------------------

def test_base_strategy_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseStrategy("id", "name")
