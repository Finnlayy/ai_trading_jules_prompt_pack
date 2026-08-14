"""Tests for the paper-training lifecycle persistence model."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.db.models import (
    AgentLearningEvent,
    AgentReviewEvent,
    PaperOutcome,
    PaperPosition,
    PaperTrade,
    RiskDecisionEvent,
    SignalCandidate,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    yield session
    session.close()


def test_lifecycle_tables_are_created(db_session):
    table_names = set(inspect(db_session.bind).get_table_names())

    assert "signal_candidates" in table_names
    assert "agent_review_events" in table_names
    assert "risk_decision_events" in table_names
    assert "paper_outcomes" in table_names
    assert "agent_learning_events" in table_names


def test_paper_trade_and_position_have_training_metadata(db_session):
    ai_trace = json.dumps({"scouts": {"risk": "reject"}})

    trade = PaperTrade(
        trade_id="paper-001",
        candidate_id="cand-001",
        signal_id="sig-001",
        symbol="SOLUSD",
        direction="LONG",
        strategy_id="pattern_enhanced",
        timeframe="1h",
        order_type="market",
        volume=0.1,
        entry_price=100.0,
        ai_trace_json=ai_trace,
        risk_decision="PROCEED_TO_SIMULATION",
        outcome_source="live_paper",
    )
    position = PaperPosition(
        candidate_id="cand-001",
        signal_id="sig-001",
        symbol="SOLUSD",
        direction="LONG",
        strategy_id="pattern_enhanced",
        timeframe="1h",
        volume=0.1,
        avg_entry_price=100.0,
        stop_loss=95.0,
        take_profit=110.0,
        ai_trace_json=ai_trace,
        risk_decision="PROCEED_TO_SIMULATION",
        opened_by_loop=True,
    )

    db_session.add_all([trade, position])
    db_session.commit()

    saved_trade = db_session.query(PaperTrade).filter_by(trade_id="paper-001").one()
    saved_position = db_session.query(PaperPosition).filter_by(signal_id="sig-001").one()

    assert saved_trade.strategy_id == "pattern_enhanced"
    assert saved_trade.ai_trace_json == ai_trace
    assert saved_position.opened_by_loop is True
    assert saved_position.take_profit == 110.0


def test_candidate_review_risk_outcome_and_learning_events(db_session):
    candidate = SignalCandidate(
        candidate_id="cand-002",
        signal_id="sig-002",
        symbol="BTCUSDT",
        timeframe="1h",
        strategy_id="default",
        bar_timestamp=datetime.now(timezone.utc),
        bar_ts_ms=1780000000000,
        direction="LONG",
        entry_price=100000.0,
        stop_price=99000.0,
        target_price=102000.0,
        confluence_score=72.0,
        features_json=json.dumps({"setup": "cisd"}),
    )
    review = AgentReviewEvent(
        candidate_id="cand-002",
        signal_id="sig-002",
        scout_name="technical",
        decision="PROCEED_TO_SIMULATION",
        confidence=0.81,
        provider="gemini",
        model="gemini-2.5-flash",
        reasons_json=json.dumps(["trend alignment"]),
    )
    risk = RiskDecisionEvent(
        candidate_id="cand-002",
        signal_id="sig-002",
        decision="PROCEED_TO_SIMULATION",
        reason_code=None,
        limits_snapshot_json=json.dumps({"max_daily_trades": 5}),
    )
    outcome = PaperOutcome(
        candidate_id="cand-002",
        trade_id="paper-002",
        signal_id="sig-002",
        symbol="BTCUSDT",
        direction="LONG",
        strategy_id="default",
        timeframe="1h",
        close_reason="TAKE_PROFIT",
        exit_price=102000.0,
        pnl=20.0,
        pnl_pct=2.0,
        r_multiple=2.0,
        win=True,
        outcome_source="live_paper",
    )
    learning = AgentLearningEvent(
        candidate_id="cand-002",
        trade_id="paper-002",
        signal_id="sig-002",
        scout_name="technical",
        symbol="BTCUSDT",
        direction="LONG",
        strategy_id="default",
        timeframe="1h",
        was_correct=True,
        context_json=json.dumps({"close_reason": "TAKE_PROFIT"}),
    )

    db_session.add_all([candidate, review, risk, outcome, learning])
    db_session.commit()

    assert db_session.query(SignalCandidate).count() == 1
    assert db_session.query(AgentReviewEvent).one().confidence == 0.81
    assert db_session.query(RiskDecisionEvent).one().decision == "PROCEED_TO_SIMULATION"
    assert db_session.query(PaperOutcome).one().win is True
    assert db_session.query(AgentLearningEvent).one().was_correct is True
