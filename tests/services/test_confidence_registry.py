import pytest
from app.services.confidence_registry import ConfidenceRegistry, ScoutReviewParams, ScoutStats, DirectionStats, SymbolStats


@pytest.fixture
def registry(tmp_path):
    path = tmp_path / "test_confidence.json"
    return ConfidenceRegistry(filepath=str(path))


def test_scout_stats_record_call(registry):
    s = ScoutStats()
    s.record_call("PROCEED_TO_SIMULATION", 0.8, was_correct=True)
    assert s.calls == 1
    assert s.approvals == 1
    assert s.correct_calls == 1
    assert s.accuracy == 1.0

    s.record_call("REJECT", 0.6, was_correct=False)
    assert s.calls == 2
    assert s.rejections == 1
    assert s.accuracy == 0.5
    assert s.avg_confidence == pytest.approx(0.7)


def test_direction_stats(registry):
    d = DirectionStats()
    d.record_trade(pnl_pct=2.5, rr=2.5, win=True)
    d.record_trade(pnl_pct=-1.0, rr=2.0, win=False)
    assert d.total == 2
    assert d.win_rate == 0.5
    assert d.avg_pnl_pct == pytest.approx(0.75)
    assert d.avg_rr == pytest.approx(2.25)


def test_symbol_context_empty(registry):
    ctx = registry.get_symbol_context("BTCUSDT", "LONG")
    assert "BTCUSDT" in ctx
    assert "LONG" in ctx
    assert "Total signals reviewed: 0" in ctx


def test_record_scout_review(registry):
    registry.record_scout_review(ScoutReviewParams("BTCUSDT", "technical", "LONG", "PROCEED_TO_SIMULATION", 0.8, True))
    registry.record_scout_review(ScoutReviewParams("BTCUSDT", "technical", "LONG", "REJECT", 0.6, False))

    stats = registry.get_symbol_stats("BTCUSDT")
    assert stats.scout_stats["technical"].calls == 2
    assert stats.scout_stats["technical"].accuracy == 0.5

    weight = registry.get_scout_weight("BTCUSDT", "technical")
    assert weight == 0.5  # 2 calls < 3 threshold


def test_scout_weight_with_enough_calls(registry):
    for i in range(5):
        registry.record_scout_review(ScoutReviewParams("BTCUSDT", "risk", "LONG", "PROCEED_TO_SIMULATION", 0.7, i < 4))

    weight = registry.get_scout_weight("BTCUSDT", "risk")
    # 4/5 = 0.8 accuracy + specialization bonus for 5 calls
    import math
    exp_bonus = min(math.log10(5) / 3.0, 1.0)
    spec_score = 0.8 * exp_bonus
    expected = 0.8 + min(spec_score * 0.15, 0.15)
    assert weight == pytest.approx(expected)


def test_record_signal_review(registry):
    registry.record_signal_review("BTCUSDT", confluence=80.0, crisis=10.0, direction="LONG")
    registry.record_signal_review("BTCUSDT", confluence=70.0, crisis=15.0, direction="LONG")

    stats = registry.get_symbol_stats("BTCUSDT")
    assert stats.total_signals == 2
    assert stats.avg_confluence == 75.0
    assert stats.avg_crisis == 12.5


def test_record_trade_outcome(registry):
    registry.record_trade_outcome("BTCUSDT", "LONG", pnl_pct=3.0, rr=3.0, win=True)
    registry.record_trade_outcome("BTCUSDT", "LONG", pnl_pct=-1.0, rr=2.0, win=False)
    registry.record_trade_outcome("BTCUSDT", "SHORT", pnl_pct=2.0, rr=2.5, win=True)

    ctx = registry.get_symbol_context("BTCUSDT", "LONG")
    assert "50% win rate" in ctx
    assert "1W/1L" in ctx

    ctx_short = registry.get_symbol_context("BTCUSDT", "SHORT")
    assert "100% win rate" in ctx_short


def test_reset_symbol(registry):
    registry.record_signal_review("BTCUSDT", confluence=80.0, crisis=10.0, direction="LONG")
    assert registry.get_symbol_stats("BTCUSDT").total_signals == 1

    registry.reset_symbol("BTCUSDT")
    assert registry.get_symbol_stats("BTCUSDT").total_signals == 0


def test_reset_all(registry):
    registry.record_signal_review("BTCUSDT", confluence=80.0, crisis=10.0, direction="LONG")
    registry.record_signal_review("ETHUSDT", confluence=75.0, crisis=12.0, direction="SHORT")

    registry.reset_all()
    assert registry.get_symbol_stats("BTCUSDT").total_signals == 0
    assert registry.get_symbol_stats("ETHUSDT").total_signals == 0


def test_persistence(tmp_path):
    path = tmp_path / "persist.json"
    reg1 = ConfidenceRegistry(filepath=str(path))
    reg1.record_scout_review(ScoutReviewParams("BTCUSDT", "technical", "LONG", "PROCEED_TO_SIMULATION", 0.9, True))
    reg1.record_trade_outcome("BTCUSDT", "LONG", pnl_pct=2.0, rr=2.0, win=True)

    reg2 = ConfidenceRegistry(filepath=str(path))
    stats = reg2.get_symbol_stats("BTCUSDT")
    assert stats.scout_stats["technical"].calls == 1
    assert stats.long_stats.total == 1


def test_serialize_deserialize_roundtrip(registry):
    registry.record_scout_review(ScoutReviewParams("BTCUSDT", "macro", "SHORT", "REJECT", 0.5, True))
    registry.record_signal_review("BTCUSDT", confluence=65.0, crisis=20.0, direction="SHORT")
    registry.record_trade_outcome("BTCUSDT", "SHORT", pnl_pct=1.5, rr=1.8, win=True)

    dumped = registry.dump()
    assert "BTCUSDT" in dumped
    assert dumped["BTCUSDT"]["scout_stats"]["macro"]["calls"] == 1
    assert dumped["BTCUSDT"]["short_stats"]["total"] == 1
