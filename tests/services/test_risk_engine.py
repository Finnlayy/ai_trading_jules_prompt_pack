import pytest
from app.services.risk_engine import RiskEngine
from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import SignalReview
from app.schemas.journal import DecisionEnum
from app.core.config import MIN_RR_RATIO

def create_valid_payload() -> M8Payload:
    return M8Payload(
        signal_id="sig-001",
        symbol="BTCUSD",
        timeframe="1h",
        direction="LONG",
        timestamp="2026-05-20T10:00:00Z",
        entry_price=50000.0,
        stop_price=48000.0,
        target_price=54000.0, # risk = 2000, reward = 4000, rr = 2.0 (meets MIN_RR_RATIO)
        confluence_score=85.0,
        crisis_score=10.0,
        mc_dispersion=2.0,
        spread=5.0
    )

def test_risk_engine_proceeds():
    engine = RiskEngine()
    payload = create_valid_payload()
    result = engine.evaluate(payload)
    assert result["decision"] == DecisionEnum.PROCEED_TO_SIMULATION
    assert result["reject_reason"] is None

def test_risk_engine_m8_explicit_reject():
    engine = RiskEngine()
    payload = create_valid_payload()
    payload.m8_reject_reason = "SOME_M8_REASON"
    result = engine.evaluate(payload)
    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "M8_EXPLICIT_REJECT"

def test_risk_engine_low_rr():
    engine = RiskEngine()
    payload = create_valid_payload()
    payload.target_price = 51000.0 # risk = 2000, reward = 1000, rr = 0.5
    result = engine.evaluate(payload)
    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "LOW_RR"

def test_risk_engine_wide_spread():
    engine = RiskEngine()
    payload = create_valid_payload()
    payload.spread = 20.0 # Exceeds MAX_SPREAD (15.0)
    result = engine.evaluate(payload)
    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "WIDE_SPREAD"

def test_risk_engine_low_confluence():
    engine = RiskEngine()
    payload = create_valid_payload()
    payload.confluence_score = 50.0 # Below MIN_CONFLUENCE_SCORE (70.0)
    result = engine.evaluate(payload)
    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "LOW_CONFLUENCE"

def test_risk_engine_high_crisis():
    engine = RiskEngine()
    payload = create_valid_payload()
    payload.crisis_score = 40.0 # Above MAX_CRISIS_SCORE (30.0)
    result = engine.evaluate(payload)
    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "HIGH_CRISIS"

def test_risk_engine_high_dispersion():
    engine = RiskEngine()
    payload = create_valid_payload()
    payload.mc_dispersion = 10.0 # Above MAX_MC_DISPERSION (5.0)
    result = engine.evaluate(payload)
    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "HIGH_DISPERSION"

def test_risk_engine_cooldown():
    engine = RiskEngine()
    payload = create_valid_payload()
    engine.last_trade_bar = 0
    engine.current_bar = 1 # Cooldown active (COOLDOWN_BARS = 3)
    result = engine.evaluate(payload)
    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "COOLDOWN_ACTIVE"

def test_risk_engine_max_trades():
    engine = RiskEngine()
    payload = create_valid_payload()
    engine.trades_today = 5 # MAX_TRADES_PER_DAY = 5
    result = engine.evaluate(payload)
    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "MAX_TRADES_REACHED"

def test_risk_engine_ai_conflict():
    engine = RiskEngine()
    payload = create_valid_payload()
    ai_review = SignalReview(
        schema_version="1.0",
        signal_id=payload.signal_id,
        decision="REJECT",
        confidence=0.9,
        reason_codes=["AI_SAID_SO"],
        risk_flags=[],
        requires_human_review=False
    )
    result = engine.evaluate(payload, ai_review)
    assert result["decision"] == DecisionEnum.REJECT
    assert result["reject_reason"] == "AI_REJECT"
