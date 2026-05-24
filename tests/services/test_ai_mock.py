import pytest
from app.services.ai_mock import MockAIReviewLayer
from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import DecisionEnum

def create_valid_payload() -> M8Payload:
    return M8Payload(
        signal_id="sig-001",
        symbol="BTCUSD",
        timeframe="1h",
        direction="LONG",
        timestamp="2026-05-20T10:00:00Z",
        entry_price=50000.0,
        stop_price=48000.0,
        target_price=54000.0,
        confluence_score=85.0,
        crisis_score=10.0,
        mc_dispersion=2.0,
        spread=5.0
    )

def test_ai_review_proceed():
    layer = MockAIReviewLayer()
    payload = create_valid_payload()
    review = layer.review_signal(payload)

    assert review.decision == DecisionEnum.PROCEED_TO_SIMULATION
    assert "FAVORABLE_SETUP" in review.reason_codes
    assert review.requires_human_review is False
    assert review.audit_trace["provider"] == "mock"

def test_ai_review_weak_confluence_warning():
    layer = MockAIReviewLayer()
    payload = create_valid_payload()
    payload.confluence_score = 72.0
    review = layer.review_signal(payload)

    assert review.decision == DecisionEnum.PROCEED_TO_SIMULATION
    assert "WEAK_CONFLUENCE_WARNING" in review.reason_codes
    assert review.confidence == 0.60

def test_ai_review_reject_high_crisis():
    layer = MockAIReviewLayer()
    payload = create_valid_payload()
    payload.crisis_score = 25.0
    review = layer.review_signal(payload)

    assert review.decision == DecisionEnum.REJECT
    assert "MACRO_RISK_HIGH" in review.reason_codes
    assert review.requires_human_review is True
    assert review.reject_reason == "High crisis environment detected"
