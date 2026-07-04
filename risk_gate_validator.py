#!/usr/bin/env python3
"""Deterministic preflight risk gate validator for Gem/LLM signal handoff."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import (
    COOLDOWN_BARS,
    MAX_CRISIS_SCORE,
    MAX_DAILY_DRAWDOWN,
    MAX_MC_DISPERSION,
    MAX_SPREAD,
    MAX_TRADES_PER_DAY,
    MIN_CONFLUENCE_SCORE,
    MIN_RR_RATIO,
)
from app.schemas.ai_review import DecisionEnum as AIDecisionEnum
from app.schemas.ai_review import SignalReview
from app.schemas.journal import DecisionEnum
from app.schemas.m8_payload import M8Payload
from app.services.war_room_rules import ai_rule_violation, classify_order


class RiskGateContext(BaseModel):
    """Optional deterministic context supplied by the caller."""

    model_config = ConfigDict(extra="allow")

    available_market_data_timestamp: str | None = None
    now_timestamp: str | None = None
    max_signal_age_seconds: int | None = Field(default=None, gt=0)
    seen_signal_ids: list[str] = Field(default_factory=list)
    duplicate_check_enabled: bool = True

    current_bar: int = 0
    last_trade_bar: int = -1
    trades_today: int = 0

    simulated_daily_drawdown_pct: float = Field(default=0.0, ge=0.0)
    max_daily_drawdown_pct: float | None = Field(default=None, gt=0.0)

    deterministic_direction: str | None = Field(
        default=None,
        pattern="^(LONG|SHORT|NEUTRAL)$",
    )

    slippage_model_applied: bool = True
    fee_model_present: bool = True
    order_fill_assumption: str | None = "DETERMINISTIC_FILL_MODEL"

    require_ai_review: bool = False
    ai_suggests_direct_execution: bool = False
    ai_references_future_information: bool = False
    ai_invents_unavailable_market_data: bool = False
    proposed_risk_parameter_changes: dict[str, Any] = Field(default_factory=dict)
    risk_parameter_change_approved: bool = False


class RiskGateRequest(BaseModel):
    """Validated wrapper request for a signal and optional AI review."""

    model_config = ConfigDict(extra="forbid")

    payload: M8Payload
    ai_review: SignalReview | None = None
    context: RiskGateContext = Field(default_factory=RiskGateContext)


def _validation_error_response(exc: ValidationError) -> dict[str, Any]:
    return {
        "ok": False,
        "decision": DecisionEnum.REJECT.value,
        "reject_reasons": ["SCHEMA_VALIDATION_FAILED"],
        "gate_results": [
            {
                "gate": "schema_validation",
                "passed": False,
                "reason_code": "SCHEMA_VALIDATION_FAILED",
                "detail": json.loads(exc.json()),
            }
        ],
        "metrics": {},
        "payload": None,
        "ai_review": None,
    }


def _build_request(raw: dict[str, Any]) -> RiskGateRequest:
    if "payload" in raw:
        data = dict(raw)
        if "risk_context" in data and "context" not in data:
            data["context"] = data.pop("risk_context")
    else:
        data = {"payload": raw}
    return RiskGateRequest.model_validate(data)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _risk_reward(payload: M8Payload) -> tuple[float | None, str | None]:
    if payload.direction == "LONG":
        risk = payload.entry_price - payload.stop_price
        reward = payload.target_price - payload.entry_price
    else:
        risk = payload.stop_price - payload.entry_price
        reward = payload.entry_price - payload.target_price

    if risk <= 0:
        return None, "INVALID_RISK"
    if reward <= 0:
        return None, "INVALID_REWARD"
    return reward / risk, None


def _append_gate(
    results: list[dict[str, Any]],
    gate: str,
    passed: bool,
    reason_code: str | None = None,
    detail: Any = None,
) -> None:
    results.append(
        {
            "gate": gate,
            "passed": bool(passed),
            "reason_code": None if passed else reason_code,
            "detail": detail,
        }
    )


def _collect_reject_reasons(gate_results: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    for gate in gate_results:
        code = gate.get("reason_code")
        if not gate.get("passed") and code and code not in reasons:
            reasons.append(code)
    return reasons


def validate_risk_gates(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Validate one Gem-produced signal before it can leave the LLM boundary.

    The function is intentionally deterministic: it does not fetch market data,
    query brokers, place orders, or call an LLM. Any external facts needed by a
    gate must be passed in the request context.
    """
    try:
        request = _build_request(raw)
    except ValidationError as exc:
        return _validation_error_response(exc)

    payload = request.payload
    ai_review = request.ai_review
    ctx = request.context
    entry_intent = payload.intent == "ENTRY"

    gate_results: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}

    _append_gate(
        gate_results,
        "m8_explicit_reject",
        not bool(payload.m8_reject_reason),
        "M8_EXPLICIT_REJECT",
        payload.m8_reject_reason,
    )

    _append_gate(
        gate_results,
        "invalidation_level",
        payload.stop_price > 0 and payload.stop_price != payload.entry_price,
        "INVALIDATION_MISSING",
        {"stop_price": payload.stop_price, "entry_price": payload.entry_price},
    )

    try:
        signal_ts = _parse_timestamp(payload.timestamp)
        _append_gate(gate_results, "signal_timestamp_parse", True)
    except ValueError as exc:
        signal_ts = None
        _append_gate(gate_results, "signal_timestamp_parse", False, "INVALID_TIMESTAMP", str(exc))

    if ctx.available_market_data_timestamp and signal_ts:
        try:
            market_ts = _parse_timestamp(ctx.available_market_data_timestamp)
            is_not_future = market_ts is None or signal_ts <= market_ts
            _append_gate(
                gate_results,
                "signal_not_newer_than_market_data",
                is_not_future,
                "SIGNAL_AFTER_AVAILABLE_MARKET_DATA",
                {
                    "signal_timestamp": payload.timestamp,
                    "available_market_data_timestamp": ctx.available_market_data_timestamp,
                },
            )
        except ValueError as exc:
            _append_gate(
                gate_results,
                "market_timestamp_parse",
                False,
                "INVALID_MARKET_DATA_TIMESTAMP",
                str(exc),
            )

    if ctx.max_signal_age_seconds and signal_ts:
        try:
            now_ts = _parse_timestamp(ctx.now_timestamp) if ctx.now_timestamp else datetime.now(timezone.utc)
            age_seconds = (now_ts - signal_ts).total_seconds() if now_ts else 0.0
            metrics["signal_age_seconds"] = round(age_seconds, 3)
            _append_gate(
                gate_results,
                "signal_freshness",
                age_seconds <= ctx.max_signal_age_seconds,
                "STALE_SIGNAL",
                {
                    "age_seconds": round(age_seconds, 3),
                    "max_signal_age_seconds": ctx.max_signal_age_seconds,
                },
            )
        except ValueError as exc:
            _append_gate(gate_results, "now_timestamp_parse", False, "INVALID_NOW_TIMESTAMP", str(exc))

    if ctx.duplicate_check_enabled:
        _append_gate(
            gate_results,
            "duplicate_signal",
            payload.signal_id not in set(ctx.seen_signal_ids),
            "DUPLICATE_SIGNAL",
            {"signal_id": payload.signal_id},
        )

    if entry_intent:
        war_room = classify_order(payload)
        _append_gate(
            gate_results,
            "war_room_order",
            war_room.reject_reason is None,
            war_room.reject_reason or "WAR_ROOM_BLOCK",
            war_room.to_dict(),
        )

        _append_gate(
            gate_results,
            "m8_confluence_score",
            payload.confluence_score >= MIN_CONFLUENCE_SCORE,
            "LOW_CONFLUENCE",
            {"value": payload.confluence_score, "minimum": MIN_CONFLUENCE_SCORE},
        )
        _append_gate(
            gate_results,
            "crisis_score",
            payload.crisis_score <= MAX_CRISIS_SCORE,
            "HIGH_CRISIS",
            {"value": payload.crisis_score, "maximum": MAX_CRISIS_SCORE},
        )
        _append_gate(
            gate_results,
            "monte_carlo_dispersion",
            payload.mc_dispersion <= MAX_MC_DISPERSION,
            "HIGH_DISPERSION",
            {"value": payload.mc_dispersion, "maximum": MAX_MC_DISPERSION},
        )
        _append_gate(
            gate_results,
            "spread",
            payload.spread <= MAX_SPREAD,
            "WIDE_SPREAD",
            {"value": payload.spread, "maximum": MAX_SPREAD},
        )

        rr_value, rr_error = _risk_reward(payload)
        metrics["risk_reward"] = None if rr_value is None else round(rr_value, 6)
        _append_gate(
            gate_results,
            "reward_risk_structure",
            rr_error is None,
            rr_error or "INVALID_RR_STRUCTURE",
            {
                "entry_price": payload.entry_price,
                "stop_price": payload.stop_price,
                "target_price": payload.target_price,
                "direction": payload.direction,
            },
        )
        if rr_error is None:
            _append_gate(
                gate_results,
                "minimum_reward_risk",
                rr_value is not None and rr_value >= MIN_RR_RATIO,
                "LOW_RR",
                {"value": rr_value, "minimum": MIN_RR_RATIO},
            )

        _append_gate(
            gate_results,
            "slippage_model",
            ctx.slippage_model_applied,
            "SLIPPAGE_MODEL_MISSING",
        )
        _append_gate(
            gate_results,
            "fee_model",
            ctx.fee_model_present,
            "FEE_MODEL_MISSING",
        )
        _append_gate(
            gate_results,
            "order_fill_assumption",
            bool(ctx.order_fill_assumption and ctx.order_fill_assumption.strip()),
            "ORDER_FILL_ASSUMPTION_UNKNOWN",
            ctx.order_fill_assumption,
        )

        cooldown_passes = ctx.last_trade_bar < 0 or (ctx.current_bar - ctx.last_trade_bar) >= COOLDOWN_BARS
        _append_gate(
            gate_results,
            "entry_cooldown",
            cooldown_passes,
            "COOLDOWN_ACTIVE",
            {
                "current_bar": ctx.current_bar,
                "last_trade_bar": ctx.last_trade_bar,
                "cooldown_bars": COOLDOWN_BARS,
            },
        )
        _append_gate(
            gate_results,
            "max_trades_per_day",
            ctx.trades_today < MAX_TRADES_PER_DAY,
            "MAX_TRADES_REACHED",
            {"trades_today": ctx.trades_today, "maximum": MAX_TRADES_PER_DAY},
        )

        max_dd = ctx.max_daily_drawdown_pct or MAX_DAILY_DRAWDOWN
        _append_gate(
            gate_results,
            "simulated_daily_drawdown",
            ctx.simulated_daily_drawdown_pct < max_dd,
            "SIMULATED_DAILY_DRAWDOWN_EXCEEDED",
            {"value": ctx.simulated_daily_drawdown_pct, "maximum": max_dd},
        )

        if ctx.deterministic_direction and ctx.deterministic_direction != "NEUTRAL":
            _append_gate(
                gate_results,
                "deterministic_market_state",
                payload.direction == ctx.deterministic_direction,
                "AI_DETERMINISTIC_MARKET_STATE_CONFLICT",
                {
                    "payload_direction": payload.direction,
                    "deterministic_direction": ctx.deterministic_direction,
                },
            )
    else:
        _append_gate(
            gate_results,
            "entry_only_gates",
            True,
            detail="CLOSE intent skips entry risk gates so exits remain available.",
        )

    if ctx.require_ai_review:
        _append_gate(gate_results, "ai_review_present", ai_review is not None, "AI_REVIEW_MISSING")

    if ai_review is not None:
        _append_gate(
            gate_results,
            "ai_signal_id_match",
            ai_review.signal_id == payload.signal_id,
            "AI_SIGNAL_ID_MISMATCH",
            {"payload_signal_id": payload.signal_id, "ai_signal_id": ai_review.signal_id},
        )
        _append_gate(
            gate_results,
            "ai_did_not_reject",
            ai_review.decision != AIDecisionEnum.REJECT,
            "AI_REJECT",
            {"ai_decision": ai_review.decision.value},
        )
        human_review_required = (
            ai_review.requires_human_review or ai_review.decision == AIDecisionEnum.HUMAN_REVIEW
        )
        _append_gate(
            gate_results,
            "ai_human_review",
            not human_review_required,
            "AI_HUMAN_REVIEW_REQUIRED",
            {
                "ai_decision": ai_review.decision.value,
                "requires_human_review": ai_review.requires_human_review,
            },
        )
        ai_scope_reason = ai_rule_violation(ai_review)
        _append_gate(
            gate_results,
            "ai_scope",
            ai_scope_reason is None,
            ai_scope_reason or "AI_SCOPE_VIOLATION",
            {
                "reason_codes": ai_review.reason_codes,
                "risk_flags": ai_review.risk_flags,
                "confidence": ai_review.confidence,
            },
        )

    _append_gate(
        gate_results,
        "ai_direct_execution",
        not ctx.ai_suggests_direct_execution,
        "AI_DIRECT_EXECUTION_REQUESTED",
    )
    _append_gate(
        gate_results,
        "ai_future_information",
        not ctx.ai_references_future_information,
        "AI_REFERENCES_FUTURE_INFORMATION",
    )
    _append_gate(
        gate_results,
        "ai_available_data_only",
        not ctx.ai_invents_unavailable_market_data,
        "AI_INVENTS_UNAVAILABLE_MARKET_DATA",
    )
    _append_gate(
        gate_results,
        "risk_parameter_changes",
        not ctx.proposed_risk_parameter_changes or ctx.risk_parameter_change_approved,
        "AI_RISK_PARAMETER_CHANGE_WITHOUT_APPROVAL",
        ctx.proposed_risk_parameter_changes,
    )

    reject_reasons = _collect_reject_reasons(gate_results)
    human_review_only = reject_reasons and all(
        reason in {"AI_HUMAN_REVIEW_REQUIRED"} for reason in reject_reasons
    )
    if not reject_reasons:
        decision = DecisionEnum.PROCEED_TO_SIMULATION
    elif human_review_only:
        decision = DecisionEnum.HUMAN_REVIEW
    else:
        decision = DecisionEnum.REJECT

    return {
        "ok": not reject_reasons,
        "decision": decision.value,
        "reject_reasons": reject_reasons,
        "gate_results": gate_results,
        "metrics": metrics,
        "payload": payload.model_dump(mode="json"),
        "ai_review": ai_review.model_dump(mode="json") if ai_review else None,
    }


def _read_json_input(path: str | None) -> dict[str, Any]:
    raw = sys.stdin.read() if not path or path == "-" else open(path, encoding="utf-8").read()
    return json.loads(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate deterministic risk gates for one signal.")
    parser.add_argument("--input", "-i", default="-", help="JSON file path, or '-' for stdin.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(argv)

    try:
        raw = _read_json_input(args.input)
        result = validate_risk_gates(raw)
    except (json.JSONDecodeError, OSError) as exc:
        result = {
            "ok": False,
            "decision": DecisionEnum.REJECT.value,
            "reject_reasons": ["INVALID_JSON"],
            "gate_results": [
                {
                    "gate": "json_parse",
                    "passed": False,
                    "reason_code": "INVALID_JSON",
                    "detail": str(exc),
                }
            ],
            "metrics": {},
            "payload": None,
            "ai_review": None,
        }

    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=args.pretty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
