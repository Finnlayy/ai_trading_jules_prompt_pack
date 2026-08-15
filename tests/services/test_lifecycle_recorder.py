from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.db.models import AgentLearningEvent, AgentReviewEvent, PaperOutcome, RiskDecisionEvent, SignalCandidate
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum, SignalReview
from app.schemas.journal import DecisionEnum as RiskDecisionEnum
from app.schemas.m8_payload import M8Payload
from app.services.lifecycle_recorder import LifecycleRecorder, candidate_id_for_signal


class FakeConfidenceRegistry:
    def __init__(self) -> None:
        self.signal_reviews: list[dict] = []
        self.scout_reviews: list[dict] = []
        self.trade_outcomes: list[dict] = []
        self.scout_outcomes: list[dict] = []

    def record_signal_review(self, **kwargs) -> None:
        self.signal_reviews.append(kwargs)

    def record_scout_review(self, params) -> None:
        self.scout_reviews.append(vars(params) if not isinstance(params, dict) else params)

    def record_trade_outcome(self, **kwargs) -> None:
        self.trade_outcomes.append(kwargs)

    def mark_scout_outcome(self, **kwargs) -> None:
        self.scout_outcomes.append(kwargs)


def _session_factory():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _payload() -> M8Payload:
    return M8Payload(
        signal_id="live-BTCUSDT-1m-default-1700000000000",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        timestamp="2026-05-20T10:00:00Z",
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        confluence_score=82.0,
        crisis_score=5.0,
        mc_dispersion=1.0,
        spread=2.0,
        strategy_id="default",
        pattern_detected="cisd",
        pattern_score=71.0,
    )


def test_lifecycle_recorder_writes_candidate_ai_and_risk_events():
    Session = _session_factory()
    confidence = FakeConfidenceRegistry()
    recorder = LifecycleRecorder(Session, confidence_registry=confidence)
    payload = _payload()
    candidate_id = candidate_id_for_signal(payload.signal_id)

    recorded_id = recorder.record_candidate(payload)
    ai_review = SignalReview(
        schema_version="1.0",
        signal_id=payload.signal_id,
        decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
        confidence=0.82,
        reason_codes=["TEST_APPROVED"],
        risk_flags=[],
        requires_human_review=False,
        audit_trace={
            "provider": "mock",
            "scouts": {
                "technical": {
                    "decision": "PROCEED_TO_SIMULATION",
                    "confidence": 0.84,
                    "report": "Confidence: 0.84\ntrend aligned",
                }
            },
        },
    )
    review_count = recorder.record_ai_review(
        candidate_id=candidate_id,
        payload=payload,
        ai_review=ai_review,
    )
    recorder.record_risk_decision(
        candidate_id=candidate_id,
        payload=payload,
        decision_result={
            "decision": RiskDecisionEnum.PROCEED_TO_SIMULATION,
            "reject_reason": None,
        },
        limits_snapshot={"source": "test"},
    )

    with Session() as db:
        candidate = db.query(SignalCandidate).one()
        review = db.query(AgentReviewEvent).one()
        risk = db.query(RiskDecisionEvent).one()

    assert recorded_id == candidate_id
    assert review_count == 1
    assert candidate.status == "ai_reviewed"
    assert candidate.features_json is not None
    assert review.scout_name == "technical"
    assert review.confidence == 0.84
    assert risk.decision == "PROCEED_TO_SIMULATION"
    assert confidence.signal_reviews == [
        {
            "symbol": "BTCUSDT",
            "confluence": 82.0,
            "crisis": 5.0,
            "direction": "LONG",
        }
    ]
    assert confidence.scout_reviews[0]["scout_name"] == "technical"
    assert confidence.scout_reviews[0]["was_correct"] is None


def test_lifecycle_recorder_can_update_candidate_status():
    Session = _session_factory()
    recorder = LifecycleRecorder(Session)
    payload = _payload()
    candidate_id = recorder.record_candidate(payload)

    recorder.update_candidate_status(candidate_id, "paper_opened")

    with Session() as db:
        candidate = db.query(SignalCandidate).one()

    assert candidate.status == "paper_opened"
    assert candidate.processed_at is not None


