from __future__ import annotations

import pytest

from app.schemas.ai_review import DecisionEnum as AIDecisionEnum, SignalReview
from app.schemas.m8_payload import M8Payload
from app.services.confidence_registry import confidence_registry
from app.services.portfolio_circuit_breaker import circuit_breaker_instance
from app.services.shadow_paper_engine import PAPER_EXECUTED, ShadowPaperEngine
from app.services.signal_generator import OHLCV, signal_generator_instance


def _bar(index: int, open_: float, high: float, low: float, close: float) -> OHLCV:
    return OHLCV(
        ts=1_700_000_000_000 + index * 60_000,
        o=open_,
        h=high,
        l=low,
        c=close,
        v=1000.0,
    )


def _payload(**overrides) -> M8Payload:
    data = {
        "signal_id": "paper-low-conf",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "direction": "LONG",
        "timestamp": "2023-11-14T22:13:20+00:00",
        "entry_price": 100.0,
        "stop_price": 99.0,
        "target_price": 102.0,
        "confluence_score": 50.0,
        "crisis_score": 45.0,
        "mc_dispersion": 1.0,
        "spread": 2.0,
    }
    data.update(overrides)
    return M8Payload(**data)


@pytest.fixture(autouse=True)
def reset_shared_state():
    confidence_registry.reset_all()
    circuit_breaker_instance.reset()
    yield
    confidence_registry.reset_all()
    circuit_breaker_instance.reset()


def test_simulator_uses_stop_first_for_ambiguous_long_candle():
    engine = ShadowPaperEngine()
    bars = [
        _bar(0, 100.0, 100.5, 99.8, 100.0),
        _bar(1, 100.0, 103.0, 98.5, 101.0),
    ]

    outcome = engine.simulate_trade(_payload(), bars, entry_index=0, max_holding_bars=5)

    assert outcome.exit_reason == "STOP_LOSS"
    assert outcome.exit_price == 99.0
    assert outcome.r_multiple == pytest.approx(-1.0)
    assert outcome.win is False


def test_simulator_uses_stop_first_for_ambiguous_short_candle():
    engine = ShadowPaperEngine()
    bars = [
        _bar(0, 100.0, 100.5, 99.8, 100.0),
        _bar(1, 100.0, 102.0, 97.0, 99.0),
    ]

    outcome = engine.simulate_trade(
        _payload(direction="SHORT", stop_price=101.0, target_price=98.0),
        bars,
        entry_index=0,
        max_holding_bars=5,
    )

    assert outcome.exit_reason == "STOP_LOSS"
    assert outcome.exit_price == 101.0
    assert outcome.r_multiple == pytest.approx(-1.0)
    assert outcome.win is False


@pytest.mark.asyncio
async def test_shadow_paper_executes_live_rejected_candidate(monkeypatch):
    engine = ShadowPaperEngine()
    bars = [
        _bar(0, 100.0, 100.5, 99.8, 100.0),
        _bar(1, 100.0, 102.2, 99.5, 102.0),
    ]
    payload = _payload(confluence_score=20.0, crisis_score=10.0)

    def fake_generate_payloads(**_kwargs):
        signal_generator_instance.last_raw_bars = bars
        signal_generator_instance.last_generation_summary = {"payloads_generated": 1}
        return [payload]

    monkeypatch.setattr(signal_generator_instance, "generate_payloads", fake_generate_payloads)
    monkeypatch.setattr("app.services.risk_engine.MIN_CONFLUENCE_SCORE", 70.0)

    replay = await engine.replay(
        symbol="BTCUSDT",
        timeframe="1m",
        bars=2,
        max_signals=1,
        use_ai=False,
    )

    row = replay["results"][0]
    assert row["live_decision"] == "REJECT"
    assert row["live_reject_reason"] == "LOW_CONFLUENCE"
    assert row["paper_decision"] == PAPER_EXECUTED
    assert row["outcome"]["exit_reason"] == "TAKE_PROFIT"
    assert replay["paper_executed"] == 1
    assert replay["live_rejected"] == 1


def test_record_learning_marks_existing_scout_calls_correct_on_win():
    engine = ShadowPaperEngine()
    payload = _payload(confluence_score=85.0, crisis_score=10.0)
    for scout_name in engine.SCOUT_NAMES:
        confidence_registry.record_scout_review(
            payload.symbol,
            scout_name,
            payload.direction,
            "PROCEED_TO_SIMULATION",
            0.7,
            was_correct=None,
        )
    outcome = engine.simulate_trade(
        payload,
        [_bar(0, 100.0, 100.5, 99.8, 100.0), _bar(1, 100.0, 102.2, 99.5, 102.0)],
        entry_index=0,
    )
    review = SignalReview(
        schema_version="1.0",
        signal_id=payload.signal_id,
        decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
        confidence=0.8,
        reason_codes=[],
        risk_flags=[],
        reject_reason=None,
        requires_human_review=False,
    )

    engine._record_learning(payload, review, outcome)

    stats = confidence_registry.get_symbol_stats(payload.symbol)
    assert stats.long_stats.total == 1
    assert stats.long_stats.wins == 1
    for scout_name in engine.SCOUT_NAMES:
        assert stats.scout_stats[scout_name].correct_calls == 1
