"""Closed-loop paper-training pipeline for autonomous candidates."""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from typing import Any

from app.schemas.ai_review import SignalReview
from app.schemas.journal import DecisionEnum
from app.schemas.m8_payload import M8Payload
from app.services.ai_factory import ai_review_instance
from app.services.kraken_paper_broker import KrakenPaperBroker
from app.services.lifecycle_recorder import (
    _json_dumps,
    candidate_id_for_signal,
    lifecycle_recorder,
    LifecycleRecorder,
)
from app.services.regime_engine import regime_engine_instance
from app.services.risk_engine import risk_engine_instance
from app.services.signal_generator import BybitDataFeed


DEFAULT_PAPER_NOTIONAL_USD = 10.0


class PaperTrainingPipeline:
    """Runs Candidate -> AI Scouts -> Risk Engine -> local Paper Trading."""

    def __init__(
        self,
        *,
        ai_review_layer: Any = None,
        risk_engine: Any = None,
        paper_broker: Any = None,
        recorder: LifecycleRecorder | None = None,
    ) -> None:
        self.ai_review_layer = ai_review_layer or ai_review_instance
        self.risk_engine = risk_engine or risk_engine_instance
        self.paper_broker = paper_broker or KrakenPaperBroker()
        self.recorder = recorder or lifecycle_recorder

    async def process_candidate(self, payload: M8Payload) -> dict[str, Any]:
        candidate_id = candidate_id_for_signal(payload.signal_id)
        self.recorder.record_candidate(payload, candidate_id=candidate_id)

        regime_result = await self._check_regime(payload)
        ai_review = await self._review_signal(payload)
        if ai_review.audit_trace is not None:
            ai_review.audit_trace["regime"] = regime_result
        self.recorder.record_ai_review(
            candidate_id=candidate_id,
            payload=payload,
            ai_review=ai_review,
        )

        decision_result = self.risk_engine.evaluate(payload, ai_review)
        if payload.intent != "CLOSE" and not regime_result.get("trade_allowed", True):
            decision_result = {
                "decision": DecisionEnum.REJECT,
                "reject_reason": f"REGIME_HALT: {regime_result.get('reason', 'Market regime unsuitable')}",
            }

        self.recorder.record_risk_decision(
            candidate_id=candidate_id,
            payload=payload,
            decision_result=decision_result,
            limits_snapshot=self._limits_snapshot(payload, regime_result, ai_review),
        )

        if self._decision_value(decision_result) != DecisionEnum.PROCEED_TO_SIMULATION.value:
            self.recorder.update_candidate_status(candidate_id, "risk_rejected")
            return self._result(
                payload=payload,
                candidate_id=candidate_id,
                ai_review=ai_review,
                decision_result=decision_result,
                regime_result=regime_result,
                final_decision="RISK_REJECTED",
                paper_result=None,
            )

        paper_result = await self._execute_paper_order(
            payload=payload,
            candidate_id=candidate_id,
            decision_result=decision_result,
            ai_review=ai_review,
        )
        if paper_result.get("status") == "ok":
            self.recorder.update_candidate_status(candidate_id, "paper_opened")
            self._update_risk_engine_after_paper_fill()
            final_decision = "PAPER_EXECUTED"
        else:
            self.recorder.update_candidate_status(candidate_id, "paper_rejected")
            final_decision = "PAPER_REJECTED"

        return self._result(
            payload=payload,
            candidate_id=candidate_id,
            ai_review=ai_review,
            decision_result=decision_result,
            regime_result=regime_result,
            final_decision=final_decision,
            paper_result=paper_result,
        )

    async def _review_signal(self, payload: M8Payload) -> SignalReview:
        review_result = self.ai_review_layer.review_signal(payload)
        return await review_result if inspect.isawaitable(review_result) else review_result

    async def _execute_paper_order(
        self,
        *,
        payload: M8Payload,
        candidate_id: str,
        decision_result: dict[str, Any],
        ai_review: SignalReview,
    ) -> dict[str, Any]:
        risk_reason = decision_result.get("reject_reason")
        return await asyncio.to_thread(
            self.paper_broker.place_paper_order,
            symbol=payload.symbol,
            direction=payload.direction,
            volume=self._volume_from_payload(payload),
            order_type="market",
            stop_loss=payload.stop_price,
            take_profit=payload.target_price,
            candidate_id=candidate_id,
            signal_id=payload.signal_id,
            strategy_id=payload.strategy_id,
            timeframe=payload.timeframe,
            ai_trace_json=_json_dumps(ai_review.audit_trace or {}),
            risk_decision=self._decision_value(decision_result),
            risk_reason=str(risk_reason) if risk_reason else None,
            opened_by_loop=True,
            outcome_source="live_paper",
        )

    async def _check_regime(self, payload: M8Payload) -> dict[str, Any]:
        try:
            bars = await asyncio.to_thread(
                BybitDataFeed.fetch,
                payload.symbol,
                bars=50,
                timeframe=payload.timeframe,
            )
            if not bars or len(bars) < 30:
                return {
                    "trade_allowed": True,
                    "regime": "UNKNOWN",
                    "reason": "Insufficient bars for regime check",
                }
            closes = [bar.c for bar in bars]
            return regime_engine_instance.should_trade(closes)
        except Exception as exc:
            return {
                "trade_allowed": True,
                "regime": "UNKNOWN",
                "reason": f"Regime check failed: {exc}",
            }

    @staticmethod
    def _volume_from_payload(payload: M8Payload) -> float:
        if payload.execution_quantity:
            return float(payload.execution_quantity)
        if payload.entry_price <= 0:
            return 0.0
        return round(DEFAULT_PAPER_NOTIONAL_USD / payload.entry_price, 8)

    @staticmethod
    def _decision_value(decision_result: dict[str, Any]) -> str:
        decision = decision_result.get("decision")
        return decision.value if hasattr(decision, "value") else str(decision)

    @staticmethod
    def _limits_snapshot(
        payload: M8Payload,
        regime_result: dict[str, Any],
        ai_review: SignalReview,
    ) -> dict[str, Any]:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": payload.symbol,
            "timeframe": payload.timeframe,
            "confluence_score": payload.confluence_score,
            "crisis_score": payload.crisis_score,
            "spread": payload.spread,
            "mc_dispersion": payload.mc_dispersion,
            "ai_decision": ai_review.decision.value,
            "ai_confidence": ai_review.confidence,
            "regime": regime_result,
        }

    def _update_risk_engine_after_paper_fill(self) -> None:
        self.risk_engine.last_trade_bar = self.risk_engine.current_bar
        self.risk_engine.trades_today += 1

    @staticmethod
    def _result(
        *,
        payload: M8Payload,
        candidate_id: str,
        ai_review: SignalReview,
        decision_result: dict[str, Any],
        regime_result: dict[str, Any],
        final_decision: str,
        paper_result: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "pipeline": "paper_training",
            "candidate_id": candidate_id,
            "signal_id": payload.signal_id,
            "final_decision": final_decision,
            "ai_decision": ai_review.decision.value,
            "ai_confidence": ai_review.confidence,
            "ai_trace": ai_review.audit_trace,
            "risk_decision": PaperTrainingPipeline._decision_value(decision_result),
            "reject_reason": decision_result.get("reject_reason"),
            "regime": regime_result,
            "paper_result": paper_result,
            "execution_mode": "paper",
        }


paper_training_pipeline = PaperTrainingPipeline()
