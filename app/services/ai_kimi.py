import json
import asyncio
from dataclasses import dataclass
from openai import AsyncOpenAI
from typing import Any

from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import SignalReview, DecisionEnum
from app.core.config import (
    AI_PROVIDER,
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
    MOONSHOT_API_KEY,
    MOONSHOT_BASE_URL,
    MOONSHOT_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
)
from app.services.ai_layer_memory import ai_layer_memory_instance


@dataclass(frozen=True)
class AIProviderConfig:
    provider: str
    api_key: str
    api_key_env: str
    base_url: str
    model: str
    unavailable_flag: str


def get_ai_provider_config(provider: str | None = None) -> AIProviderConfig:
    selected = (provider or AI_PROVIDER or "moonshot").strip().lower()

    if selected in {"moonshot", "kimi", "kimi-k2.6"}:
        return AIProviderConfig(
            provider="moonshot",
            api_key=MOONSHOT_API_KEY,
            api_key_env="MOONSHOT_API_KEY",
            base_url=MOONSHOT_BASE_URL,
            model=MOONSHOT_MODEL,
            unavailable_flag="KIMI_UNAVAILABLE",
        )

    if selected in {"openai", "chatgpt", "gpt"}:
        return AIProviderConfig(
            provider="openai",
            api_key=OPENAI_API_KEY,
            api_key_env="OPENAI_API_KEY",
            base_url=OPENAI_BASE_URL,
            model=OPENAI_MODEL,
            unavailable_flag="OPENAI_UNAVAILABLE",
        )

    if selected in {"gemini", "google", "google-gemini"}:
        return AIProviderConfig(
            provider="gemini",
            api_key=GEMINI_API_KEY,
            api_key_env="GEMINI_API_KEY",
            base_url=GEMINI_BASE_URL,
            model=GEMINI_MODEL,
            unavailable_flag="GEMINI_UNAVAILABLE",
        )

    raise ValueError(
        f"Unsupported AI_PROVIDER '{selected}'. Use one of: moonshot, openai, gemini."
    )

