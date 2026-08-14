from __future__ import annotations

import json

import pytest

from app.schemas.ai_review import DecisionEnum
from app.schemas.m8_payload import M8Payload
from app.services.ai.gem_agents import GEM_AGENT_NAMES
from app.services.ai.gem_pipeline import (
    BACKTEST_AREA,
    LIVE_TRADE_EVALUATION,
    PIONEX_DEPLOYMENT,
    STRATEGY_REVIEW,
    GemInputRouter,
)
from app.services.ai.gem_native_review import GemNativeReviewService
from app.services.ai_factory import get_ai_review_instance
from app.services.confidence_registry import confidence_registry


def _payload() -> M8Payload:
    return M8Payload(
        signal_id="gem10-BTCUSDT-1m-default-1700000000000",
        symbol="BTCUSDT",
        timeframe="1m",
        direction="LONG",
        timestamp="2026-05-20T10:00:00Z",
        entry_price=100.0,
        stop_price=98.0,
        target_price=104.0,
        confluence_score=84.0,
        crisis_score=8.0,
        mc_dispersion=1.2,
        spread=2.0,
        strategy_id="default",
    )


@pytest.fixture(autouse=True)
def reset_confidence_registry():
    confidence_registry.reset_all()
    yield
    confidence_registry.reset_all()


def test_ai_factory_uses_legacy_by_default():
    from app.services.ai_kimi import ai_review_instance as legacy_instance

    assert get_ai_review_instance(provider="moonshot", engine="legacy6") is legacy_instance


def test_ai_factory_can_create_gem10_native():
    instance = get_ai_review_instance(provider="moonshot", engine="gem10_native")

    assert isinstance(instance, GemNativeReviewService)
    assert instance.SCOUT_NAMES == list(GEM_AGENT_NAMES)


def test_gem_input_router_selects_plan3_phase_sets():
    router = GemInputRouter()

    assert [item.phase_id for item in router.definitions_for_mode(LIVE_TRADE_EVALUATION)] == [
        1,
        2,
        3,
        4,
        5,
        6,
        8,
        9,
    ]
    assert [item.phase_id for item in router.definitions_for_mode(STRATEGY_REVIEW)] == [
        1,
        2,
        3,
        4,
        5,
        6,
        7,
    ]
    assert [item.name for item in router.definitions_for_mode(PIONEX_DEPLOYMENT)] == [
        "pine_core",
        "payload_qa",
    ]
    assert [item.phase_id for item in router.definitions_for_mode(BACKTEST_AREA)] == [
        2,
        3,
        4,
        5,
        6,
        10,
    ]
    assert router.resolve_mode("auto", {"pionex_payload": {}}) == PIONEX_DEPLOYMENT
    assert router.resolve_mode("auto", {"m8_payload": {}}) == LIVE_TRADE_EVALUATION


def test_gem10_parser_accepts_string_reason_fields():
    parsed = GemNativeReviewService._parse_gem_response(
        json.dumps(
            {
                "decision": "PROCEED_TO_SIMULATION",
                "confidence": "0.8",
                "reason_codes": "SINGLE_REASON",
                "risk_flags": "SINGLE_FLAG",
                "report": "ok",
            }
        )
    )

    assert parsed["reason_codes"] == ["SINGLE_REASON"]
    assert parsed["risk_flags"] == ["SINGLE_FLAG"]


@pytest.mark.asyncio
async def test_gem10_native_review_records_live_trade_phase_gems(monkeypatch):
    service = GemNativeReviewService(provider="moonshot")
    expected_names = [item.name for item in service.input_router.definitions_for_mode(LIVE_TRADE_EVALUATION)]

    async def fake_call(scout_name: str, prompt: str, system: str = "", response_format=None):
        assert response_format == {"type": "json_object"}
        assert scout_name in expected_names
        assert "review_context" in prompt
        return json.dumps(
            {
                "decision": "PROCEED_TO_SIMULATION",
                "confidence": 0.82,
                "reason_codes": [f"{scout_name.upper()}_OK"],
                "risk_flags": [],
                "report": f"{scout_name} approves supplied backend context.",
            }
        )

    monkeypatch.setattr(service, "_call_llm_for_scout", fake_call)

    review = await service.review_signal(_payload())

    assert review.decision == DecisionEnum.PROCEED_TO_SIMULATION
    assert review.audit_trace["engine"] == "gem10_native"
    assert review.audit_trace["mode"] == LIVE_TRADE_EVALUATION
    assert review.audit_trace["selected_phases"] == [1, 2, 3, 4, 5, 6, 8, 9]
    assert set(review.audit_trace["scouts"].keys()) == set(expected_names)
    assert review.audit_trace["confidence_recorded"] is True

    stats = confidence_registry.get_symbol_stats("BTCUSDT")
    for gem_name in expected_names:
        assert stats.scout_stats[gem_name].calls == 1


