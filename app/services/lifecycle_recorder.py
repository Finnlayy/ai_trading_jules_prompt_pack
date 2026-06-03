"""Persistence helpers for the paper-training lifecycle audit trail."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.db.models import AgentReviewEvent, RiskDecisionEvent, SignalCandidate
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

    def __init__(self, session_factory: Callable[[], Session] = SessionLocal) -> None:
        self._session_factory = session_factory

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

        with self._session_factory() as db:
            db.add_all(events)
            self._update_candidate_status(db, candidate_id, "ai_reviewed")
            db.commit()
            return len(events)

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
