import json
import asyncio
import google.generativeai as genai
from typing import Dict, Any

from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import SignalReview, DecisionEnum
from app.core.config import GEMINI_API_KEY, GEMINI_MODEL

# Configure the Gemini client
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    # Dummy config for tests
    genai.configure(api_key="dummy_gemini_key")

class GeminiSwarmService:
    """
    Implements a multi-agent swarm using Google's Gemini Pro model to review the signal payload.
    It fires multiple scout agents concurrently and synthesizes their results into a strict Pydantic JSON structure.
    """

    async def review_signal(self, payload: M8Payload) -> SignalReview:
        try:
            # Gather scout reviews concurrently
            sentiment_task = self._run_sentiment_scout(payload)
            technical_task = self._run_technical_scout(payload)
            risk_task = self._run_risk_scout(payload)

            sentiment_analysis, technical_analysis, risk_analysis = await asyncio.gather(
                sentiment_task, technical_task, risk_task
            )

            # Orchestrator synthesizes the responses using strict JSON format
            return await self._run_orchestrator(payload, sentiment_analysis, technical_analysis, risk_analysis)

        except Exception as e:
            print(f"Gemini API Error: {e}")
            # Fallback pattern if API fails: proceed to deterministic risk engine but log warning
            return SignalReview(
                schema_version="1.0",
                signal_id=payload.signal_id,
                decision=DecisionEnum.PROCEED_TO_SIMULATION,
                confidence=0.5,
                reason_codes=["API_FALLBACK"],
                risk_flags=["GEMINI_UNAVAILABLE"],
                reject_reason=None,
                requires_human_review=False
            )

    async def _run_sentiment_scout(self, payload: M8Payload) -> str:
        prompt = f"Analyze sentiment for {payload.symbol} at {payload.timestamp}. Is there any macro news?"
        return await self._call_gemini(prompt, system="You are a market sentiment expert. Keep it brief.")

    async def _run_technical_scout(self, payload: M8Payload) -> str:
        prompt = f"Review technicals: Direction: {payload.direction}, Confluence: {payload.confluence_score}, Dispersion: {payload.mc_dispersion}."
        return await self._call_gemini(prompt, system="You are a quant technical analyst. Assess setup quality.")

    async def _run_risk_scout(self, payload: M8Payload) -> str:
        prompt = f"Assess risk: Crisis Score is {payload.crisis_score}. Spread is {payload.spread}."
        return await self._call_gemini(prompt, system="You are a risk manager. Flag any anomalies.")

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

        json_output = await self._call_gemini(
            prompt,
            system="You are the lead trading orchestrator. You MUST return strictly valid JSON. Do not include markdown code blocks.",
            response_mime_type="application/json"
        )

        try:
            # We don't need to strip markdown block wrappers usually with Gemini application/json, but safe to do
            clean_json = json_output.replace('```json', '').replace('```', '').strip()
            data = json.loads(clean_json)
            data['signal_id'] = payload.signal_id
            data['schema_version'] = "1.0"
            return SignalReview(**data)
        except Exception as e:
            print(f"Failed to parse JSON from Gemini: {e}")
            raise e

    async def _call_gemini(self, prompt: str, system: str = "You are a helpful assistant", response_mime_type: str = "text/plain") -> str:
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                response_mime_type=response_mime_type
            )
        )
        # Using generate_content_async for concurrency
        response = await model.generate_content_async(prompt)
        return response.text

ai_gemini_instance = GeminiSwarmService()
