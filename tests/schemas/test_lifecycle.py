"""Tests for paper-training lifecycle schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.lifecycle import (
    AgentLearningRecord,
    AgentReviewRecord,
    PaperOutcomeRecord,
    SignalCandidateRecord,
)


def test_signal_candidate_record_accepts_live_paper_candidate():
    record = SignalCandidateRecord(
        candidate_id="cand-001",
        signal_id="sig-001",
        symbol="BTCUSDT",
        timeframe="1h",
        strategy_id="pattern_enhanced",
        direction="LONG",
        entry_price=100000.0,
        stop_price=99000.0,
        target_price=102000.0,
        confluence_score=80.0,
        features={"setup": "cisd"},
    )

    assert record.source == "live_paper"
    assert record.features["setup"] == "cisd"


def test_agent_review_confidence_is_bounded():
    with pytest.raises(ValidationError):
        AgentReviewRecord(
            candidate_id="cand-001",
            scout_name="risk",
            decision="REJECT",
            confidence=1.5,
        )


def test_paper_outcome_and_learning_records_capture_agent_ground_truth():
    outcome = PaperOutcomeRecord(
        candidate_id="cand-001",
        trade_id="paper-001",
        symbol="SOLUSD",
        direction="LONG",
        close_reason="STOP_LOSS",
        exit_price=95.0,
        pnl=-5.0,
        win=False,
    )
    learning = AgentLearningRecord(
        scout_name="risk",
        symbol="SOLUSD",
        direction="LONG",
        was_correct=True,
        candidate_id=outcome.candidate_id,
        trade_id=outcome.trade_id,
        context={"risk_scout_rejected": True},
    )

    assert outcome.outcome_source == "live_paper"
    assert learning.was_correct is True
    assert learning.context["risk_scout_rejected"] is True
