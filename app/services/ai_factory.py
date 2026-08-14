from __future__ import annotations

from app.core.config import AI_PROVIDER, AI_REVIEW_ENGINE


def get_ai_review_instance(provider: str | None = None, engine: str | None = None):
    selected_provider = (provider or AI_PROVIDER or "moonshot").strip().lower()
    selected_engine = (engine or AI_REVIEW_ENGINE or "legacy6").strip().lower()

    if selected_provider in {"mock", "offline", "none"}:
        from app.services.ai_mock import MockAIReviewLayer

        return MockAIReviewLayer()

    if selected_engine == "gem10_native":
        from app.services.ai.gem_native_review import GemNativeReviewService

        return GemNativeReviewService(provider=selected_provider)

    from app.services.ai_kimi import ai_review_instance as legacy_ai_review_instance

    return legacy_ai_review_instance


ai_review_instance = get_ai_review_instance()
