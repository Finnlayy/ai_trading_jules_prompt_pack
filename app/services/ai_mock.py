from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import SignalReview, DecisionEnum
from app.services.ai_layer_memory import ai_layer_memory_instance

class MockAIReviewLayer:
    """
    Mock AI Review Layer for the MVP.
    In a real scenario, this would format a prompt, call the LLM API,
    and parse the resulting JSON into the SignalReview schema.
    """
    def review_signal(self, payload: M8Payload) -> SignalReview:
        # Simplistic logic to simulate an AI decision
        # If confluence is very high, strongly approve. If low-ish but passable, add a warning.

        decision = DecisionEnum.PROCEED_TO_SIMULATION
        confidence = 0.85
        reason_codes = ["FAVORABLE_SETUP"]
        requires_human_review = False

        if payload.confluence_score < 75.0:
            confidence = 0.60
            reason_codes.append("WEAK_CONFLUENCE_WARNING")

        if 15.0 < payload.crisis_score <= 20.0:
            # Elevated risk: don't auto-reject, but flag for human review
            decision = DecisionEnum.PROCEED_TO_SIMULATION
            confidence = 0.55
            reason_codes = ["MACRO_RISK_ELEVATED"]
            requires_human_review = True

        if payload.crisis_score > 20.0:
            decision = DecisionEnum.REJECT
            confidence = 0.95
            reason_codes = ["MACRO_RISK_HIGH"]
            requires_human_review = True

        return SignalReview(
            schema_version="1.0",
            signal_id=payload.signal_id,
            decision=decision,
            confidence=confidence,
            reason_codes=reason_codes,
            risk_flags=[],
            reject_reason="High crisis environment detected" if decision == DecisionEnum.REJECT else None,
            requires_human_review=requires_human_review,
            audit_trace={
                "trace_type": "ai_reasoning_audit_not_hidden_chain_of_thought",
                "provider": "mock",
                "behavior_profile": ai_layer_memory_instance.get_profile().model_dump(),
                "final_summary": {
                    "decision": decision.value,
                    "confidence": confidence,
                    "reason_codes": reason_codes,
                    "risk_flags": [],
                    "requires_human_review": requires_human_review,
                },
            },
        )

ai_review_instance = MockAIReviewLayer()
