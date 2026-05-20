import pytest
from app.schemas.ai_review import SignalReview, DecisionEnum
from pydantic import ValidationError

def test_valid_ai_review():
    review_data = {
        "schema_version": "1.0",
        "signal_id": "sig-123",
        "decision": "PROCEED_TO_SIMULATION",
        "confidence": 0.9,
        "reason_codes": ["BULLISH_MACRO", "SUPPORT_HELD"],
        "risk_flags": [],
        "requires_human_review": False
    }
    review = SignalReview(**review_data)
    assert review.decision == DecisionEnum.PROCEED_TO_SIMULATION
    assert review.confidence == 0.9

def test_invalid_confidence():
    review_data = {
        "schema_version": "1.0",
        "signal_id": "sig-123",
        "decision": "PROCEED_TO_SIMULATION",
        "confidence": 1.5, # Out of bounds
        "reason_codes": [],
        "risk_flags": [],
        "requires_human_review": False
    }
    with pytest.raises(ValidationError):
        SignalReview(**review_data)

def test_invalid_decision():
    review_data = {
        "schema_version": "1.0",
        "signal_id": "sig-123",
        "decision": "INVALID_DECISION",
        "confidence": 0.9,
        "reason_codes": [],
        "risk_flags": [],
        "requires_human_review": False
    }
    with pytest.raises(ValidationError):
        SignalReview(**review_data)
