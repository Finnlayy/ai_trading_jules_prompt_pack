from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import SignalReview, DecisionEnum as AIDecisionEnum
from app.schemas.journal import DecisionEnum, FinalDecisionEnum
from app.core.config import MIN_RR_RATIO, MAX_SPREAD, MIN_CONFLUENCE_SCORE, MAX_CRISIS_SCORE, MAX_MC_DISPERSION, COOLDOWN_BARS, MAX_TRADES_PER_DAY
from app.core.exceptions import RiskGateException
from typing import Optional, Dict

class RiskEngine:
    def __init__(self):
        # state for simulation tests
        self.trades_today = 0
        self.last_trade_bar = -1
        self.current_bar = 0

    def evaluate(self, payload: M8Payload, ai_review: Optional[SignalReview] = None) -> Dict:
        """
        Evaluates the payload and AI review against deterministic risk gates.
        Returns a dict with 'decision' and 'reject_reason' (if rejected).
        """
        try:
            self._gate_invalid_payload(payload)
            if payload.intent == "CLOSE":
                return {
                    "decision": DecisionEnum.PROCEED_TO_SIMULATION,
                    "reject_reason": None,
                }
            self._gate_m8_score(payload)
            self._gate_crisis_score(payload)
            self._gate_dispersion(payload)
            self._gate_spread(payload)
            self._gate_rr(payload)
            self._gate_cooldown()
            self._gate_max_trades()
            if ai_review:
                self._gate_ai_conflict(payload, ai_review)

            return {
                "decision": DecisionEnum.PROCEED_TO_SIMULATION,
                "reject_reason": None
            }
        except RiskGateException as e:
            return {
                "decision": DecisionEnum.REJECT,
                "reject_reason": e.reason_code
            }

    def _gate_invalid_payload(self, payload: M8Payload):
        if payload.m8_reject_reason:
            raise RiskGateException(f"M8 explicitly rejected: {payload.m8_reject_reason}", "M8_EXPLICIT_REJECT")
            
    def _gate_m8_score(self, payload: M8Payload):
        if payload.confluence_score < MIN_CONFLUENCE_SCORE:
            raise RiskGateException("Confluence score below minimum", "LOW_CONFLUENCE")
            
    def _gate_crisis_score(self, payload: M8Payload):
        if payload.crisis_score > MAX_CRISIS_SCORE:
            raise RiskGateException("Crisis score too high", "HIGH_CRISIS")

    def _gate_dispersion(self, payload: M8Payload):
        if payload.mc_dispersion > MAX_MC_DISPERSION:
            raise RiskGateException("MC dispersion too high", "HIGH_DISPERSION")

    def _gate_spread(self, payload: M8Payload):
        if payload.spread > MAX_SPREAD:
            raise RiskGateException("Spread exceeds maximum limit", "WIDE_SPREAD")

    def _gate_rr(self, payload: M8Payload):
        if payload.direction == "LONG":
            risk = payload.entry_price - payload.stop_price
            reward = payload.target_price - payload.entry_price
        else:
            risk = payload.stop_price - payload.entry_price
            reward = payload.entry_price - payload.target_price

        if risk <= 0:
            raise RiskGateException("Invalid risk (stop loss above entry for LONG or below entry for SHORT)", "INVALID_RISK")
            
        rr = reward / risk
        if rr < MIN_RR_RATIO:
            raise RiskGateException("Reward/Risk ratio too low", "LOW_RR")

    def _gate_cooldown(self):
        if self.last_trade_bar != -1 and (self.current_bar - self.last_trade_bar) < COOLDOWN_BARS:
            raise RiskGateException("Entry cooldown is active", "COOLDOWN_ACTIVE")

    def _gate_max_trades(self):
        if self.trades_today >= MAX_TRADES_PER_DAY:
            raise RiskGateException("Maximum trades per day reached", "MAX_TRADES_REACHED")

    def _gate_ai_conflict(self, payload: M8Payload, ai_review: SignalReview):
        if ai_review.decision == AIDecisionEnum.REJECT:
            raise RiskGateException("AI review rejected the signal", "AI_REJECT")
        if ai_review.requires_human_review:
             raise RiskGateException("AI requires human review", "AI_HUMAN_REVIEW_REQUIRED")


# Global instance for FastAPI usage
risk_engine_instance = RiskEngine()
