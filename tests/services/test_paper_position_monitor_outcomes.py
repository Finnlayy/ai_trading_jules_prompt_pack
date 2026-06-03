from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.db import SessionLocal
from app.db.models import AgentLearningEvent, AgentReviewEvent, PaperOutcome, PaperPosition, SignalCandidate
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum, SignalReview
from app.schemas.m8_payload import M8Payload
from app.services.confidence_registry import confidence_registry
from app.services.kraken_paper_broker import KrakenPaperBroker
from app.services.lifecycle_recorder import lifecycle_recorder, candidate_id_for_signal
from app.services.position_monitor import PaperPositionMonitor


@pytest.fixture(autouse=True)
def reset_paper_outcome_state():
    confidence_registry.reset_all()
    with SessionLocal() as db:
        db.query(AgentLearningEvent).delete()
        db.query(AgentReviewEvent).delete()
        db.query(PaperOutcome).delete()
        db.query(SignalCandidate).delete()
        db.query(PaperPosition).delete()
        db.commit()
    yield
    confidence_registry.reset_all()


def _payload() -> M8Payload:
    return M8Payload(
        signal_id="live-SOLUSDT-1h-default-1700000000000",
        symbol="SOLUSD",
        timeframe="1h",
        direction="LONG",
        timestamp=datetime.now(timezone.utc).isoformat(),
        entry_price=100.0,
        stop_price=90.0,
        target_price=120.0,
        confluence_score=82.0,
        crisis_score=5.0,
        mc_dispersion=1.0,
        spread=2.0,
        strategy_id="default",
    )


def test_paper_position_monitor_writes_outcome_and_learning_on_tp(monkeypatch):
    broker = KrakenPaperBroker()
    broker.reset_paper_account(new_balance=1000.0)
    monkeypatch.setattr(broker, "_get_live_price", lambda _symbol: (100.0, 100.0))

    payload = _payload()
    candidate_id = candidate_id_for_signal(payload.signal_id)
    lifecycle_recorder.record_candidate(payload, candidate_id=candidate_id)
    lifecycle_recorder.record_ai_review(
        candidate_id=candidate_id,
        payload=payload,
        ai_review=SignalReview(
            schema_version="1.0",
            signal_id=payload.signal_id,
            decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
            confidence=0.8,
            reason_codes=["TEST"],
            risk_flags=[],
            requires_human_review=False,
            audit_trace={
                "provider": "mock",
                "scouts": {
                    "technical": {
                        "decision": "PROCEED_TO_SIMULATION",
                        "confidence": 0.8,
                        "report": "Confidence: 0.80\napproved",
                    },
                    "risk": {
                        "decision": "REJECT",
                        "confidence": 0.7,
                        "report": "Confidence: 0.70\nrejected",
                    },
                },
            },
        ),
    )
    confidence_registry.record_scout_review("SOLUSD", "technical", "LONG", "PROCEED_TO_SIMULATION", 0.8)
    confidence_registry.record_scout_review("SOLUSD", "risk", "LONG", "REJECT", 0.7)

    result = broker.place_paper_order(
        "SOLUSD",
        "BUY",
        1.0,
        "market",
        stop_loss=90.0,
        take_profit=101.0,
        candidate_id=candidate_id,
        signal_id=payload.signal_id,
        strategy_id=payload.strategy_id,
        timeframe=payload.timeframe,
        risk_decision="PROCEED_TO_SIMULATION",
        opened_by_loop=True,
    )
    assert result["status"] == "ok"
    monkeypatch.setattr(broker, "_get_live_price", lambda _symbol: (102.0, 102.0))

    monitor = PaperPositionMonitor(broker=broker)
    monitor._check_positions()

    with SessionLocal() as db:
        outcomes = db.query(PaperOutcome).all()
        learning = {
            row.scout_name: row.was_correct
            for row in db.query(AgentLearningEvent).all()
        }
        open_positions = db.query(PaperPosition).filter(PaperPosition.status == "open").all()
        candidate = db.query(SignalCandidate).filter(SignalCandidate.candidate_id == candidate_id).one()

    stats = confidence_registry.get_symbol_stats("SOLUSD")

    assert len(outcomes) == 1
    assert outcomes[0].close_reason == "TAKE_PROFIT"
    assert outcomes[0].win is True
    assert learning == {"technical": True, "risk": False}
    assert open_positions == []
    assert candidate.status == "paper_closed"
    assert stats.long_stats.total == 1
    assert stats.long_stats.wins == 1
    assert stats.scout_stats["technical"].correct_calls == 1
    assert stats.scout_stats["risk"].correct_calls == 0
