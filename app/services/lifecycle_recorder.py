"""Persistence helpers for the paper-training lifecycle audit trail."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.db.models import (
    AgentLearningEvent,
    AgentReviewEvent,
    PaperOutcome,
    RiskDecisionEvent,
    SignalCandidate,
)
from app.schemas.ai_review import SignalReview
from app.schemas.m8_payload import M8Payload


def _json_default(value: Any) -> str:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=True, sort_keys=True)


def _enum_value(value: Any) -> str:
    return value.value if isinstance(value, Enum) else str(value)


def candidate_id_for_signal(signal_id: str) -> str:
    """Derive a stable lifecycle candidate id from a signal id."""
    return f"cand-{signal_id}"


class LifecycleRecorder:
    """Records candidate, AI-review, and risk-decision lifecycle events."""

    def __init__(
        self,
        session_factory: Callable[[], Session] = SessionLocal,
        confidence_registry: Any | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._confidence_registry = confidence_registry

    def record_candidate(
        self,
        payload: M8Payload,
        *,
        source: str = "live_paper",
        features: dict[str, Any] | None = None,
        candidate_id: str | None = None,
    ) -> str:
        candidate_id = candidate_id or candidate_id_for_signal(payload.signal_id)
        bar_timestamp = self._parse_timestamp(payload.timestamp)
        features_payload = features or self._payload_features(payload)

        with self._session_factory() as db:
            existing = (
                db.query(SignalCandidate)
                .filter(SignalCandidate.candidate_id == candidate_id)
                .first()
            )
            if existing:
                return existing.candidate_id

            candidate = SignalCandidate(
                candidate_id=candidate_id,
                signal_id=payload.signal_id,
                symbol=payload.symbol.upper(),
                timeframe=payload.timeframe,
                strategy_id=payload.strategy_id or "unknown",
                bar_timestamp=bar_timestamp,
                bar_ts_ms=int(bar_timestamp.timestamp() * 1000) if bar_timestamp else None,
                direction=payload.direction,
                entry_price=payload.entry_price,
                stop_price=payload.stop_price,
                target_price=payload.target_price,
                confluence_score=payload.confluence_score,
                status="created",
                features_json=_json_dumps(features_payload),
                source=source,
            )
            db.add(candidate)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
            return candidate_id

    def record_ai_review(
        self,
        *,
        candidate_id: str,
        payload: M8Payload,
        ai_review: SignalReview,
    ) -> int:
        trace = ai_review.audit_trace or {}
        provider = str(trace.get("provider") or trace.get("original_provider") or "")
        scouts = trace.get("scouts") or {}

        events: list[AgentReviewEvent] = []
        if isinstance(scouts, dict) and scouts:
            for scout_name, scout_report in scouts.items():
                events.append(
                    AgentReviewEvent(
                        candidate_id=candidate_id,
                        signal_id=payload.signal_id,
                        scout_name=str(scout_name),
                        decision=self._scout_decision(scout_report, ai_review),
                        confidence=self._scout_confidence(scout_report, ai_review),
                        provider=provider or None,
                        model=self._scout_model(trace, str(scout_name)),
                        reasons_json=_json_dumps(self._scout_reasons(scout_report, ai_review)),
                        raw_report=self._scout_raw_report(scout_report),
                    )
                )
        else:
            events.append(
                AgentReviewEvent(
                    candidate_id=candidate_id,
                    signal_id=payload.signal_id,
                    scout_name="orchestrator",
                    decision=_enum_value(ai_review.decision),
                    confidence=ai_review.confidence,
                    provider=provider or None,
                    reasons_json=_json_dumps(ai_review.reason_codes),
                    raw_report=ai_review.explanation or _json_dumps(trace),
                )
            )

        confidence_snapshots = [
            {
                "scout_name": event.scout_name,
                "decision": event.decision,
                "confidence": event.confidence,
            }
            for event in events
        ]
        with self._session_factory() as db:
            db.add_all(events)
            self._update_candidate_status(db, candidate_id, "ai_reviewed")
            db.commit()
            event_count = len(events)

        if not (ai_review.audit_trace or {}).get("confidence_recorded"):
            self._record_confidence_reviews(
                payload=payload,
                ai_review=ai_review,
                events=confidence_snapshots,
            )
        return event_count

    def record_risk_decision(
        self,
        *,
        candidate_id: str,
        payload: M8Payload,
        decision_result: dict[str, Any],
        limits_snapshot: dict[str, Any] | None = None,
    ) -> None:
        decision = _enum_value(decision_result.get("decision"))
        reason = decision_result.get("reject_reason")
        with self._session_factory() as db:
            event = RiskDecisionEvent(
                candidate_id=candidate_id,
                signal_id=payload.signal_id,
                decision=decision,
                reason_code=str(reason) if reason else None,
                limits_snapshot_json=_json_dumps(limits_snapshot or {}),
            )
            db.add(event)
            db.commit()

    def update_candidate_status(self, candidate_id: str, status: str) -> None:
        with self._session_factory() as db:
            self._update_candidate_status(db, candidate_id, status)
            db.commit()

    def record_paper_outcome(
        self,
        *,
        position_snapshot: dict[str, Any],
        close_result: dict[str, Any],
        close_reason: str,
        outcome_source: str = "live_paper",
    ) -> str | None:
        """Persist a closed paper position outcome and attribute it to scouts."""
        if close_result.get("status") != "ok":
            return None

        candidate_id = position_snapshot.get("candidate_id")
        signal_id = position_snapshot.get("signal_id")
        trade_id = str(close_result.get("trade_id") or position_snapshot.get("trade_id") or "")
        if not trade_id:
            return None

        symbol = str(position_snapshot.get("symbol") or close_result.get("symbol") or "").upper()
        direction = str(position_snapshot.get("direction") or close_result.get("direction") or "")
        entry_price = float(position_snapshot.get("avg_entry_price") or 0.0)
        volume = float(position_snapshot.get("volume") or close_result.get("volume") or 0.0)
        exit_price = float(close_result.get("fill_price") or position_snapshot.get("current_price") or 0.0)
        pnl = float(close_result.get("pnl") or 0.0)
        notional = entry_price * volume
        pnl_pct = (pnl / notional) * 100.0 if notional else 0.0
        r_multiple = self._r_multiple(
            direction=direction,
            entry_price=entry_price,
            stop_loss=position_snapshot.get("stop_loss"),
            volume=volume,
            pnl=pnl,
        )
        win = pnl > 0.0
        duration_seconds = self._duration_seconds(position_snapshot.get("created_at"))

        with self._session_factory() as db:
            existing = (
                db.query(PaperOutcome)
                .filter(PaperOutcome.trade_id == trade_id)
                .first()
            )
            if existing:
                return existing.trade_id

            outcome = PaperOutcome(
                candidate_id=candidate_id,
                trade_id=trade_id,
                signal_id=signal_id,
                symbol=symbol,
                direction=direction,
                strategy_id=position_snapshot.get("strategy_id"),
                timeframe=position_snapshot.get("timeframe"),
                close_reason=close_reason,
                exit_price=exit_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
                r_multiple=r_multiple,
                win=win,
                duration_seconds=duration_seconds,
                outcome_source=outcome_source,
            )
            db.add(outcome)

            learning_events = self._build_learning_events(
                db=db,
                candidate_id=candidate_id,
                signal_id=signal_id,
                trade_id=trade_id,
                symbol=symbol,
                direction=direction,
                strategy_id=position_snapshot.get("strategy_id"),
                timeframe=position_snapshot.get("timeframe"),
                win=win,
                close_reason=close_reason,
                outcome_source=outcome_source,
            )
            confidence_updates = [
                (event.scout_name, bool(event.was_correct))
                for event in learning_events
            ]
            db.add_all(learning_events)
            if candidate_id:
                self._update_candidate_status(db, str(candidate_id), "paper_closed")
            db.commit()

        self._update_confidence_from_outcome(
            candidate_id=candidate_id,
            signal_id=signal_id,
            trade_id=trade_id,
            symbol=symbol,
            direction=direction,
            strategy_id=position_snapshot.get("strategy_id"),
            timeframe=position_snapshot.get("timeframe"),
            close_reason=close_reason,
            outcome_source=outcome_source,
            pnl_pct=pnl_pct,
            r_multiple=r_multiple,
            win=win,
            learning_events=confidence_updates,
        )
        return trade_id

    @staticmethod
    def _update_candidate_status(db: Session, candidate_id: str, status: str) -> None:
        candidate = (
            db.query(SignalCandidate)
            .filter(SignalCandidate.candidate_id == candidate_id)
            .first()
        )
        if candidate:
            candidate.status = status
            candidate.processed_at = datetime.now(timezone.utc)

    def _build_learning_events(
        self,
        *,
        db: Session,
        candidate_id: str | None,
        signal_id: str | None,
        trade_id: str,
        symbol: str,
        direction: str,
        strategy_id: str | None,
        timeframe: str | None,
        win: bool,
        close_reason: str,
        outcome_source: str,
    ) -> list[AgentLearningEvent]:
        query = db.query(AgentReviewEvent)
        if candidate_id:
            query = query.filter(AgentReviewEvent.candidate_id == candidate_id)
        elif signal_id:
            query = query.filter(AgentReviewEvent.signal_id == signal_id)
        else:
            return []

        events: list[AgentLearningEvent] = []
        for review in query.all():
            scout_approved = self._decision_is_approval(review.decision)
            was_correct = (scout_approved and win) or (not scout_approved and not win)
            events.append(
                AgentLearningEvent(
                    candidate_id=candidate_id,
                    trade_id=trade_id,
                    signal_id=signal_id,
                    scout_name=review.scout_name,
                    symbol=symbol,
                    direction=direction,
                    strategy_id=strategy_id,
                    timeframe=timeframe,
                    was_correct=was_correct,
                    outcome_source=outcome_source,
                    context_json=_json_dumps({
                        "close_reason": close_reason,
                        "review_decision": review.decision,
                        "review_confidence": review.confidence,
                    }),
                )
            )
        return events

    def _update_confidence_from_outcome(
        self,
        *,
        candidate_id: str | None,
        signal_id: str | None,
        trade_id: str,
        symbol: str,
        direction: str,
        strategy_id: str | None,
        timeframe: str | None,
        close_reason: str,
        outcome_source: str,
        pnl_pct: float,
        r_multiple: float,
        win: bool,
        learning_events: list[tuple[str, bool]],
    ) -> None:
        confidence_registry = self._get_confidence_registry()

        confidence_registry.record_trade_outcome(
            symbol=symbol,
            direction=direction,
            pnl_pct=pnl_pct,
            rr=r_multiple,
            win=win,
        )
        for scout_name, was_correct in learning_events:
            confidence_registry.mark_scout_outcome(
                symbol=symbol,
                scout_names=[scout_name],
                was_correct=was_correct,
                details={
                    "candidate_id": candidate_id,
                    "signal_id": signal_id,
                    "trade_id": trade_id,
                    "strategy_id": strategy_id,
                    "timeframe": timeframe,
                    "direction": direction,
                    "close_reason": close_reason,
                    "outcome_source": outcome_source,
                    "win": win,
                    "pnl_pct": pnl_pct,
                    "r_multiple": r_multiple,
                },
            )

    def _record_confidence_reviews(
        self,
        *,
        payload: M8Payload,
        ai_review: SignalReview,
        events: list[dict[str, Any]],
    ) -> None:
        confidence_registry = self._get_confidence_registry()
        confidence_registry.record_signal_review(
            symbol=payload.symbol,
            confluence=payload.confluence_score,
            crisis=payload.crisis_score,
            direction=payload.direction,
        )
        for event in events:
            confidence_registry.record_scout_review(
                symbol=payload.symbol,
                scout_name=str(event.get("scout_name") or ""),
                direction=payload.direction,
                decision=str(event.get("decision") or ""),
                confidence=float(event.get("confidence") or ai_review.confidence),
                was_correct=None,
            )

    def _get_confidence_registry(self) -> Any:
        if self._confidence_registry is None:
            from app.services.confidence_registry import confidence_registry

            self._confidence_registry = confidence_registry
        return self._confidence_registry

    @staticmethod
    def _decision_is_approval(decision: str | None) -> bool:
        normalized = (decision or "").upper()
        return normalized in {"PROCEED_TO_SIMULATION", "APPROVE", "APPROVED", "GO"}

    @staticmethod
    def _r_multiple(
        *,
        direction: str,
        entry_price: float,
        stop_loss: Any,
        volume: float,
        pnl: float,
    ) -> float:
        try:
            stop = float(stop_loss)
        except (TypeError, ValueError):
            return 0.0
        if direction.upper() == "LONG":
            risk_per_unit = entry_price - stop
        else:
            risk_per_unit = stop - entry_price
        risk_total = risk_per_unit * volume
        return pnl / risk_total if risk_total > 0 else 0.0

    @staticmethod
    def _duration_seconds(created_at: Any) -> float | None:
        if not created_at:
            return None
        if isinstance(created_at, datetime):
            start = created_at
        else:
            try:
                start = datetime.fromisoformat(str(created_at))
            except ValueError:
                return None
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - start).total_seconds())

    @staticmethod
    def _parse_timestamp(value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _payload_features(payload: M8Payload) -> dict[str, Any]:
        return {
            "intent": payload.intent,
            "account_mode": payload.account_mode,
            "relative_volume": payload.relative_volume,
            "crisis_score": payload.crisis_score,
            "mc_dispersion": payload.mc_dispersion,
            "spread": payload.spread,
            "pattern_detected": payload.pattern_detected,
            "pattern_score": payload.pattern_score,
            "market_regime": payload.market_regime,
            "bar_confirmed": payload.bar_confirmed,
            "order_command": payload.order_command,
        }

    @staticmethod
    def _scout_decision(scout_report: Any, ai_review: SignalReview) -> str:
        if isinstance(scout_report, dict):
            decision = scout_report.get("decision")
            if decision:
                return _enum_value(decision)
        return _enum_value(ai_review.decision)

    @staticmethod
    def _scout_confidence(scout_report: Any, ai_review: SignalReview) -> float:
        if isinstance(scout_report, dict):
            raw_confidence = scout_report.get("confidence")
            if raw_confidence is not None:
                try:
                    return max(0.0, min(1.0, float(raw_confidence)))
                except (TypeError, ValueError):
                    pass
            report = str(scout_report.get("report") or "")
        else:
            report = str(scout_report or "")

        lower = report.lower()
        if "confidence:" in lower:
            try:
                value = lower.split("confidence:", 1)[1].strip().split()[0]
                return max(0.0, min(1.0, float(value)))
            except (IndexError, ValueError):
                pass
        return ai_review.confidence

    @staticmethod
    def _scout_reasons(scout_report: Any, ai_review: SignalReview) -> list[str]:
        if isinstance(scout_report, dict):
            reasons = scout_report.get("reason_codes") or scout_report.get("reasons")
            if isinstance(reasons, list):
                return [str(reason) for reason in reasons]
        return [str(reason) for reason in ai_review.reason_codes]

    @staticmethod
    def _scout_model(trace: dict[str, Any], scout_name: str) -> str | None:
        models = trace.get("models") or trace.get("scout_models") or {}
        if isinstance(models, dict):
            model = models.get(scout_name)
            return str(model) if model else None
        model = trace.get("model")
        return str(model) if model else None

    @staticmethod
    def _scout_raw_report(scout_report: Any) -> str:
        if isinstance(scout_report, dict):
            report = scout_report.get("report")
            return str(report) if report is not None else _json_dumps(scout_report)
        return str(scout_report)


lifecycle_recorder = LifecycleRecorder()
