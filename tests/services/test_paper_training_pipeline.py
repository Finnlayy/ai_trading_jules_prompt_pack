from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.db.models import AgentReviewEvent, RiskDecisionEvent, SignalCandidate
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum, SignalReview
from app.schemas.journal import DecisionEnum as RiskDecisionEnum
from app.schemas.m8_payload import M8Payload
from app.services.ai.gem_agents import GEM_AGENT_NAMES
from app.services.lifecycle_recorder import LifecycleRecorder, candidate_id_for_signal
from app.services.paper_training_pipeline import PaperTrainingPipeline


def _session_factory():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _payload(signal_id: str = "live-BTCUSDT-1m-default-1700000000000") -> M8Payload:
    return M8Payload(
        signal_id=signal_id,
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
    )


class FakeAIReviewLayer:
    def __init__(self, decision: AIDecisionEnum = AIDecisionEnum.PROCEED_TO_SIMULATION) -> None:
        self.decision = decision

    async def review_signal(self, payload: M8Payload) -> SignalReview:
        return SignalReview(
            schema_version="1.0",
            signal_id=payload.signal_id,
            decision=self.decision,
            confidence=0.83,
            reason_codes=["FAKE_AI"],
            risk_flags=[],
            requires_human_review=False,
            audit_trace={
                "provider": "mock",
                "scouts": {
                    "technical": {
                        "decision": self.decision.value,
                        "confidence": 0.83,
                        "report": "Confidence: 0.83\nfake technical approval",
                    },
                    "risk": {
                        "decision": self.decision.value,
                        "confidence": 0.79,
                        "report": "Confidence: 0.79\nfake risk approval",
                    },
                },
            },
        )


class FakeRiskEngine:
    def __init__(self, decision: RiskDecisionEnum, reason: str | None = None) -> None:
        self.decision = decision
        self.reason = reason
        self.current_bar = 0
        self.last_trade_bar = -1
        self.trades_today = 0

    def evaluate(self, _payload: M8Payload, _ai_review: SignalReview):
        return {"decision": self.decision, "reject_reason": self.reason}


class FakePaperBroker:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def place_paper_order(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "status": "ok",
            "trade_id": "paper_fake_001",
            "fill_price": 100.1,
            "mode": "paper",
        }


class FakeGem10AIReviewLayer:
    async def review_signal(self, payload: M8Payload) -> SignalReview:
        return SignalReview(
            schema_version="1.0",
            signal_id=payload.signal_id,
            decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
            confidence=0.81,
            reason_codes=["GEM10_TEST"],
            risk_flags=[],
            requires_human_review=False,
            audit_trace={
                "provider": "mock",
                "engine": "gem10_native",
                "scouts": {
                    name: {
                        "decision": AIDecisionEnum.PROCEED_TO_SIMULATION.value,
                        "confidence": 0.8,
                        "report": f"{name} test approval",
                    }
                    for name in GEM_AGENT_NAMES
                },
            },
        )


@pytest.mark.asyncio
async def test_paper_training_pipeline_records_full_approved_cycle(monkeypatch):
    async def fake_regime(_payload):
        return {"trade_allowed": True, "regime": "TEST", "reason": "ok"}

    Session = _session_factory()
    recorder = LifecycleRecorder(Session)
    broker = FakePaperBroker()
    risk = FakeRiskEngine(RiskDecisionEnum.PROCEED_TO_SIMULATION)
    pipeline = PaperTrainingPipeline(
        ai_review_layer=FakeAIReviewLayer(),
        risk_engine=risk,
        paper_broker=broker,
        recorder=recorder,
    )
    monkeypatch.setattr(pipeline, "_check_regime", fake_regime)

    payload = _payload()
    result = await pipeline.process_candidate(payload)

    with Session() as db:
        candidate = db.query(SignalCandidate).one()
        reviews = db.query(AgentReviewEvent).all()
        risk_events = db.query(RiskDecisionEvent).all()

    assert result["final_decision"] == "PAPER_EXECUTED"
    assert result["candidate_id"] == candidate_id_for_signal(payload.signal_id)
    assert candidate.status == "paper_opened"
    assert len(reviews) == 2
    assert len(risk_events) == 1
    assert broker.calls[0]["candidate_id"] == candidate_id_for_signal(payload.signal_id)
    assert broker.calls[0]["signal_id"] == payload.signal_id
    assert broker.calls[0]["strategy_id"] == "default"
    assert broker.calls[0]["opened_by_loop"] is True
    assert risk.trades_today == 1


@pytest.mark.asyncio
async def test_paper_training_pipeline_records_gem10_review_events(monkeypatch):
    async def fake_regime(_payload):
        return {"trade_allowed": True, "regime": "TEST", "reason": "ok"}

    Session = _session_factory()
    recorder = LifecycleRecorder(Session)
    broker = FakePaperBroker()
    risk = FakeRiskEngine(RiskDecisionEnum.PROCEED_TO_SIMULATION)
    pipeline = PaperTrainingPipeline(
        ai_review_layer=FakeGem10AIReviewLayer(),
        risk_engine=risk,
        paper_broker=broker,
        recorder=recorder,
    )
    monkeypatch.setattr(pipeline, "_check_regime", fake_regime)

    await pipeline.process_candidate(_payload("live-BTCUSDT-1m-default-1700000000030"))

    with Session() as db:
        reviews = db.query(AgentReviewEvent).all()

    assert len(reviews) == len(GEM_AGENT_NAMES)
    assert {row.scout_name for row in reviews} == set(GEM_AGENT_NAMES)


@pytest.mark.asyncio
async def test_paper_training_pipeline_records_risk_rejection_without_paper_order(monkeypatch):
    async def fake_regime(_payload):
        return {"trade_allowed": True, "regime": "TEST", "reason": "ok"}

    Session = _session_factory()
    recorder = LifecycleRecorder(Session)
    broker = FakePaperBroker()
    pipeline = PaperTrainingPipeline(
        ai_review_layer=FakeAIReviewLayer(),
        risk_engine=FakeRiskEngine(RiskDecisionEnum.REJECT, reason="LOW_CONFLUENCE"),
        paper_broker=broker,
        recorder=recorder,
    )
    monkeypatch.setattr(pipeline, "_check_regime", fake_regime)

    result = await pipeline.process_candidate(_payload("live-BTCUSDT-1m-default-1700000000060"))

    with Session() as db:
        candidate = db.query(SignalCandidate).one()
        risk_event = db.query(RiskDecisionEvent).one()

    assert result["final_decision"] == "RISK_REJECTED"
    assert result["reject_reason"] == "LOW_CONFLUENCE"
    assert candidate.status == "risk_rejected"
    assert risk_event.reason_code == "LOW_CONFLUENCE"
    assert broker.calls == []
