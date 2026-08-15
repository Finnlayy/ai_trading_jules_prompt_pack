from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import desc

from app.core import config
from app.db import SessionLocal
from app.db.models import PaperBalance, PaperOutcome, PaperPosition, PaperTrade
from app.schemas.ai_review import DecisionEnum, SignalReview
from app.schemas.m8_payload import M8Payload
from app.services.ai.gem_agents import GEM_AGENT_DEFINITIONS, GEM_AGENT_NAMES, AgentDefinition
from app.services.ai.gem_pipeline import (
    LIVE_TRADE_EVALUATION,
    GemInputRouter,
    redact_secret_context,
)
from app.services.ai_kimi import KimiSwarmService
from app.services.ai_layer_memory import ai_layer_memory_instance
from app.services.confidence_registry import confidence_registry, ScoutReviewParams


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class GemContextBuilder:
    """Builds secret-free backend context for the native 10-Gem review path."""

    async def build(self, payload: M8Payload, mode: str = LIVE_TRADE_EVALUATION) -> dict[str, Any]:
        paper_snapshot = await asyncio.to_thread(self._paper_snapshot, payload.symbol)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "payload": payload.model_dump(mode="json"),
            "behavior_profile": ai_layer_memory_instance.get_profile().model_dump(),
            "behavior_prompt": ai_layer_memory_instance.behavior_prompt(),
            "learning": self._learning_snapshot(payload.symbol, payload.direction),
            "strategy": self._strategy_snapshot(),
            "risk_limits": self._risk_limits_snapshot(),
            "paper": paper_snapshot,
            "hard_rules": {
                "gems_do_not_execute_orders": True,
                "deterministic_risk_engine_is_authoritative": True,
                "real_money_orders_are_not_allowed_from_ai": True,
                "final_runtime_contract": "SignalReview",
            },
        }

    async def build_generic(
        self,
        mode: str,
        context: dict[str, Any],
        symbol: str | None,
        direction: str | None,
        output_contract: str,
        selected_phases: tuple[int, ...],
        selected_gems: tuple[str, ...],
        allowed_actions: tuple[str, ...],
    ) -> dict[str, Any]:
        paper_snapshot = await asyncio.to_thread(self._paper_snapshot, symbol or "")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "input": redact_secret_context(context),
            "symbol": symbol.upper() if symbol else None,
            "direction": direction.upper() if direction else None,
            "input_router": {
                "selected_phases": list(selected_phases),
                "selected_gems": list(selected_gems),
                "output_contract": output_contract,
                "allowed_actions": list(allowed_actions),
            },
            "behavior_profile": ai_layer_memory_instance.get_profile().model_dump(),
            "behavior_prompt": ai_layer_memory_instance.behavior_prompt(),
            "learning": self._learning_snapshot(symbol, direction),
            "strategy": self._strategy_snapshot(),
            "risk_limits": self._risk_limits_snapshot(),
            "paper": paper_snapshot,
            "hard_rules": {
                "gems_do_not_execute_orders": True,
                "backend_supplies_data": True,
                "backend_executes_only_allowed_actions": True,
                "deterministic_risk_engine_is_authoritative": True,
                "real_money_orders_are_not_allowed_from_ai": True,
                "final_runtime_contract": output_contract,
            },
        }

    def _learning_snapshot(self, symbol: str | None, direction: str | None) -> dict[str, Any]:
        if not symbol:
            return {
                "available": False,
                "reason": "symbol_not_supplied",
                "agent_weights": {name: 1.0 for name in GEM_AGENT_NAMES},
            }
        symbol = symbol.upper()
        direction_value = (direction or "LONG").upper()
        stats = confidence_registry.dump().get(symbol, {})
        return {
            "available": True,
            "symbol_context": confidence_registry.get_symbol_context(symbol, direction_value),
            "agent_weights": {
                name: confidence_registry.get_scout_weight(symbol, name)
                for name in GEM_AGENT_NAMES
            },
            "symbol_stats": stats,
        }

    @staticmethod
    def _strategy_snapshot() -> dict[str, Any]:
        try:
            from app.services.strategy_engine import strategy_registry

            active = strategy_registry.get_active_strategy()
            metadata = active.get_metadata()
            return {
                "active_strategy_id": strategy_registry.active_strategy_id,
                "available": strategy_registry.list_strategies(),
                "metadata": metadata.model_dump() if hasattr(metadata, "model_dump") else str(metadata),
            }
        except Exception as exc:
            return {"available": False, "error": type(exc).__name__}

    @staticmethod
    def _risk_limits_snapshot() -> dict[str, Any]:
        return {
            "min_rr_ratio": config.MIN_RR_RATIO,
            "max_spread": config.MAX_SPREAD,
            "min_confluence_score": config.MIN_CONFLUENCE_SCORE,
            "max_crisis_score": config.MAX_CRISIS_SCORE,
            "max_mc_dispersion": config.MAX_MC_DISPERSION,
            "max_daily_drawdown": config.MAX_DAILY_DRAWDOWN,
            "max_trades_per_day": config.MAX_TRADES_PER_DAY,
            "cooldown_bars": config.COOLDOWN_BARS,
            "war_room_enabled": config.WAR_ROOM_ENABLED,
            "war_room_ai_min_confidence": config.WAR_ROOM_AI_MIN_CONFIDENCE,
        }

    @staticmethod
    def _paper_snapshot(symbol: str) -> dict[str, Any]:
        if not symbol:
            return {"available": False, "reason": "symbol_not_supplied"}
        symbol_upper = symbol.upper()
        try:
            with SessionLocal() as db:
                balance = db.query(PaperBalance).filter(PaperBalance.currency == "USD").first()
                positions = (
                    db.query(PaperPosition)
                    .filter(PaperPosition.status == "open")
                    .order_by(desc(PaperPosition.created_at))
                    .limit(10)
                    .all()
                )
                trades = (
                    db.query(PaperTrade)
                    .order_by(desc(PaperTrade.created_at))
                    .limit(10)
                    .all()
                )
                outcomes = (
                    db.query(PaperOutcome)
                    .filter(PaperOutcome.symbol == symbol_upper)
                    .order_by(desc(PaperOutcome.created_at))
                    .limit(10)
                    .all()
                )
                return {
                    "available": True,
                    "balance": {
                        "currency": balance.currency if balance else "USD",
                        "balance": balance.balance if balance else None,
                        "equity": balance.equity if balance else None,
                        "total_pnl": balance.total_pnl if balance else None,
                    },
                    "open_positions": [
                        {
                            "symbol": pos.symbol,
                            "direction": pos.direction,
                            "volume": pos.volume,
                            "avg_entry_price": pos.avg_entry_price,
                            "unrealized_pnl": pos.unrealized_pnl,
                            "realized_pnl": pos.realized_pnl,
                            "stop_loss": pos.stop_loss,
                            "take_profit": pos.take_profit,
                            "strategy_id": pos.strategy_id,
                            "timeframe": pos.timeframe,
                        }
                        for pos in positions
                    ],
                    "recent_trades": [
                        {
                            "symbol": trade.symbol,
                            "direction": trade.direction,
                            "status": trade.status,
                            "volume": trade.volume,
                            "entry_price": trade.entry_price,
                            "exit_price": trade.exit_price,
                            "pnl": trade.pnl,
                            "strategy_id": trade.strategy_id,
                            "timeframe": trade.timeframe,
                        }
                        for trade in trades
                    ],
                    "recent_outcomes": [
                        {
                            "symbol": outcome.symbol,
                            "direction": outcome.direction,
                            "pnl": outcome.pnl,
                            "pnl_pct": outcome.pnl_pct,
                            "r_multiple": outcome.r_multiple,
                            "win": outcome.win,
                            "close_reason": outcome.close_reason,
                        }
                        for outcome in outcomes
                    ],
                }
        except Exception as exc:
            return {"available": False, "error": type(exc).__name__}