class KimiSwarmService:
    """
    Implements a multi-agent review swarm using the configured LLM provider.
    It fires multiple scout agents concurrently and synthesizes their results into a strict Pydantic JSON structure.
    """
    def __init__(self, provider: str | None = None) -> None:
        self.provider = provider

    def _provider_unavailable_flag(self) -> str:
        try:
            return get_ai_provider_config(self.provider).unavailable_flag
        except Exception:
            return "AI_PROVIDER_UNAVAILABLE"

    def _behavior_guidance(self) -> str:
        return ai_layer_memory_instance.behavior_prompt()

    def _trace_base(self) -> dict[str, Any]:
        return {
            "trace_type": "ai_reasoning_audit_not_hidden_chain_of_thought",
            "provider": self.provider or AI_PROVIDER,
            "behavior_profile": ai_layer_memory_instance.get_profile().model_dump(),
            "behavior_prompt": self._behavior_guidance(),
        }
    
    async def review_signal(self, payload: M8Payload) -> SignalReview:
        try:
            # Gather scout reviews concurrently
            sentiment_task = self._run_sentiment_scout(payload)
            technical_task = self._run_technical_scout(payload)
            risk_task = self._run_risk_scout(payload)
            
            sentiment_analysis, technical_analysis, risk_analysis = await asyncio.gather(
                sentiment_task, technical_task, risk_task
            )
            
            # Orchestrator synthesizes the responses
            review = await self._run_orchestrator(payload, sentiment_analysis, technical_analysis, risk_analysis)
            review.audit_trace = {
                **self._trace_base(),
                "scouts": {
                    "sentiment": sentiment_analysis,
                    "technical": technical_analysis,
                    "risk": risk_analysis,
                },
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
            
        except Exception as e:
            print(f"AI provider error ({self.provider or AI_PROVIDER}): {e}")
            # Fallback pattern if API fails: proceed to deterministic risk engine but log warning
            return SignalReview(
                schema_version="1.0",
                signal_id=payload.signal_id,
                decision=DecisionEnum.PROCEED_TO_SIMULATION,
                confidence=0.5,
                reason_codes=["API_FALLBACK"],
                risk_flags=[self._provider_unavailable_flag()],
                reject_reason=None,
                requires_human_review=False,
                audit_trace={
                    **self._trace_base(),
                    "fallback": True,
                    "error_type": type(e).__name__,
                    "final_summary": {
                        "decision": DecisionEnum.PROCEED_TO_SIMULATION.value,
                        "confidence": 0.5,
                        "reason_codes": ["API_FALLBACK"],
                        "risk_flags": [self._provider_unavailable_flag()],
                    },
                },
            )

    async def _run_sentiment_scout(self, payload: M8Payload) -> str:
        prompt = f"Analyze sentiment for {payload.symbol} at {payload.timestamp}. Is there any macro news?"
        return await self._call_kimi(
            prompt,
            system=f"You are a market sentiment expert. Keep it brief.\n\n{self._behavior_guidance()}",
        )

    async def _run_technical_scout(self, payload: M8Payload) -> str:
        prompt = f"Review technicals: Direction: {payload.direction}, Confluence: {payload.confluence_score}, Dispersion: {payload.mc_dispersion}."
        return await self._call_kimi(
            prompt,
            system=f"You are a quant technical analyst. Assess setup quality.\n\n{self._behavior_guidance()}",
        )

    async def _run_risk_scout(self, payload: M8Payload) -> str:
        prompt = f"Assess risk: Crisis Score is {payload.crisis_score}. Spread is {payload.spread}."
        return await self._call_kimi(
            prompt,
            system=f"You are a risk manager. Flag any anomalies.\n\n{self._behavior_guidance()}",
        )

    async def _run_orchestrator(self, payload: M8Payload, sentiment: str, tech: str, risk: str) -> SignalReview:
        schema_format = """
        {
          "schema_version": "1.0",
          "signal_id": "string",
          "decision": "PROCEED_TO_SIMULATION" | "REJECT" | "HUMAN_REVIEW",
          "confidence": number between 0 and 1,
          "reason_codes": [ "string" ],
          "risk_flags": [ "string" ],
          "reject_reason": "string" or null,
          "requires_human_review": boolean
        }
        """
        
        prompt = f"""
        Signal ID: {payload.signal_id}
        
        Scout Reports:
        Sentiment: {sentiment}
        Technical: {tech}
        Risk: {risk}
        
        Based on these reports, produce a final JSON decision strictly matching this schema:
        {schema_format}
        """
        
        json_output = await self._call_kimi(
            prompt, 
            system=(
                "You are the lead trading orchestrator. You MUST return strictly valid JSON. "
                "Do not include markdown code blocks.\n\n"
                f"{self._behavior_guidance()}"
            ),
            response_format={"type": "json_object"}
        )
        
        try:
            # Remove possible markdown wrappers if they leaked through
            clean_json = json_output.replace('```json', '').replace('```', '').strip()
            data = json.loads(clean_json)
            # Add signal_id if it got missed by LLM
            data['signal_id'] = payload.signal_id
            data['schema_version'] = "1.0"
            return SignalReview(**data)
        except Exception as e:
            print(f"Failed to parse JSON from AI provider: {e}")
            raise e

    async def _call_kimi(self, prompt: str, system: str = "You are a helpful assistant", response_format: Any = None) -> str:
        return await self._call_llm(prompt, system=system, response_format=response_format)

    async def _call_llm(self, prompt: str, system: str = "You are a helpful assistant", response_format: Any = None) -> str:
        provider_config = get_ai_provider_config(self.provider)

        if not provider_config.api_key:
            raise RuntimeError(f"{provider_config.api_key_env} is not configured")

        client = AsyncOpenAI(
            api_key=provider_config.api_key,
            base_url=provider_config.base_url
        )

        kwargs = {
            "model": provider_config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ]
        }
        
        # Some OpenAI-compatible providers reject response_format; retry below keeps the pipeline available.
        if response_format:
            kwargs["response_format"] = response_format
            
        try:
            response = await client.chat.completions.create(**kwargs)
        except Exception as e:
            if response_format and self._should_retry_without_response_format(e):
                kwargs.pop("response_format", None)
                response = await client.chat.completions.create(**kwargs)
            else:
                raise

        return response.choices[0].message.content

    @staticmethod
    def _should_retry_without_response_format(error: Exception) -> bool:
        message = str(error).lower()
        return "response_format" in message and (
            "unsupported" in message
            or "not support" in message
            or "invalid" in message
            or "unknown field" in message
        )

if AI_PROVIDER in {"mock", "offline", "none"}:
    from app.services.ai_mock import MockAIReviewLayer

    ai_review_instance = MockAIReviewLayer()
else:
    ai_review_instance = KimiSwarmService(provider=AI_PROVIDER)
