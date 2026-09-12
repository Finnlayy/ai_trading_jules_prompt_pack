import pytest
from datetime import datetime, timezone
from pydantic import ValidationError
from app.schemas.ai_layer import (
    utc_now,
    AIBehaviorProfile,
    AIChatMessage,
    AIChatRequest,
    AIChatResponse
)

def test_utc_now():
    now_str = utc_now()
    assert isinstance(now_str, str)

    parsed = datetime.fromisoformat(now_str)

    assert parsed.tzinfo is not None
    assert parsed.tzinfo == timezone.utc

    now = datetime.now(timezone.utc)
    diff = abs((now - parsed).total_seconds())
    assert diff < 1.0

def test_ai_behavior_profile_defaults():
    profile = AIBehaviorProfile()
    assert profile.trading_style == "balanced"
    assert profile.risk_tolerance == "moderate"
    assert profile.preferred_symbols == []
    assert profile.blocked_symbols == []
    assert profile.max_risk_pct is None
    assert profile.min_confluence_preference is None
    assert profile.notes == ""
    assert len(profile.guardrails) == 3
    assert "Do not request live execution directly." in profile.guardrails
    assert isinstance(profile.updated_at, str)
    parsed = datetime.fromisoformat(profile.updated_at)
    assert parsed.tzinfo == timezone.utc

def test_ai_behavior_profile_validation():
    # Valid
    profile = AIBehaviorProfile(
        trading_style="aggressive",
        max_risk_pct=5.5,
        min_confluence_preference=80.0
    )
    assert profile.max_risk_pct == 5.5
    assert profile.min_confluence_preference == 80.0

    # Invalid max_risk_pct (must be > 0.0)
    with pytest.raises(ValidationError):
        AIBehaviorProfile(max_risk_pct=0.0)

    with pytest.raises(ValidationError):
        AIBehaviorProfile(max_risk_pct=-1.0)

    # Invalid min_confluence_preference (0.0 <= x <= 100.0)
    with pytest.raises(ValidationError):
        AIBehaviorProfile(min_confluence_preference=-0.1)

    with pytest.raises(ValidationError):
        AIBehaviorProfile(min_confluence_preference=100.1)

def test_ai_chat_message():
    # Valid
    msg = AIChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
    assert isinstance(msg.timestamp, str)
    parsed = datetime.fromisoformat(msg.timestamp)
    assert parsed.tzinfo == timezone.utc

    # Invalid role
    with pytest.raises(ValidationError):
        AIChatMessage(role="invalid_role", content="Hello")

def test_ai_chat_request_defaults():
    req = AIChatRequest(message="Test message")
    assert req.message == "Test message"
    assert req.apply_to_profile is True
    assert req.chart_context is None
    assert req.bars_count == 50
    assert req.strategy_context is None
    assert req.return_prompt_only is False

def test_ai_chat_request_validation():
    # Message length limits
    with pytest.raises(ValidationError):
        AIChatRequest(message="") # min 1

    with pytest.raises(ValidationError):
        AIChatRequest(message="A" * 100001) # max 100000 (raised in #158 payload crash fix)

    # Bars count bounds (10 <= x <= 300)
    with pytest.raises(ValidationError):
        AIChatRequest(message="Test", bars_count=9)

    with pytest.raises(ValidationError):
        AIChatRequest(message="Test", bars_count=301)

    # Valid custom bars_count
    req = AIChatRequest(message="Test", bars_count=150)
    assert req.bars_count == 150

def test_ai_chat_response():
    profile = AIBehaviorProfile()
    mem = [AIChatMessage(role="user", content="Hello")]

    res = AIChatResponse(
        reply="Hi",
        provider="openai",
        used_llm=True,
        profile=profile,
        memory=mem
    )

    assert res.reply == "Hi"
    assert res.provider == "openai"
    assert res.used_llm is True
    assert res.profile == profile
    assert res.memory == mem
    assert res.raw_profile_patch == {}
    assert res.recommended_action is None
    assert res.generated_prompt is None
    assert res.system_prompt is None
