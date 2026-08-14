import pytest
from app.services.ai_factory import ai_review_instance, get_ai_review_instance
from app.services.ai_mock import MockAIReviewLayer
from app.services.ai.gem_native_review import GemNativeReviewService

def test_ai_factory_mock():
    # Test provider="mock"
    instance = get_ai_review_instance("mock", "legacy")
    assert isinstance(instance, MockAIReviewLayer)

    # Test provider="offline"
    instance = get_ai_review_instance("offline", "legacy")
    assert isinstance(instance, MockAIReviewLayer)

def test_ai_factory_gem10_native():
    instance = get_ai_review_instance("gemini", "gem10_native")
    assert isinstance(instance, GemNativeReviewService)

def test_ai_factory_legacy():
    # Default behavior for non-mock, non-gem10
    instance = get_ai_review_instance("moonshot", "legacy")
    assert not isinstance(instance, MockAIReviewLayer)
    assert not isinstance(instance, GemNativeReviewService)
