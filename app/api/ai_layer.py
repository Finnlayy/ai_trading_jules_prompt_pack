from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.core.config import AI_PROVIDER
from app.schemas.ai_layer import AIBehaviorProfile, AIChatRequest, AIChatResponse
from app.schemas.gem_pipeline import GemPipelineRequest, GemPipelineResponse
from app.services.ai.gem_native_review import GemNativeReviewService
from app.services.ai_kimi import KimiSwarmService
from app.services.ai_layer_memory import ai_layer_memory_instance

logger = logging.getLogger(__name__)

router = APIRouter()

AI_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "ai_prompts"

DEFAULT_CHAT_SYSTEM_PROMPT = (
    "Prompt file unavailable. Act as a safe AI behavior profile assistant and return JSON with "
    "reply and profile_patch only; never bypass risk gates or place trades."
)


def _extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _local_profile_patch(message: str) -> dict[str, Any]:
    lower = message.lower()
    patch: dict[str, Any] = {}

    if any(word in lower for word in ("conservative", "vorsichtig", "weniger risiko", "lower risk")):
        patch["risk_tolerance"] = "conservative"
        patch["trading_style"] = "capital_preservation"
    elif any(word in lower for word in ("aggressive", "mehr risiko", "scalp", "scalping")):
        patch["risk_tolerance"] = "aggressive"
        patch["trading_style"] = "opportunistic"

    if "human review" in lower or "manual review" in lower or "mensch" in lower:
        patch["guardrails"] = [
            *ai_layer_memory_instance.get_profile().guardrails,
            "Escalate uncertain setups to human review.",
        ]

    if "confluence" in lower:
        numbers = [float(token) for token in lower.replace(",", " ").split() if token.replace(".", "", 1).isdigit()]
        if numbers:
            patch["min_confluence_preference"] = max(0.0, min(100.0, numbers[-1]))

    return patch


def _local_recommended_action(message: str) -> dict[str, Any] | None:
    lower = message.lower()

    # 1. toggle_emergency (check first to avoid collision with stop_training)
    if "emergency" in lower:
        active = True
        if any(word in lower for word in ("disable", "off", "false", "lift", "stop emergency")):
            active = False
        return {
            "action": "toggle_emergency",
            "params": {"active": active}
        }

    # 2. run_backtest
    if "backtest" in lower:
        symbol = "HYPEUSDT"  # Default
        for token in message.split():
            clean_token = token.strip(".,!?\"'()").upper()
            if "USDT" in clean_token:
                symbol = clean_token
                break

        bars = 500
        for token in lower.replace("bars", "").split():
            if token.isdigit():
                val = int(token)
                if 10 <= val <= 10000:
                    bars = val
                    break

        return {
            "action": "run_backtest",
            "params": {
                "symbol": symbol,
                "bars": bars,
            }
        }

    # 3. trigger_drill
    if "drill" in lower and any(word in lower for word in ("trigger", "start", "run")):
        scout_name = None
        for scout in ("technical", "sentiment", "risk", "macro", "execution", "correlation"):
            if scout in lower:
                scout_name = scout
                break
        params = {}
        if scout_name:
            params["scout_name"] = scout_name
        return {
            "action": "trigger_drill",
            "params": params
        }

    # 4. start_training
    if "start" in lower and ("training" in lower or "loop" in lower):
        return {
            "action": "start_training",
            "params": {}
        }

    # 5. stop_training
    if any(word in lower for word in ("stop", "pause", "halt")) and ("training" in lower or "loop" in lower):
        return {
            "action": "stop_training",
            "params": {}
        }

    # 6. reset_memory
    if "reset memory" in lower or "clear memory" in lower or "reset chat" in lower:
        return {
            "action": "reset_memory",
            "params": {}
        }

    return None


