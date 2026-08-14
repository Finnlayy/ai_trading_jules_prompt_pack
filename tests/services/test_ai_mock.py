import pytest
from app.services.ai_mock import MockAIReviewLayer
from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import DecisionEnum
from app.services.confidence_registry import confidence_registry


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
        spread=5.0,
        market_regime="GREEN",
    )


@pytest.fixture(autouse=True)
def reset_confidence_registry():
    confidence_registry.reset_all()
    yield
    confidence_registry.reset_all()


def test_ai_review_proceed():
    layer = MockAIReviewLayer()
    payload = create_valid_payload()
    review = layer.review_signal(payload)

    assert review.decision == DecisionEnum.PROCEED_TO_SIMULATION
    assert "FAVORABLE_SETUP" in review.reason_codes
    assert review.requires_human_review is False
    assert review.audit_trace["provider"] == "mock"
    # 4-scout swarm
    scouts = review.audit_trace["scouts"]
    assert set(scouts.keys()) == {"macro_sentinel", "market_dna", "structural_architect", "harmony_coordinator", "indicator_fusion", "risk_kernel", "pine_core", "payload_qa", "execution_watchdog", "evolution_optimizer"}
    assert "symbol_context" in review.audit_trace
    assert "scout_weights" in review.audit_trace
    assert "weighted_scout_vote" in review.audit_trace
    assert review.audit_trace["confidence_recorded"] is True
    assert review.audit_trace["weighted_scout_vote"]["decision_hint"] == DecisionEnum.PROCEED_TO_SIMULATION.value


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


def test_ai_review_updates_confidence_registry():
    layer = MockAIReviewLayer()
    payload = create_valid_payload()
    review = layer.review_signal(payload)

    stats = confidence_registry.get_symbol_stats("BTCUSD")
    assert stats.total_signals == 1
    # All 4 scouts should have been recorded
    for scout_name in layer.SCOUT_NAMES:
        assert scout_name in stats.scout_stats
        assert stats.scout_stats[scout_name].calls == 1


def test_ai_review_uses_weighted_scout_rejection():
    layer = MockAIReviewLayer()
    payload = create_valid_payload()
    payload.confluence_score = 60.0
    payload.market_regime = "RED"
    payload.macro_event_risk = True
    payload.spread = 80.0

    review = layer.review_signal(payload)

    assert review.decision == DecisionEnum.REJECT
    assert "WEIGHTED_SCOUT_REJECT" in review.reason_codes
    assert review.audit_trace["weighted_scout_vote"]["rejection_score"] > review.audit_trace["weighted_scout_vote"]["approval_score"]
