from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import SignalReview, DecisionEnum as AIDecisionEnum
from app.schemas.journal import DecisionEnum, FinalDecisionEnum
from app.core.config import (
    MIN_RR_RATIO, MAX_SPREAD, MIN_CONFLUENCE_SCORE, MAX_CRISIS_SCORE,
    MAX_MC_DISPERSION, COOLDOWN_BARS, MAX_TRADES_PER_DAY,
    NEWS_IMPACT_ENABLED,
)
from app.core.exceptions import RiskGateException
from app.services.war_room_rules import ai_rule_violation, classify_order
from app.services.portfolio_circuit_breaker import circuit_breaker_instance
from app.services.correlation_risk import correlation_checker
from typing import Optional, Dict, List

class RiskEngine:
    def __init__(self):
        # state for simulation tests
        self.trades_today = 0
        self.last_trade_bar = -1
        self.current_bar = 0
        self.open_positions: List[dict] = []  # for correlation risk checks

    def evaluate(self, payload: M8Payload, ai_review: Optional[SignalReview] = None) -> Dict:
        """
        Evaluates the payload and AI review against deterministic risk gates.
        Optionally applies news-based risk adjustments.
        Returns a dict with 'decision' and 'reject_reason' (if rejected).
        """
        # Load news-based adjustments
        adjustments = self._get_news_adjustments(payload.symbol)
        if adjustments.human_review_required:
            return {
                "decision": DecisionEnum.HUMAN_REVIEW,
                "reject_reason": "NEWS_IMPACT_MANDATES_HUMAN_REVIEW",
            }

        try:
            self._gate_invalid_payload(payload)
            if payload.intent == "CLOSE":
                return {
                    "decision": DecisionEnum.PROCEED_TO_SIMULATION,
                    "reject_reason": None,
                }
            self._gate_war_room_order(payload)
            self._gate_m8_score(payload, adjustments)
            self._gate_crisis_score(payload, adjustments)
            self._gate_dispersion(payload)
            self._gate_spread(payload, adjustments)
            self._gate_rr(payload)
            self._gate_cooldown(adjustments)
            self._gate_max_trades()
            self._gate_portfolio_drawdown()
            self._gate_correlation_risk(payload)
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

    def _gate_war_room_order(self, payload: M8Payload):
        war_room = classify_order(payload)
        if war_room.reject_reason:
            raise RiskGateException("War Room order gate blocked entry", war_room.reject_reason)
            
    def _get_news_adjustments(self, symbol: str):
        """Fetch news-based risk adjustments for the symbol."""
        from app.services.news_impact_scorer import news_impact_scorer, RiskAdjustments
        from app.services.news_aggregator import news_aggregator_instance

        if not NEWS_IMPACT_ENABLED:
            return RiskAdjustments()
        try:
            cached_news = news_aggregator_instance.get_cached()
            scored = news_impact_scorer.score_items(cached_news, symbol)
            summary = news_impact_scorer.aggregate_impact(scored)
            return summary.risk_adjustments
        except Exception:
            return RiskAdjustments()

    def _gate_m8_score(self, payload: M8Payload, adjustments=None):
        effective = MIN_CONFLUENCE_SCORE + (adjustments.confluence_offset if adjustments else 0.0)
        if payload.confluence_score < effective:
            raise RiskGateException(f"Confluence score below minimum ({effective})", "LOW_CONFLUENCE")

    def _gate_crisis_score(self, payload: M8Payload, adjustments=None):
        effective = MAX_CRISIS_SCORE + (adjustments.crisis_offset if adjustments else 0.0)
        if payload.crisis_score > effective:
            raise RiskGateException(f"Crisis score too high ({effective})", "HIGH_CRISIS")

    def _gate_dispersion(self, payload: M8Payload):
        if payload.mc_dispersion > MAX_MC_DISPERSION:
            raise RiskGateException("MC dispersion too high", "HIGH_DISPERSION")

    def _gate_spread(self, payload: M8Payload, adjustments=None):
        effective = MAX_SPREAD * (adjustments.spread_multiplier if adjustments else 1.0)
        if payload.spread > effective:
            raise RiskGateException(f"Spread exceeds maximum limit ({effective})", "WIDE_SPREAD")

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

    def _gate_cooldown(self, adjustments=None):
        effective = COOLDOWN_BARS + (adjustments.cooldown_bars_offset if adjustments else 0)
        if self.last_trade_bar != -1 and (self.current_bar - self.last_trade_bar) < effective:
            raise RiskGateException("Entry cooldown is active", "COOLDOWN_ACTIVE")

    def _gate_max_trades(self):
        if self.trades_today >= MAX_TRADES_PER_DAY:
            raise RiskGateException("Maximum trades per day reached", "MAX_TRADES_REACHED")

    def _gate_ai_conflict(self, payload: M8Payload, ai_review: SignalReview):
        war_room_ai_reason = ai_rule_violation(ai_review)
        if war_room_ai_reason:
            raise RiskGateException("AI review violated War Room rules", war_room_ai_reason)
        if ai_review.decision == AIDecisionEnum.REJECT:
            raise RiskGateException("AI review rejected the signal", "AI_REJECT")
        if ai_review.requires_human_review:
             raise RiskGateException("AI requires human review", "AI_HUMAN_REVIEW_REQUIRED")

    def _gate_portfolio_drawdown(self):
        cb = circuit_breaker_instance.check_trade_allowed()
        if not cb["trade_allowed"]:
            raise RiskGateException(
                f"Portfolio circuit breaker active: {cb['reason']}",
                "PORTFOLIO_DRAWDOWN_HALT"
            )

    def _gate_correlation_risk(self, payload: M8Payload):
        result = correlation_checker.check_new_entry(payload.symbol, self.open_positions)
        if not result["allowed"]:
            raise RiskGateException(result["reason"], "CORRELATION_RISK_LIMIT")


# Global instance for FastAPI usage
risk_engine_instance = RiskEngine()
