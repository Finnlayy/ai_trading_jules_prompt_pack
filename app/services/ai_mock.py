from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import SignalReview, DecisionEnum
from app.services.ai_layer_memory import ai_layer_memory_instance
from app.services.confidence_registry import confidence_registry


class MockAIReviewLayer:
    """
    Mock AI Review Layer that simulates a 4-scout swarm.
    In mock mode, scouts use deterministic heuristics instead of LLM calls.
    """

    SCOUT_NAMES = ["technical", "sentiment", "risk", "macro"]

    def review_signal(self, payload: M8Payload) -> SignalReview:
        # Simulate 4 scouts with deterministic heuristics
        scout_reports = {
            "technical": self._mock_technical(payload),
            "sentiment": self._mock_sentiment(payload),
            "risk": self._mock_risk(payload),
            "macro": self._mock_macro(payload),
        }

        # Mock orchestrator synthesis
        decision = DecisionEnum.PROCEED_TO_SIMULATION
        confidence = 0.85
        reason_codes = ["FAVORABLE_SETUP"]
        risk_flags = []
        requires_human_review = False
        reject_reason = None

        # Crisis override
        if payload.crisis_score > 20.0:
            decision = DecisionEnum.REJECT
            confidence = 0.95
            reason_codes = ["MACRO_RISK_HIGH"]
            risk_flags = ["CRISIS_ABOVE_20"]
            requires_human_review = True
            reject_reason = "High crisis environment detected"
        elif payload.crisis_score > 15.0:
            confidence = 0.55
            reason_codes = ["MACRO_RISK_ELEVATED"]
            requires_human_review = True
        elif payload.confluence_score < 75.0:
            confidence = 0.60
            reason_codes.append("WEAK_CONFLUENCE_WARNING")

        # Record in confidence registry (outcome = None for now)
        for scout_name, report in scout_reports.items():
            conf = self._extract_confidence(report)
            confidence_registry.record_scout_review(
                symbol=payload.symbol,
                scout_name=scout_name,
                direction=payload.direction,
                decision=decision.value,
                confidence=conf,
                was_correct=None,
            )

        confidence_registry.record_signal_review(
            symbol=payload.symbol,
            confluence=payload.confluence_score,
            crisis=payload.crisis_score,
            direction=payload.direction,
        )

        symbol_context = confidence_registry.get_symbol_context(
            payload.symbol, payload.direction
        )

        return SignalReview(
            schema_version="1.0",
            signal_id=payload.signal_id,
            decision=decision,
            confidence=confidence,
            reason_codes=reason_codes,
            risk_flags=risk_flags,
            reject_reason=reject_reason,
            requires_human_review=requires_human_review,
            audit_trace={
                "trace_type": "ai_reasoning_audit_not_hidden_chain_of_thought",
                "provider": "mock",
                "behavior_profile": ai_layer_memory_instance.get_profile().model_dump(),
                "scouts": scout_reports,
                "symbol_context": symbol_context,
                "scout_weights": {
                    name: confidence_registry.get_scout_weight(payload.symbol, name)
                    for name in self.SCOUT_NAMES
                },
                "final_summary": {
                    "decision": decision.value,
                    "confidence": confidence,
                    "reason_codes": reason_codes,
                    "risk_flags": risk_flags,
                    "requires_human_review": requires_human_review,
                },
            },
        )

    def _mock_technical(self, payload: M8Payload) -> str:
        conf = min(1.0, payload.confluence_score / 100 + 0.1)
        quality = "excellent" if payload.confluence_score >= 85 else "good" if payload.confluence_score >= 70 else "fair"
        return (
            f"Confidence: {conf:.2f}\n"
            f"Technical setup quality: {quality}. Confluence {payload.confluence_score}/100. "
            f"Spread {payload.spread}bps. No major structural concerns."
        )

    def _mock_sentiment(self, payload: M8Payload) -> str:
        conf = 0.7 if not payload.macro_event_risk else 0.4
        bias = "bullish" if payload.direction == "LONG" else "bearish"
        risk_note = "No macro event risk." if not payload.macro_event_risk else "Macro event risk flagged."
        return (
            f"Confidence: {conf:.2f}\n"
            f"Sentiment bias: {bias}. {risk_note} Crisis score {payload.crisis_score}."
        )

    def _mock_risk(self, payload: M8Payload) -> str:
        if payload.crisis_score > 20:
            conf, level = 0.9, "critical"
        elif payload.crisis_score > 15:
            conf, level = 0.6, "elevated"
        else:
            conf, level = 0.8, "moderate"
        lev_note = f"Leverage {payload.leverage}x." if payload.leverage else "No leverage."
        return (
            f"Confidence: {conf:.2f}\n"
            f"Risk level: {level}. {lev_note} Drawdown {payload.drawdown_pct}%. "
            f"Regime {payload.market_regime or 'unknown'}."
        )

    def _mock_macro(self, payload: M8Payload) -> str:
        conf = 0.75 if payload.market_regime in {"GREEN", "YELLOW"} else 0.5
        regime = payload.market_regime or "unknown"
        tailwind = "favorable" if payload.direction == "LONG" and regime == "GREEN" else "neutral"
        return (
            f"Confidence: {conf:.2f}\n"
            f"Macro regime: {regime}. Tailwind for {payload.direction}: {tailwind}. "
            f"No structural headwinds detected."
        )

    @staticmethod
    def _extract_confidence(report: str) -> float:
        try:
            for line in report.splitlines():
                if "confidence:" in line.lower():
                    parts = line.lower().split("confidence:")
                    if len(parts) > 1:
                        return max(0.0, min(1.0, float(parts[1].strip().split()[0])))
        except Exception:
            pass
        return 0.5
