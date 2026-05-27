from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.core.config import AI_PROVIDER
from app.schemas.ai_layer import AIBehaviorProfile, AIChatRequest, AIChatResponse
from app.services.ai_kimi import KimiSwarmService
from app.services.ai_layer_memory import ai_layer_memory_instance

logger = logging.getLogger(__name__)

router = APIRouter()


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


def _build_prompt(request: AIChatRequest) -> tuple[str, str]:
    """Build the system prompt and user prompt dict for the AI chat."""
    profile = ai_layer_memory_instance.get_profile()
    memory = ai_layer_memory_instance.get_memory()

    system = (
        "You are the configuration assistant for a multi-agent trading bot AI layer. "
        "Help the user translate behavior preferences into review-layer guidance. "
        "Never claim to train a model, never bypass deterministic risk gates, and never place trades. "
        "Return concise JSON with keys reply and profile_patch. profile_patch may contain only fields "
        "from AIBehaviorProfile."
    )

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
        generated_prompt=user_prompt,
        system_prompt=system,
    )


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