class GemNativeReviewService(KimiSwarmService):
    """Backend-native 10-Gem AI review engine.

    It keeps the public runtime contract identical to KimiSwarmService:
    review_signal(payload) returns SignalReview and never executes orders.
    """

    SCOUT_NAMES = list(GEM_AGENT_NAMES)

    def __init__(self, provider: str | None = None, context_builder: GemContextBuilder | None = None) -> None:
        super().__init__(provider=provider)
        self.context_builder = context_builder or GemContextBuilder()
        self.input_router = GemInputRouter()

    def _prompt_base_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "ai_prompts" / "gems"

    def get_prompt_for_scout(self, scout_name: str) -> str:
        prompt_path = self._prompt_base_dir() / scout_name / "v_active.md"
        if prompt_path.exists():
            active_text = prompt_path.read_text(encoding="utf-8").strip()
            if active_text and "\n" not in active_text and active_text.endswith(".md"):
                candidate = (prompt_path.parent / active_text).resolve()
                try:
                    candidate.relative_to(prompt_path.parent.resolve())
                except ValueError:
                    return active_text
                if candidate.is_file():
                    return candidate.read_text(encoding="utf-8")
            return active_text
        definition = next((item for item in GEM_AGENT_DEFINITIONS if item.name == scout_name), None)
        display = definition.display_name if definition else scout_name
        return f"You are {display}. Review only the provided backend context and return structured JSON."

    async def review_signal(self, payload: M8Payload) -> SignalReview:
        try:
            mode = LIVE_TRADE_EVALUATION
            selected_definitions = self.input_router.definitions_for_mode(mode)
            context = await self.context_builder.build(payload, mode=mode)
            results = await asyncio.gather(
                *(self._run_gem(definition, context) for definition in selected_definitions)
            )
            scout_reports = {name: report for name, report in results}
            review = self._synthesize(payload, scout_reports, context)
            self._record_confidence(payload, scout_reports)
            selected_phases = [definition.phase_id for definition in selected_definitions if definition.phase_id]
            selected_gems = [definition.name for definition in selected_definitions]
            review.audit_trace = {
                **self._trace_base(),
                "engine": "gem10_native",
                "mode": mode,
                "selected_phases": selected_phases,
                "selected_gems": selected_gems,
                "scouts": scout_reports,
                "backend_context": context,
                "scout_weights": {
                    name: confidence_registry.get_scout_weight(payload.symbol, name)
                    for name in selected_gems
                },
                "weighted_scout_vote": review.audit_trace.get("weighted_scout_vote") if review.audit_trace else {},
                "confidence_recorded": True,
                "final_summary": {
                    "decision": review.decision.value,
                    "confidence": review.confidence,
                    "reason_codes": review.reason_codes,
                    "risk_flags": review.risk_flags,
                    "requires_human_review": review.requires_human_review,
                    "reject_reason": review.reject_reason,
                },
            }
            return review
        except Exception as exc:
            return self._fatal_fallback(payload, exc)

    async def review_pipeline(
        self,
        *,
        mode: str = "auto",
        context: dict[str, Any] | None = None,
        symbol: str | None = None,
        direction: str | None = None,
        output_contract: str | None = None,
        return_prompt_only: bool = False,
    ) -> dict[str, Any]:
        request_context = context or {}
        resolved_mode = self.input_router.resolve_mode(mode, request_context)
        selected_definitions = self.input_router.definitions_for_mode(resolved_mode)
        selected_phases = tuple(definition.phase_id for definition in selected_definitions if definition.phase_id)
        selected_gems = tuple(definition.name for definition in selected_definitions)
        final_contract = self.input_router.output_contract_for_mode(resolved_mode, output_contract)
        allowed_actions = self.input_router.allowed_actions_for_mode(resolved_mode)
        backend_context = await self.context_builder.build_generic(
            mode=resolved_mode,
            context=request_context,
            symbol=symbol,
            direction=direction,
            output_contract=final_contract,
            selected_phases=selected_phases,
            selected_gems=selected_gems,
            allowed_actions=allowed_actions,
        )

        generated_prompts: dict[str, dict[str, str]] = {}
        for definition in selected_definitions:
            system, user_prompt = self._build_gem_messages(definition, backend_context)
            generated_prompts[definition.name] = {"system": system, "user": user_prompt}
        if return_prompt_only:
            return {
                "status": "ok",
                "engine": "gem10_native",
                "provider": self.provider or config.AI_PROVIDER,
                "requested_mode": mode,
                "mode": resolved_mode,
                "selected_phases": list(selected_phases),
                "selected_gems": list(selected_gems),
                "allowed_actions": list(allowed_actions),
                "output_contract": final_contract,
                "used_llm": False,
                "decision": DecisionEnum.HUMAN_REVIEW.value,
                "confidence": 0.5,
                "reason_codes": ["PROMPT_ONLY"],
                "risk_flags": [],
                "summary": "Generated Gem10 pipeline prompts without provider execution.",
                "gem_reports": {},
                "backend_context": backend_context,
                "generated_prompts": generated_prompts,
            }

        results = await asyncio.gather(
            *(self._run_gem(definition, backend_context) for definition in selected_definitions)
        )
        gem_reports = {name: report for name, report in results}
        response = self._synthesize_pipeline(
            mode=resolved_mode,
            requested_mode=mode,
            symbol=symbol,
            selected_phases=selected_phases,
            selected_gems=selected_gems,
            allowed_actions=allowed_actions,
            output_contract=final_contract,
            gem_reports=gem_reports,
            backend_context=backend_context,
            generated_prompts={},
        )
        self._record_pipeline_confidence(symbol, direction, gem_reports)
        return response

    async def _run_gem(
        self,
        definition: AgentDefinition,
        context: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        system, user_prompt = self._build_gem_messages(definition, context)
        try:
            raw = await self._call_llm_for_scout(
                definition.name,
                user_prompt,
                system=system,
                response_format={"type": "json_object"},
            )
            parsed = self._parse_gem_response(raw)
        except Exception as exc:
            parsed = {
                "decision": DecisionEnum.HUMAN_REVIEW.value,
                "confidence": 0.5,
                "reason_codes": ["GEM_REVIEW_UNAVAILABLE"],
                "risk_flags": [self._provider_unavailable_flag()],
                "report": f"{definition.display_name} unavailable: {type(exc).__name__}",
            }
        parsed["phase_id"] = definition.phase_id
        parsed["display_name"] = definition.display_name
        return definition.name, parsed

    def _build_gem_messages(self, definition: AgentDefinition, context: dict[str, Any]) -> tuple[str, str]:
        prompt_text = self.get_prompt_for_scout(definition.name)
        system = "\n".join(
            [
                prompt_text,
                "You are a backend-native trading review Gem, not an order executor.",
                "Use only the supplied JSON context. Do not claim external browsing or hidden broker access.",
                "The backend supplies data and executes only the allowed_actions listed in context.",
                "Return strictly valid JSON with keys: decision, confidence, reason_codes, risk_flags, report.",
                "decision must be PROCEED_TO_SIMULATION, REJECT, or HUMAN_REVIEW.",
                self._behavior_guidance(),
            ]
        )
        user_prompt = json.dumps(
            {
                "gem": {
                    "name": definition.name,
                    "display_name": definition.display_name,
                    "phase_id": definition.phase_id,
                },
                "review_context": context,
            },
            ensure_ascii=True,
            sort_keys=True,
            default=_json_default,
        )
        return system, user_prompt

    @staticmethod
    def _parse_gem_response(raw: str) -> dict[str, Any]:
        clean = (raw or "").replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        if not isinstance(data, dict):
            raise ValueError("Gem response was not a JSON object")
        decision = str(data.get("decision") or DecisionEnum.HUMAN_REVIEW.value).upper()
        if decision not in {item.value for item in DecisionEnum}:
            decision = DecisionEnum.HUMAN_REVIEW.value
        try:
            confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
        except (TypeError, ValueError):
            confidence = 0.5
        return {
            "decision": decision,
            "confidence": confidence,
            "reason_codes": GemNativeReviewService._string_list(data.get("reason_codes")),
            "risk_flags": GemNativeReviewService._string_list(data.get("risk_flags")),
            "report": str(data.get("report") or data.get("reasoning") or ""),
        }

    def _synthesize(
        self,
        payload: M8Payload,
        scout_reports: dict[str, dict[str, Any]],
        context: dict[str, Any],
    ) -> SignalReview:
        rows: dict[str, dict[str, Any]] = {}
        approval_score = 0.0
        rejection_score = 0.0
        human_score = 0.0
        total_weight = 0.0
        weighted_confidence = 0.0
        reason_codes: list[str] = []
        risk_flags: list[str] = []

        for name, report in scout_reports.items():
            decision = str(report.get("decision") or DecisionEnum.HUMAN_REVIEW.value).upper()
            confidence = max(0.0, min(1.0, float(report.get("confidence") or 0.5)))
            weight = confidence_registry.get_scout_weight(payload.symbol, name)
            score = weight * confidence
            if decision == DecisionEnum.REJECT.value:
                rejection_score += score
            elif decision == DecisionEnum.PROCEED_TO_SIMULATION.value:
                approval_score += score
            else:
                human_score += score
            total_weight += weight
            weighted_confidence += score
            reason_codes.extend(self._string_list(report.get("reason_codes")))
            risk_flags.extend(self._string_list(report.get("risk_flags")))
            rows[name] = {
                "decision": decision,
                "confidence": round(confidence, 4),
                "weight": round(weight, 4),
                "score": round(score, 4),
            }

        total_score = approval_score + rejection_score + human_score
        approval_ratio = approval_score / total_score if total_score else 0.0
        rejection_ratio = rejection_score / total_score if total_score else 0.0
        final_confidence = round(weighted_confidence / total_weight, 4) if total_weight else 0.5
        veto_names = {"risk_kernel", "payload_qa", "execution_watchdog"}
        vetoed = any(
            rows.get(name, {}).get("decision") == DecisionEnum.REJECT.value
            and float(rows.get(name, {}).get("confidence") or 0.0) >= 0.65
            for name in veto_names
        )

        if vetoed or rejection_ratio >= 0.45:
            decision = DecisionEnum.REJECT
            requires_human_review = True
            reject_reason = "Gem10 native review rejected the candidate"
            reason_codes.append("GEM10_REJECT")
        elif approval_ratio >= 0.62 and final_confidence >= 0.55:
            decision = DecisionEnum.PROCEED_TO_SIMULATION
            requires_human_review = False
            reject_reason = None
            reason_codes.append("GEM10_APPROVE")
        else:
            decision = DecisionEnum.HUMAN_REVIEW
            requires_human_review = True
            reject_reason = "Gem10 native review requires human review"
            reason_codes.append("GEM10_HUMAN_REVIEW")

        weighted_vote = {
            "approval_score": round(approval_score, 4),
            "rejection_score": round(rejection_score, 4),
            "human_review_score": round(human_score, 4),
            "approval_ratio": round(approval_ratio, 4),
            "rejection_ratio": round(rejection_ratio, 4),
            "weighted_confidence": final_confidence,
            "scouts": rows,
        }
        return SignalReview(
            schema_version="1.0",
            signal_id=payload.signal_id,
            decision=decision,
            confidence=final_confidence,
            reason_codes=self._unique(reason_codes),
            risk_flags=self._unique(risk_flags),
            reject_reason=reject_reason,
            requires_human_review=requires_human_review,
            audit_trace={
                "weighted_scout_vote": weighted_vote,
                "context_mode": context.get("mode"),
            },
        )

    def _synthesize_pipeline(
        self,
        *,
        mode: str,
        requested_mode: str,
        symbol: str | None,
        selected_phases: tuple[int, ...],
        selected_gems: tuple[str, ...],
        allowed_actions: tuple[str, ...],
        output_contract: str,
        gem_reports: dict[str, dict[str, Any]],
        backend_context: dict[str, Any],
        generated_prompts: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        approval_score = 0.0
        rejection_score = 0.0
        human_score = 0.0
        total_weight = 0.0
        weighted_confidence = 0.0
        reason_codes: list[str] = []
        risk_flags: list[str] = []
        report_lines: list[str] = []

        for name, report in gem_reports.items():
            decision = str(report.get("decision") or DecisionEnum.HUMAN_REVIEW.value).upper()
            confidence = max(0.0, min(1.0, float(report.get("confidence") or 0.5)))
            weight = confidence_registry.get_scout_weight(symbol, name) if symbol else 1.0
            score = weight * confidence
            if decision == DecisionEnum.REJECT.value:
                rejection_score += score
            elif decision == DecisionEnum.PROCEED_TO_SIMULATION.value:
                approval_score += score
            else:
                human_score += score
            total_weight += weight
            weighted_confidence += score
            reason_codes.extend(self._string_list(report.get("reason_codes")))
            risk_flags.extend(self._string_list(report.get("risk_flags")))
            if report.get("report"):
                report_lines.append(f"{name}: {report.get('report')}")

        total_score = approval_score + rejection_score + human_score
        approval_ratio = approval_score / total_score if total_score else 0.0
        rejection_ratio = rejection_score / total_score if total_score else 0.0
        final_confidence = round(weighted_confidence / total_weight, 4) if total_weight else 0.5

        if rejection_ratio >= 0.45 or any(
            str(report.get("decision") or "").upper() == DecisionEnum.REJECT.value
            and float(report.get("confidence") or 0.0) >= 0.8
            for report in gem_reports.values()
        ):
            decision = DecisionEnum.REJECT.value
            reason_codes.append("GEM_PIPELINE_REJECT")
        elif approval_ratio >= 0.62 and final_confidence >= 0.55:
            decision = DecisionEnum.PROCEED_TO_SIMULATION.value
            reason_codes.append("GEM_PIPELINE_APPROVE")
        else:
            decision = DecisionEnum.HUMAN_REVIEW.value
            reason_codes.append("GEM_PIPELINE_HUMAN_REVIEW")

        summary = " | ".join(report_lines[:6])
        if not summary:
            summary = f"Gem10 {mode} pipeline synthesized {len(gem_reports)} phase reports."

        return {
            "status": "ok",
            "engine": "gem10_native",
            "provider": self.provider or config.AI_PROVIDER,
            "requested_mode": requested_mode,
            "mode": mode,
            "selected_phases": list(selected_phases),
            "selected_gems": list(selected_gems),
            "allowed_actions": list(allowed_actions),
            "output_contract": output_contract,
            "used_llm": True,
            "decision": decision,
            "confidence": final_confidence,
            "reason_codes": self._unique(reason_codes),
            "risk_flags": self._unique(risk_flags),
            "summary": summary,
            "gem_reports": gem_reports,
            "backend_context": backend_context,
            "generated_prompts": generated_prompts,
        }

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value if item is not None]
        return [str(value)]

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value and value not in seen:
                result.append(value)
                seen.add(value)
        return result

    def _record_confidence(self, payload: M8Payload, scout_reports: dict[str, dict[str, Any]]) -> None:
        for name, report in scout_reports.items():
            confidence_registry.record_scout_review(
                    ScoutReviewParams(
                        symbol=payload.symbol,
                        scout_name=name,
                        direction=payload.direction,
                        decision=str(report.get("decision") or DecisionEnum.HUMAN_REVIEW.value),
                        confidence=float(report.get("confidence") or 0.5),
                        was_correct=None,
                    )
            )
        confidence_registry.record_signal_review(
            symbol=payload.symbol,
            confluence=payload.confluence_score,
            crisis=payload.crisis_score,
            direction=payload.direction,
        )

    def _record_pipeline_confidence(
        self,
        symbol: str | None,
        direction: str | None,
        gem_reports: dict[str, dict[str, Any]],
    ) -> None:
        if not symbol or not direction:
            return
        for name, report in gem_reports.items():
            confidence_registry.record_scout_review(
                    ScoutReviewParams(
                        symbol=symbol,
                        scout_name=name,
                        direction=direction,
                        decision=str(report.get("decision") or DecisionEnum.HUMAN_REVIEW.value),
                        confidence=float(report.get("confidence") or 0.5),
                        was_correct=None,
                    )
            )

    def _fatal_fallback(self, payload: M8Payload, exc: Exception) -> SignalReview:
        scout_reports = {
            definition.name: {
                "decision": DecisionEnum.HUMAN_REVIEW.value,
                "confidence": 0.5,
                "reason_codes": ["GEM10_FATAL_FALLBACK"],
                "risk_flags": [self._provider_unavailable_flag()],
                "report": f"{definition.display_name} skipped after fatal Gem10 error: {type(exc).__name__}",
                "phase_id": definition.phase_id,
                "display_name": definition.display_name,
            }
            for definition in GEM_AGENT_DEFINITIONS
        }
        return SignalReview(
            schema_version="1.0",
            signal_id=payload.signal_id,
            decision=DecisionEnum.HUMAN_REVIEW,
            confidence=0.5,
            reason_codes=["GEM10_FATAL_FALLBACK"],
            risk_flags=[self._provider_unavailable_flag()],
            reject_reason="Gem10 native review failed before synthesis",
            requires_human_review=True,
            audit_trace={
                **self._trace_base(),
                "engine": "gem10_native",
                "fallback": True,
                "error_type": type(exc).__name__,
                "scouts": scout_reports,
                "confidence_recorded": False,
            },
        )