def test_lifecycle_recorder_records_paper_outcome_and_learning_events():
    Session = _session_factory()
    confidence = FakeConfidenceRegistry()
    recorder = LifecycleRecorder(Session, confidence_registry=confidence)
    payload = _payload()
    candidate_id = recorder.record_candidate(payload)
    ai_review = SignalReview(
        schema_version="1.0",
        signal_id=payload.signal_id,
        decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
        confidence=0.82,
        reason_codes=["TEST_APPROVED"],
        risk_flags=[],
        requires_human_review=False,
        audit_trace={
            "provider": "mock",
            "scouts": {
                "technical": {
                    "decision": "PROCEED_TO_SIMULATION",
                    "confidence": 0.84,
                    "report": "Confidence: 0.84\ntrend aligned",
                },
                "risk": {
                    "decision": "REJECT",
                    "confidence": 0.7,
                    "report": "Confidence: 0.70\nrisk objected",
                },
            },
        },
    )
    recorder.record_ai_review(candidate_id=candidate_id, payload=payload, ai_review=ai_review)

    trade_id = recorder.record_paper_outcome(
        position_snapshot={
            "candidate_id": candidate_id,
            "signal_id": payload.signal_id,
            "symbol": payload.symbol,
            "direction": payload.direction,
            "strategy_id": payload.strategy_id,
            "timeframe": payload.timeframe,
            "volume": 0.1,
            "avg_entry_price": 100.0,
            "stop_loss": 98.0,
        },
        close_result={
            "status": "ok",
            "trade_id": "paper-close-001",
            "fill_price": 104.0,
            "pnl": 0.4,
        },
        close_reason="TAKE_PROFIT",
    )

    with Session() as db:
        outcome = db.query(PaperOutcome).one()
        learning = {
            row.scout_name: row.was_correct
            for row in db.query(AgentLearningEvent).all()
        }
        candidate = db.query(SignalCandidate).one()

    assert trade_id == "paper-close-001"
    assert outcome.close_reason == "TAKE_PROFIT"
    assert outcome.win is True
    assert round(outcome.r_multiple, 2) == 2.0
    assert learning == {"technical": True, "risk": False}
    assert candidate.status == "paper_closed"
    assert confidence.trade_outcomes[0]["win"] is True
    assert confidence.scout_outcomes[0]["details"]["trade_id"] == "paper-close-001"
    assert confidence.scout_outcomes[0]["details"]["strategy_id"] == "default"
    assert confidence.scout_outcomes[0]["details"]["timeframe"] == "1m"
    assert confidence.scout_outcomes[0]["details"]["outcome_source"] == "live_paper"


def test_lifecycle_recorder_skips_duplicate_confidence_reviews_when_ai_layer_recorded():
    Session = _session_factory()
    confidence = FakeConfidenceRegistry()
    recorder = LifecycleRecorder(Session, confidence_registry=confidence)
    payload = _payload()
    candidate_id = recorder.record_candidate(payload)

    ai_review = SignalReview(
        schema_version="1.0",
        signal_id=payload.signal_id,
        decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
        confidence=0.82,
        reason_codes=["TEST_APPROVED"],
        risk_flags=[],
        requires_human_review=False,
        audit_trace={
            "confidence_recorded": True,
            "scouts": {
                "technical": {
                    "decision": "PROCEED_TO_SIMULATION",
                    "confidence": 0.84,
                    "report": "Confidence: 0.84\ntrend aligned",
                }
            },
        },
    )

    recorder.record_ai_review(candidate_id=candidate_id, payload=payload, ai_review=ai_review)

    with Session() as db:
        assert db.query(AgentReviewEvent).count() == 1
    assert confidence.signal_reviews == []
    assert confidence.scout_reviews == []
