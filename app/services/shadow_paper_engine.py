from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from app.schemas.ai_review import DecisionEnum as AIDecisionEnum, SignalReview
from app.schemas.journal import DecisionEnum
from app.schemas.m8_payload import M8Payload
from app.services.confidence_registry import confidence_registry
from app.services.risk_engine import RiskEngine
from app.services.signal_generator import OHLCV, signal_generator_instance


PAPER_EXECUTED = "EXECUTED_PAPER"
PAPER_REJECTED = "REJECTED_PAPER"


@dataclass(frozen=True)
class PaperTradeOutcome:
    exit_reason: str
    entry_index: int
    exit_index: int
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    pnl_quote: float
    pnl_pct: float
    r_multiple: float
    win: bool
    bars_held: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "exit_reason": self.exit_reason,
            "entry_index": self.entry_index,
            "exit_index": self.exit_index,
            "entry_time": self.entry_time,
            "exit_time": self.exit_time,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl_quote": self.pnl_quote,
            "pnl_pct": self.pnl_pct,
            "r_multiple": self.r_multiple,
            "win": self.win,
            "bars_held": self.bars_held,
        }


class ShadowPaperEngine:
    """
    Local paper-trading engine for Pionex-first development.

    It deliberately separates the strict live decision from the paper decision:
    rejected live candidates can still be simulated locally to create outcome
    feedback for the AI confidence registry. It never places broker orders.
    """

    SCOUT_NAMES = ["technical", "sentiment", "risk", "macro", "execution", "correlation"]

    def __init__(self) -> None:
        self.last_replay: dict[str, Any] | None = None

    async def replay(
        self,
        symbol: str = "HYPEUSDT",
        timeframe: str = "1m",
        bars: int = 500,
        max_signals: Optional[int] = 50,
        min_confluence: Optional[float] = None,
        max_holding_bars: int = 50,
        use_ai: bool = True,
    ) -> dict[str, Any]:
        payloads = signal_generator_instance.generate_payloads(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
            min_confluence=min_confluence,
        )
        generation_summary = getattr(signal_generator_instance, "last_generation_summary", {})
        raw_bars = getattr(signal_generator_instance, "last_raw_bars", [])

        if max_signals:
            payloads = payloads[:max_signals]

        bar_index = {self._bar_time(bar): index for index, bar in enumerate(raw_bars)}
        live_risk = RiskEngine()
        results: list[dict[str, Any]] = []

        for payload in payloads:
            entry_index = bar_index.get(payload.timestamp)
            if entry_index is None:
                results.append(self._missing_bar_result(payload))
                continue

            ai_review = await self._review_payload(payload, use_ai=use_ai)
            live_risk.current_bar = entry_index
            live_decision = live_risk.evaluate(payload, ai_review)
            if live_decision["decision"] == DecisionEnum.PROCEED_TO_SIMULATION:
                live_risk.last_trade_bar = live_risk.current_bar
                live_risk.trades_today += 1

            paper_decision, paper_reject_reason = self._paper_decision(payload)
            outcome: PaperTradeOutcome | None = None
            if paper_decision == PAPER_EXECUTED:
                try:
                    outcome = self.simulate_trade(payload, raw_bars, entry_index, max_holding_bars)
                    self._record_learning(payload, ai_review, outcome)
                except ValueError as exc:
                    paper_decision = PAPER_REJECTED
                    paper_reject_reason = str(exc)

            results.append(
                {
                    "signal_id": payload.signal_id,
                    "symbol": payload.symbol,
                    "timeframe": payload.timeframe,
                    "direction": payload.direction,
                    "entry_price": payload.entry_price,
                    "stop_price": payload.stop_price,
                    "target_price": payload.target_price,
                    "confluence_score": payload.confluence_score,
                    "crisis_score": payload.crisis_score,
                    "live_decision": self._enum_value(live_decision["decision"]),
                    "live_reject_reason": live_decision.get("reject_reason"),
                    "paper_decision": paper_decision,
                    "paper_reject_reason": paper_reject_reason,
                    "ai_decision": self._enum_value(ai_review.decision),
                    "ai_confidence": ai_review.confidence,
                    "ai_trace": ai_review.audit_trace,
                    "outcome": outcome.to_dict() if outcome else None,
                    "confidence_after": confidence_registry.dump().get(payload.symbol.upper(), {}),
                }
            )

        summary = self._summary(results)
        response = {
            "status": "ok",
            "mode": "shadow_paper",
            "symbol": symbol,
            "timeframe": timeframe,
            "bars_analyzed": len(raw_bars),
            "signals_generated": len(payloads),
            "max_holding_bars": max_holding_bars,
            "generation_summary": generation_summary,
            **summary,
            "results": results,
        }
        self.last_replay = response
        return response

    def simulate_trade(
        self,
        payload: M8Payload,
        bars: list[OHLCV],
        entry_index: int,
        max_holding_bars: int = 50,
    ) -> PaperTradeOutcome:
        if entry_index >= len(bars) - 1:
            raise ValueError("No future bars available for paper trade simulation")

        risk = self._risk_per_unit(payload)
        if risk <= 0:
            raise ValueError("Invalid risk for paper trade simulation")

        start = entry_index + 1
        end = min(len(bars) - 1, entry_index + max(1, max_holding_bars))
        exit_index = end
        exit_price = bars[end].c
        exit_reason = "TIME_EXIT"

        for index in range(start, end + 1):
            bar = bars[index]
            if payload.direction == "LONG":
                # Stop-first on same candle keeps ambiguous intrabar outcomes conservative.
                if bar.l <= payload.stop_price:
                    exit_index = index
                    exit_price = payload.stop_price
                    exit_reason = "STOP_LOSS"
                    break
                if bar.h >= payload.target_price:
                    exit_index = index
                    exit_price = payload.target_price
                    exit_reason = "TAKE_PROFIT"
                    break
            else:
                if bar.h >= payload.stop_price:
                    exit_index = index
                    exit_price = payload.stop_price
                    exit_reason = "STOP_LOSS"
                    break
                if bar.l <= payload.target_price:
                    exit_index = index
                    exit_price = payload.target_price
                    exit_reason = "TAKE_PROFIT"
                    break

        if payload.direction == "LONG":
            pnl_quote = exit_price - payload.entry_price
        else:
            pnl_quote = payload.entry_price - exit_price

        r_multiple = pnl_quote / risk
        return PaperTradeOutcome(
            exit_reason=exit_reason,
            entry_index=entry_index,
            exit_index=exit_index,
            entry_time=self._bar_time(bars[entry_index]),
            exit_time=self._bar_time(bars[exit_index]),
            entry_price=payload.entry_price,
            exit_price=exit_price,
            pnl_quote=pnl_quote,
            pnl_pct=r_multiple * 100.0,
            r_multiple=r_multiple,
            win=pnl_quote > 0,
            bars_held=exit_index - entry_index,
        )

    async def _review_payload(self, payload: M8Payload, use_ai: bool) -> SignalReview:
        if not use_ai:
            return SignalReview(
                schema_version="1.0",
                signal_id=payload.signal_id,
                decision=AIDecisionEnum.PROCEED_TO_SIMULATION,
                confidence=0.5,
                reason_codes=["PAPER_REPLAY_AI_DISABLED"],
                risk_flags=[],
                reject_reason=None,
                requires_human_review=False,
                audit_trace={"mode": "paper_replay_ai_disabled"},
            )

        from app.api import orchestrator

        review_result = orchestrator.ai_review_instance.review_signal(payload)
        return await review_result if inspect.isawaitable(review_result) else review_result

    def _record_learning(
        self,
        payload: M8Payload,
        ai_review: SignalReview,
        outcome: PaperTradeOutcome,
    ) -> None:
        confidence_registry.record_trade_outcome(
            symbol=payload.symbol,
            direction=payload.direction,
            pnl_pct=outcome.pnl_pct,
            rr=abs(outcome.r_multiple),
            win=outcome.win,
        )

        ai_approved = ai_review.decision == AIDecisionEnum.PROCEED_TO_SIMULATION
        ai_rejected = ai_review.decision == AIDecisionEnum.REJECT
        was_correct: bool | None = None
        if ai_approved:
            was_correct = outcome.win
        elif ai_rejected:
            was_correct = not outcome.win

        if was_correct is not None:
            confidence_registry.mark_scout_outcome(
                symbol=payload.symbol,
                scout_names=self.SCOUT_NAMES,
                was_correct=was_correct,
            )

    @staticmethod
    def _paper_decision(payload: M8Payload) -> tuple[str, str | None]:
        if payload.intent != "ENTRY":
            return PAPER_REJECTED, "PAPER_ENTRY_ONLY"
        risk = ShadowPaperEngine._risk_per_unit(payload)
        reward = ShadowPaperEngine._reward_per_unit(payload)
        if risk <= 0:
            return PAPER_REJECTED, "PAPER_INVALID_RISK"
        if reward <= 0:
            return PAPER_REJECTED, "PAPER_INVALID_REWARD"
        return PAPER_EXECUTED, None

    @staticmethod
    def _risk_per_unit(payload: M8Payload) -> float:
        if payload.direction == "LONG":
            return payload.entry_price - payload.stop_price
        return payload.stop_price - payload.entry_price

    @staticmethod
    def _reward_per_unit(payload: M8Payload) -> float:
        if payload.direction == "LONG":
            return payload.target_price - payload.entry_price
        return payload.entry_price - payload.target_price

    @staticmethod
    def _bar_time(bar: OHLCV) -> str:
        return datetime.fromtimestamp(bar.ts / 1000.0, tz=timezone.utc).isoformat()

    @staticmethod
    def _enum_value(value: Any) -> Any:
        return value.value if hasattr(value, "value") else value

    @staticmethod
    def _missing_bar_result(payload: M8Payload) -> dict[str, Any]:
        return {
            "signal_id": payload.signal_id,
            "symbol": payload.symbol,
            "timeframe": payload.timeframe,
            "direction": payload.direction,
            "entry_price": payload.entry_price,
            "live_decision": "UNKNOWN",
            "live_reject_reason": "ENTRY_BAR_NOT_FOUND",
            "paper_decision": PAPER_REJECTED,
            "paper_reject_reason": "ENTRY_BAR_NOT_FOUND",
            "ai_decision": None,
            "ai_confidence": None,
            "ai_trace": None,
            "outcome": None,
            "confidence_after": confidence_registry.dump().get(payload.symbol.upper(), {}),
        }

    @staticmethod
    def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
        paper_executed = sum(1 for row in results if row.get("paper_decision") == PAPER_EXECUTED)
        paper_rejected = sum(1 for row in results if row.get("paper_decision") == PAPER_REJECTED)
        live_rejected = sum(1 for row in results if row.get("live_decision") == DecisionEnum.REJECT.value)
        wins = sum(1 for row in results if (row.get("outcome") or {}).get("win") is True)
        losses = sum(1 for row in results if (row.get("outcome") or {}).get("win") is False)
        total_r = sum(float((row.get("outcome") or {}).get("r_multiple") or 0.0) for row in results)
        return {
            "paper_executed": paper_executed,
            "paper_rejected": paper_rejected,
            "live_rejected": live_rejected,
            "wins": wins,
            "losses": losses,
            "win_rate": wins / paper_executed if paper_executed else 0.0,
            "total_r": total_r,
        }


shadow_paper_engine = ShadowPaperEngine()
