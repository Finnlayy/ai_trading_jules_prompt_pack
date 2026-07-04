import pytest
from app.services.risk_engine import RiskEngine
from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import SignalReview, DecisionEnum as AIDecisionEnum
from app.schemas.journal import DecisionEnum
from app.services.confidence_registry import confidence_registry
from app.core.exceptions import RiskGateException

@pytest.fixture
def risk_engine():
    return RiskEngine()

@pytest.fixture
def valid_payload():
    return M8Payload(
        signal_id="sig_test_1",
        symbol="BTCUSDT",
        timeframe="15m",
        direction="LONG",
        timestamp="2023-01-01T00:00:00Z",
        entry_price=50000.0,
        stop_price=49000.0,
        target_price=52000.0,
        confluence_score=85.0,
        crisis_score=10.0,
        mc_dispersion=1.0,
        spread=5.0,
    )

@pytest.fixture
def mock_ai_review():
    return SignalReview(
        schema_version="1.0",
        signal_id="sig_test_1",
        decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
        confidence=0.85,
        reason_codes=[],
        risk_flags=[],
        requires_human_review=False,
        audit_trace={
            "weighted_scout_vote": 0.8,
            "symbol_context": "Good history"
        }
    )

def test_risk_engine_accepts_good_candidate(risk_engine, valid_payload, mock_ai_review, monkeypatch):
    # Mock correlation to allow trade
    class MockCorrelationChecker:
        def check_new_entry(self, symbol, positions):
            return {"allowed": True, "reason": None}
    monkeypatch.setattr("app.services.risk_engine.correlation_checker", MockCorrelationChecker())

    # Mock war room to allow trade
    class MockWarRoom:
        reject_reason = None
    monkeypatch.setattr("app.services.risk_engine.classify_order", lambda p: MockWarRoom())

    # Mock confidence registry to return good history
    class MockStats:
        class MockDirectionStats:
            total = 10
            win_rate = 0.6
        def get_direction_stats(self, direction):
            return self.MockDirectionStats()
    monkeypatch.setattr("app.services.confidence_registry.ConfidenceRegistry.get_symbol_stats", lambda self, sym: MockStats())

    result = risk_engine.evaluate(valid_payload, mock_ai_review)

    assert result["decision"] == DecisionEnum.PROCEED_TO_SIMULATION
    assert result["reject_reason"] is None
    assert result["weighted_scout_vote"] == 0.8
    assert result["confidence_context"] == "Good history"

def test_risk_engine_blocks_hard_kill_despite_ai(risk_engine, valid_payload, mock_ai_review, monkeypatch):
    valid_payload.crisis_score = 99.0 # Trigger HIGH_CRISIS

    # Mock correlation to allow trade
    class MockCorrelationChecker:
        def check_new_entry(self, symbol, positions):
            return {"allowed": True, "reason": None}
    monkeypatch.setattr("app.services.risk_engine.correlation_checker", MockCorrelationChecker())

    # Mock war room to allow trade
    class MockWarRoom:
        reject_reason = None
    monkeypatch.setattr("app.services.risk_engine.classify_order", lambda p: MockWarRoom())

    result = risk_engine.evaluate(valid_payload, mock_ai_review)
    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "HIGH_CRISIS"
    assert result["weighted_scout_vote"] == 0.8 # should still preserve it if evaluated

def test_risk_engine_blocks_weak_scout_vote(risk_engine, valid_payload, mock_ai_review, monkeypatch):
    mock_ai_review.audit_trace["weighted_scout_vote"] = 0.3 # below 0.5 threshold

    # Mock correlation to allow trade
    class MockCorrelationChecker:
        def check_new_entry(self, symbol, positions):
            return {"allowed": True, "reason": None}
    monkeypatch.setattr("app.services.risk_engine.correlation_checker", MockCorrelationChecker())

    # Mock war room to allow trade
    class MockWarRoom:
        reject_reason = None
    monkeypatch.setattr("app.services.risk_engine.classify_order", lambda p: MockWarRoom())

    result = risk_engine.evaluate(valid_payload, mock_ai_review)
    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "WEAK_SCOUT_VOTE"

def test_risk_engine_blocks_poor_history(risk_engine, valid_payload, mock_ai_review, monkeypatch):
    # Mock correlation to allow trade
    class MockCorrelationChecker:
        def check_new_entry(self, symbol, positions):
            return {"allowed": True, "reason": None}
    monkeypatch.setattr("app.services.risk_engine.correlation_checker", MockCorrelationChecker())

    # Mock war room to allow trade
    class MockWarRoom:
        reject_reason = None
    monkeypatch.setattr("app.services.risk_engine.classify_order", lambda p: MockWarRoom())

    # Mock confidence registry to return POOR history
    class MockStats:
        class MockDirectionStats:
            total = 6
            win_rate = 0.1 # < 0.3
        def get_direction_stats(self, direction):
            return self.MockDirectionStats()

    monkeypatch.setattr("app.services.confidence_registry.ConfidenceRegistry.get_symbol_stats", lambda self, sym: MockStats())

    result = risk_engine.evaluate(valid_payload, mock_ai_review)
    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "POOR_HISTORY"
