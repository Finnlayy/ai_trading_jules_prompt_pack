from app.core.config import AI_PROVIDER, AI_REVIEW_ENGINE

def get_ai_review_instance():
    if AI_PROVIDER in {"mock", "offline", "none"}:
        from app.services.ai_mock import MockAIReviewLayer
        return MockAIReviewLayer()

    if AI_REVIEW_ENGINE == "gem10_native":
        from app.services.ai.gem_native_review import GemNativeReviewService
        return GemNativeReviewService(provider=AI_PROVIDER)
    else:
        from app.services.ai_kimi import KimiSwarmService
        return KimiSwarmService(provider=AI_PROVIDER)

ai_review_instance = get_ai_review_instance()