async def _execute_action(action: str, params: dict[str, Any]) -> str:
    """Execute the recommended action on the user's behalf and return feedback."""
    if action == "run_backtest":
        try:
            from app.api.backtest_runner import run_backtest, BacktestRunRequest
            req = BacktestRunRequest(
                symbol=params.get("symbol", "HYPEUSDT"),
                bars=params.get("bars", 500),
                max_signals=params.get("max_signals", 50),
                min_confluence=params.get("min_confluence")
            )
            res = await run_backtest(req)
            if res.get("signals_generated", 0) == 0:
                return f"[Action Executed: run_backtest] Completed. No signals generated for {req.symbol}."
            return (
                f"[Action Executed: run_backtest] Completed for {req.symbol}. "
                f"Generated: {res.get('signals_generated')}, Executed SIM: {res.get('executed')}, Rejected: {res.get('rejected')}."
            )
        except Exception as exc:
            return f"[Action Failed: run_backtest] Error: {exc}"

    elif action == "trigger_drill":
        try:
            from app.services.training_loop import training_loop
            await training_loop.trigger_manual_cycle()
            return "[Action Executed: trigger_drill] Drill cycle triggered successfully."
        except Exception as exc:
            return f"[Action Failed: trigger_drill] Error: {exc}"

    elif action == "start_training":
        try:
            from app.services.training_loop import training_loop
            res = await training_loop.start()
            if res.get("started"):
                return "[Action Executed: start_training] Academy training loop started."
            return f"[Action Executed: start_training] Loop not started: {res.get('reason')}."
        except Exception as exc:
            return f"[Action Failed: start_training] Error: {exc}"

    elif action == "stop_training":
        try:
            from app.services.training_loop import training_loop
            await training_loop.stop()
            return "[Action Executed: stop_training] Academy training loop stopped."
        except Exception as exc:
            return f"[Action Failed: stop_training] Error: {exc}"

    elif action == "reset_memory":
        try:
            ai_layer_memory_instance.reset()
            return "[Action Executed: reset_memory] AI layer memory and behavior profile reset."
        except Exception as exc:
            return f"[Action Failed: reset_memory] Error: {exc}"

    elif action == "toggle_emergency":
        try:
            active = params.get("active", True)
            import app.api.live_trading as live_trading
            from app.services.autonomous_loop import autonomous_loop_instance
            from app.services.dashboard_sse import dashboard_sse_manager
            from datetime import datetime, timezone, timedelta

            if active:
                halted_until = datetime.now(timezone.utc) + timedelta(minutes=1440)
                live_trading._emergency_halt_until = halted_until
                autonomous_loop_instance.pause()
                dashboard_sse_manager.broadcast_alert(
                    "🚨 EMERGENCY STOP: Activated via AI Chat", level="critical"
                )
                return "[Action Executed: toggle_emergency] Emergency halt activated (24h)."
            else:
                live_trading._emergency_halt_until = None
                dashboard_sse_manager.broadcast_alert(
                    "🚨 EMERGENCY STOP: Deactivated via AI Chat", level="info"
                )
                return "[Action Executed: toggle_emergency] Emergency halt deactivated."
        except Exception as exc:
            return f"[Action Failed: toggle_emergency] Error: {exc}"

    return f"[Action Ignored] Unknown or unauthorized action: {action}"


def _resolve_active_prompt(prompt_name: str, default: str) -> str:
    prompt_path = AI_PROMPTS_DIR / prompt_name / "v_active.md"
    if not prompt_path.exists():
        return default

    active_text = prompt_path.read_text(encoding="utf-8").strip()
    if active_text and "\n" not in active_text and active_text.endswith(".md"):
        candidate = (prompt_path.parent / active_text).resolve()
        try:
            candidate.relative_to(prompt_path.parent.resolve())
        except ValueError:
            return active_text
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    return active_text or default


def _chat_system_prompt() -> str:
    return _resolve_active_prompt("chat", DEFAULT_CHAT_SYSTEM_PROMPT)


def _build_prompt(request: AIChatRequest) -> tuple[str, str]:
    """Build the system prompt and user prompt dict for the AI chat."""
    profile = ai_layer_memory_instance.get_profile()
    memory = ai_layer_memory_instance.get_memory()

    system = _chat_system_prompt()

    prompt: dict[str, Any] = {
        "current_profile": profile.model_dump(),
        "recent_memory": [message.model_dump() for message in memory[-12:]],
        "user_message": request.message,
        "allowed_profile_fields": list(AIBehaviorProfile.model_fields.keys()),
    }

    chart_context = request.chart_context
    if chart_context:
        # Respect bars_count by slicing recent_candles if present
        recent_candles = chart_context.get("recent_candles") or []
        if recent_candles and request.bars_count:
            chart_context = {**chart_context, "recent_candles": recent_candles[-request.bars_count:]}
        prompt["chart_context"] = chart_context
        system += (
            " When chart_context is provided, analyze the actual price action and indicators. "
            "Base your guidance on market structure, trend, volatility, and confluence scores. "
            "Do not hallucinate levels; reference the data explicitly."
        )

    if request.strategy_context:
        prompt["mounted_strategy"] = request.strategy_context
        system += (
            f" The user has mounted the strategy '{request.strategy_context}'. "
            "Factor this strategy's logic into your analysis when relevant."
        )

    return system, json.dumps(prompt, indent=2)