@pytest.mark.asyncio
async def test_gem10_native_risk_veto_rejects(monkeypatch):
    service = GemNativeReviewService(provider="moonshot")

    async def fake_call(scout_name: str, prompt: str, system: str = "", response_format=None):
        decision = "REJECT" if scout_name == "risk_kernel" else "PROCEED_TO_SIMULATION"
        confidence = 0.9 if scout_name == "risk_kernel" else 0.7
        return json.dumps(
            {
                "decision": decision,
                "confidence": confidence,
                "reason_codes": [f"{scout_name.upper()}_{decision}"],
                "risk_flags": ["RISK_KERNEL_VETO"] if scout_name == "risk_kernel" else [],
                "report": f"{scout_name} decision: {decision}",
            }
        )

    monkeypatch.setattr(service, "_call_llm_for_scout", fake_call)

    review = await service.review_signal(_payload())

    assert review.decision == DecisionEnum.REJECT
    assert review.requires_human_review is True
    assert "GEM10_REJECT" in review.reason_codes
    assert "RISK_KERNEL_VETO" in review.risk_flags


@pytest.mark.asyncio
async def test_gem10_native_provider_failure_stays_structured(monkeypatch):
    service = GemNativeReviewService(provider="moonshot")
    expected_names = [item.name for item in service.input_router.definitions_for_mode(LIVE_TRADE_EVALUATION)]

    async def fake_fail(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(service, "_call_llm_for_scout", fake_fail)

    review = await service.review_signal(_payload())

    assert review.decision == DecisionEnum.HUMAN_REVIEW
    assert set(review.audit_trace["scouts"].keys()) == set(expected_names)
    assert review.audit_trace["engine"] == "gem10_native"


@pytest.mark.asyncio
async def test_gem_pipeline_prompt_only_redacts_secrets_and_selects_pionex_phases():
    service = GemNativeReviewService(provider="moonshot")

    result = await service.review_pipeline(
        mode=PIONEX_DEPLOYMENT,
        context={
            "pionex_payload": {"signal_type": "uuid"},
            "api_key": "should-not-leak",
            "nested": {"api_secret": "also-hidden"},
        },
        symbol="BTCUSDT",
        direction="LONG",
        return_prompt_only=True,
    )

    assert result["used_llm"] is False
    assert result["selected_phases"] == [7, 8]
    assert result["selected_gems"] == ["pine_core", "payload_qa"]
    assert result["backend_context"]["input"]["api_key"] == "[REDACTED]"
    assert result["backend_context"]["input"]["nested"]["api_secret"] == "[REDACTED]"
    assert set(result["generated_prompts"].keys()) == {"pine_core", "payload_qa"}


@pytest.mark.asyncio
async def test_gem_pipeline_runs_selected_backtest_phases(monkeypatch):
    service = GemNativeReviewService(provider="moonshot")

    async def fake_call(scout_name: str, prompt: str, system: str = "", response_format=None):
        return json.dumps(
            {
                "decision": "PROCEED_TO_SIMULATION",
                "confidence": 0.75,
                "reason_codes": [f"{scout_name.upper()}_BACKTEST_OK"],
                "risk_flags": [],
                "report": f"{scout_name} accepted backtest context.",
            }
        )

    monkeypatch.setattr(service, "_call_llm_for_scout", fake_call)

    result = await service.review_pipeline(
        mode=BACKTEST_AREA,
        context={"backtest": {"trades": 12, "net_pnl": 4.2}},
        symbol="BTCUSDT",
        direction="LONG",
    )

    assert result["used_llm"] is True
    assert result["mode"] == BACKTEST_AREA
    assert result["selected_phases"] == [2, 3, 4, 5, 6, 10]
    assert set(result["gem_reports"].keys()) == {
        "market_dna",
        "structural_architect",
        "harmony_coordinator",
        "indicator_fusion",
        "risk_kernel",
        "evolution_optimizer",
    }
    assert result["decision"] == DecisionEnum.PROCEED_TO_SIMULATION.value
