from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from app.core.config import (
    WAR_ROOM_AI_MIN_CONFIDENCE,
    WAR_ROOM_CHOP_STANDBY_THRESHOLD,
    WAR_ROOM_ENABLED,
    WAR_ROOM_HARD_KILL_DRAWDOWN_PCT,
    WAR_ROOM_HURST_HAZARD_THRESHOLD,
    WAR_ROOM_ORANGE_MAX_RISK_PCT,
    WAR_ROOM_PENDING_ORDER_MAX_AGE_SECONDS,
    WAR_ROOM_VIP_CONFLUENCE_SCORE,
    WAR_ROOM_VIP_MAX_CRISIS_SCORE,
    WAR_ROOM_VIP_MAX_MC_DISPERSION,
    WAR_ROOM_VIP_RELATIVE_VOLUME,
)
from app.schemas.ai_review import SignalReview
from app.schemas.m8_payload import M8Payload


class WarRoomColor(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"


class WarRoomCommand(str, Enum):
    GO = "GO"
    HOLD = "HOLD"
    KILL = "KILL"


@dataclass(frozen=True)
class WarRoomDecision:
    color: WarRoomColor
    command: WarRoomCommand
    reason_codes: tuple[str, ...]
    risk_cap_pct: float | None = None
    kelly_mode_hint: str = "half_kelly_capped"

    def to_dict(self) -> dict:
        return {
            "color": self.color.value,
            "command": self.command.value,
            "reason_codes": list(self.reason_codes),
            "risk_cap_pct": self.risk_cap_pct,
            "kelly_mode_hint": self.kelly_mode_hint,
        }

    @property
    def reject_reason(self) -> str | None:
        if self.command == WarRoomCommand.GO:
            return None
        return self.reason_codes[0] if self.reason_codes else f"WAR_ROOM_{self.command.value}"


def _upper_items(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(str(value).upper() for value in values)


def classify_order(payload: M8Payload) -> WarRoomDecision:
    if not WAR_ROOM_ENABLED:
        return WarRoomDecision(
            color=WarRoomColor.GREEN,
            command=WarRoomCommand.GO,
            reason_codes=("WAR_ROOM_DISABLED",),
        )

    if payload.intent == "CLOSE":
        return WarRoomDecision(
            color=WarRoomColor.GREEN,
            command=WarRoomCommand.GO,
            reason_codes=("CLOSE_INTENT_PRIORITY",),
        )

    explicit_command = WarRoomCommand(payload.order_command)
    if explicit_command == WarRoomCommand.KILL:
        return WarRoomDecision(
            color=WarRoomColor.RED,
            command=WarRoomCommand.KILL,
            reason_codes=("WAR_ROOM_KILL_COMMAND",),
        )
    if explicit_command == WarRoomCommand.HOLD:
        return WarRoomDecision(
            color=WarRoomColor.YELLOW,
            command=WarRoomCommand.HOLD,
            reason_codes=("WAR_ROOM_HOLD_COMMAND",),
        )

    explicit_regime = WarRoomColor(payload.market_regime) if payload.market_regime else None
    if explicit_regime == WarRoomColor.RED:
        return WarRoomDecision(
            color=WarRoomColor.RED,
            command=WarRoomCommand.KILL,
            reason_codes=("WAR_ROOM_RED_REGIME",),
        )
    if explicit_regime == WarRoomColor.YELLOW:
        return WarRoomDecision(
            color=WarRoomColor.YELLOW,
            command=WarRoomCommand.HOLD,
            reason_codes=("WAR_ROOM_YELLOW_STANDBY",),
        )

    if not payload.bar_confirmed:
        return WarRoomDecision(
            color=WarRoomColor.YELLOW,
            command=WarRoomCommand.HOLD,
            reason_codes=("BAR_NOT_CONFIRMED",),
        )

    if payload.drawdown_pct is not None and payload.drawdown_pct >= WAR_ROOM_HARD_KILL_DRAWDOWN_PCT:
        return WarRoomDecision(
            color=WarRoomColor.RED,
            command=WarRoomCommand.KILL,
            reason_codes=("DRAWDOWN_HARD_KILL",),
        )

    max_age = payload.max_pending_order_age_seconds or WAR_ROOM_PENDING_ORDER_MAX_AGE_SECONDS
    if payload.pending_order_age_seconds is not None and payload.pending_order_age_seconds > max_age:
        return WarRoomDecision(
            color=WarRoomColor.RED,
            command=WarRoomCommand.KILL,
            reason_codes=("PENDING_ORDER_EXPIRED",),
        )

    if payload.chop_index is not None and payload.chop_index > WAR_ROOM_CHOP_STANDBY_THRESHOLD:
        return WarRoomDecision(
            color=WarRoomColor.YELLOW,
            command=WarRoomCommand.HOLD,
            reason_codes=("CHOP_STANDBY",),
        )

    hazard_reasons: list[str] = []
    if payload.hurst_exponent is not None and payload.hurst_exponent < WAR_ROOM_HURST_HAZARD_THRESHOLD:
        hazard_reasons.append("HURST_HAZARD")
    if payload.macro_event_risk:
        hazard_reasons.append("MACRO_EVENT_RISK")
    if explicit_regime == WarRoomColor.ORANGE:
        hazard_reasons.append("WAR_ROOM_ORANGE_REGIME")

    if hazard_reasons:
        return WarRoomDecision(
            color=WarRoomColor.ORANGE,
            command=WarRoomCommand.GO,
            reason_codes=tuple(hazard_reasons),
            risk_cap_pct=WAR_ROOM_ORANGE_MAX_RISK_PCT,
            kelly_mode_hint="orange_base_risk_cap",
        )

    vip_reasons = ["WAR_ROOM_GREEN_GO"]
    if (
        payload.confluence_score >= WAR_ROOM_VIP_CONFLUENCE_SCORE
        and payload.crisis_score <= WAR_ROOM_VIP_MAX_CRISIS_SCORE
        and payload.mc_dispersion <= WAR_ROOM_VIP_MAX_MC_DISPERSION
        and (
            payload.relative_volume is None
            or payload.relative_volume >= WAR_ROOM_VIP_RELATIVE_VOLUME
        )
    ):
        vip_reasons.append("VIP_REGIME_CANDIDATE")

    return WarRoomDecision(
        color=WarRoomColor.GREEN,
        command=WarRoomCommand.GO,
        reason_codes=tuple(vip_reasons),
        kelly_mode_hint="half_kelly_capped",
    )


def ai_rule_violation(ai_review: SignalReview) -> str | None:
    if not WAR_ROOM_ENABLED:
        return None

    if ai_review.confidence < WAR_ROOM_AI_MIN_CONFIDENCE:
        return "AI_LOW_CONFIDENCE"

    combined = _upper_items(ai_review.reason_codes or ()) + _upper_items(ai_review.risk_flags or ())
    forbidden_markers = (
        "BYPASS_RISK",
        "FORCE_ORDER",
        "FORCE_LIVE",
        "PLACE_ORDER",
        "DIRECT_EXECUTION",
        "IGNORE_GATES",
    )
    for marker in forbidden_markers:
        if any(marker in item for item in combined):
            return "AI_SCOPE_VIOLATION"

    if any("UNCONFIRMED_BAR" in item for item in combined):
        return "AI_UNCONFIRMED_BAR"

    return None