@router.get("/profile")
async def get_ai_profile():
    return {
        "status": "ok",
        "provider": AI_PROVIDER,
        "profile": ai_layer_memory_instance.get_profile(),
        "memory": ai_layer_memory_instance.get_memory(),
        "behavior_prompt": ai_layer_memory_instance.behavior_prompt(),
    }


@router.post("/profile")
async def update_ai_profile(profile: AIBehaviorProfile):
    updated = ai_layer_memory_instance.update_profile(profile.model_dump())
    ai_layer_memory_instance.append_message("system", "AI behavior profile updated from dashboard controls.")
    return {"status": "ok", "provider": AI_PROVIDER, "profile": updated}


@router.post("/chat", response_model=AIChatResponse)
async def chat_with_ai_layer(request: AIChatRequest):
    ai_layer_memory_instance.append_message("user", request.message)
    profile = ai_layer_memory_instance.get_profile()

    system, user_prompt = _build_prompt(request)

    if request.return_prompt_only:
        return AIChatResponse(
            reply="",
            provider=AI_PROVIDER,
            used_llm=False,
            profile=profile,
            memory=ai_layer_memory_instance.get_memory(),
            raw_profile_patch={},
            generated_prompt=user_prompt,
            system_prompt=system,
        )

    used_llm = False
    reply = ""
    patch: dict[str, Any] = {}
    recommended_action: dict[str, Any] | None = None

    try:
        if AI_PROVIDER not in {"mock", "offline", "none"}:
            service = KimiSwarmService(provider=AI_PROVIDER)
            raw = await service._call_llm(
                user_prompt,
                system=system,
                response_format={"type": "json_object"},
            )
            parsed = _extract_json_object(raw)
            reply = str(parsed.get("reply") or "").strip()
            raw_patch = parsed.get("profile_patch", {})
            patch = raw_patch if isinstance(raw_patch, dict) else {}
            
            raw_action = parsed.get("recommended_action")
            if isinstance(raw_action, dict) and "action" in raw_action:
                recommended_action = raw_action

            used_llm = True
    except Exception as exc:
        logger.info("AI layer chat fell back to local parser: %s", exc)

    if not reply:
        patch = _local_profile_patch(request.message)
        reply = (
            "I captured that as AI-layer behavior guidance. "
            "It will influence review confidence, reason codes, and human-review escalation, "
            "while deterministic risk gates remain the final authority."
        )

    if not recommended_action:
        recommended_action = _local_recommended_action(request.message)

    if recommended_action:
        action_name = recommended_action.get("action")
        action_params = recommended_action.get("params") or {}
        feedback = await _execute_action(action_name, action_params)
        if feedback:
            reply = f"{reply}\n\n{feedback}"

    if request.apply_to_profile and patch:
        profile = ai_layer_memory_instance.update_profile(patch)

    ai_layer_memory_instance.append_message("assistant", reply)

    return AIChatResponse(
        reply=reply,
        provider=AI_PROVIDER,
        used_llm=used_llm,
        profile=profile,
        memory=ai_layer_memory_instance.get_memory(),
        raw_profile_patch=patch,
        recommended_action=recommended_action,
        generated_prompt=user_prompt,
        system_prompt=system,
    )


@router.post("/gems/review", response_model=GemPipelineResponse)
async def review_with_gem_pipeline(request: GemPipelineRequest):
    service = GemNativeReviewService(provider=AI_PROVIDER)
    result = await service.review_pipeline(
        mode=request.mode,
        context=request.context,
        symbol=request.symbol,
        direction=request.direction,
        output_contract=request.output_contract,
        return_prompt_only=request.return_prompt_only,
    )
    return GemPipelineResponse(**result)


@router.post("/reset")
async def reset_ai_layer_memory():
    state = ai_layer_memory_instance.reset()
    return {"status": "reset", "provider": AI_PROVIDER, **state}


@router.get("/strategies")
async def list_strategies():
    """List available Pine Script and Python strategies in the scripts directory."""
    strategies = []
    base = Path(__file__).resolve().parents[2] / "app" / "scripts"

    pine_dir = base / "generated_pines"
    if pine_dir.exists():
        for f in sorted(pine_dir.glob("*.pine")):
            strategies.append({"name": f.stem, "type": "pine", "path": str(f)})

    for f in sorted(base.glob("*.py")):
        strategies.append({"name": f.stem, "type": "python", "path": str(f)})

    return {"strategies": strategies}
