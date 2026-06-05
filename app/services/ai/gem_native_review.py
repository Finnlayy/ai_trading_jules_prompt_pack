from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import SignalReview, DecisionEnum
from app.core import config
from app.services.ai_layer_memory import ai_layer_memory_instance
from app.services.confidence_registry import confidence_registry
import json
import asyncio
from pathlib import Path

class GemNativeReviewService:
    SCOUT_NAMES = [
        "macro_sentinel",
        "market_dna",
        "structural_architect",
        "harmony_coordinator",
        "indicator_fusion",
        "risk_kernel",
        "pine_core",
        "payload_qa",
        "execution_watchdog",
        "evolution_optimizer"
    ]

    def __init__(self, provider: str = None):
        self.provider = provider
        self.prompts_dir = Path("app/ai_prompts")

    def _get_gem_prompt(self, gem_name: str) -> str:
        prompt_path = self.prompts_dir / gem_name / "v_active.md"
        if prompt_path.exists():
            return prompt_path.read_text()
        return f"You are the {gem_name}."

    def _trace_base(self) -> dict:
        return {
            "trace_type": "ai_reasoning_audit_not_hidden_chain_of_thought",
            "provider": self.provider or config.AI_PROVIDER,
            "behavior_profile": ai_layer_memory_instance.get_profile().model_dump()
        }

    async def _mock_llm_call(self, prompt: str) -> str:
        return json.dumps({
            "decision": DecisionEnum.PROCEED_TO_SIMULATION.value,
            "confidence": 0.85,
            "reasoning": "Mocked LLM reasoning for prompt.",
            "reason_codes": [],
            "risk_flags": [],
            "requires_human_review": False
        })

    async def review_signal(self, payload: M8Payload) -> SignalReview:
        symbol_context = confidence_registry.get_symbol_context(
            payload.symbol, payload.direction
        )

        # Build context
        context_data = {
            "symbol": payload.symbol,
            "direction": payload.direction,
            "timeframe": payload.timeframe,
            "entry_price": payload.entry_price,
            "stop_price": payload.stop_price,
            "target_price": payload.target_price,
            "confluence": payload.confluence_score,
            "crisis": payload.crisis_score,
            "regime": payload.market_regime
        }

        # Concurrently gather gem reviews
        async def fetch_gem_review(gem_name):
            prompt = self._get_gem_prompt(gem_name)
            full_prompt = f"{prompt}\nContext: {json.dumps(context_data)}\nSymbol Context: {symbol_context}"
            res_str = await self._mock_llm_call(full_prompt)
            res = json.loads(res_str)
            return gem_name, res

        gem_results = await asyncio.gather(*[fetch_gem_review(name) for name in self.SCOUT_NAMES])

        scout_reports = {}
        for name, res in gem_results:
            scout_reports[name] = {
                "report": res.get("reasoning", "MOCK"),
                "decision": res.get("decision", DecisionEnum.PROCEED_TO_SIMULATION.value),
                "confidence": res.get("confidence", 0.5)
            }

        # Basic Orchestrator logic
        approvals = sum(1 for r in scout_reports.values() if r["decision"] == DecisionEnum.PROCEED_TO_SIMULATION.value)
        rejections = len(self.SCOUT_NAMES) - approvals

        decision = DecisionEnum.PROCEED_TO_SIMULATION if approvals >= rejections else DecisionEnum.REJECT
        confidence = sum(r["confidence"] for r in scout_reports.values()) / len(self.SCOUT_NAMES)

        audit_trace = {
            **self._trace_base(),
            "scouts": scout_reports,
            "symbol_context": symbol_context,
            "scout_weights": {name: 1.0 for name in self.SCOUT_NAMES},
            "weighted_scout_vote": confidence
        }

        return SignalReview(
            schema_version="1.0",
            signal_id=payload.signal_id,
            decision=decision,
            confidence=confidence,
            reason_codes=["MOCKED_GEM_REASONS"],
            risk_flags=[],
            requires_human_review=False,
            audit_trace=audit_trace
        )
