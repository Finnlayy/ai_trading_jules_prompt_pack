import json
import asyncio
from openai import AsyncOpenAI
from typing import Dict, Any

from app.schemas.m8_payload import M8Payload
from app.schemas.ai_review import SignalReview, DecisionEnum
from app.core.config import MOONSHOT_API_KEY, MOONSHOT_BASE_URL, MOONSHOT_MODEL

# Instantiate Async Client pointing to Moonshot API
client = AsyncOpenAI(
    api_key=MOONSHOT_API_KEY or "dummy_key_for_tests", 
    base_url=MOONSHOT_BASE_URL
)

class KimiSwarmService:
    """
    Implements a multi-agent swarm using Kimi K2.6 models to review the signal payload.
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
            
            # Orchestrator synthesizes the responses
            return await self._run_orchestrator(payload, sentiment_analysis, technical_analysis, risk_analysis)
            
        except Exception as e:
            print(f"Kimi API Error: {e}")
            # Fallback pattern if API fails: proceed to deterministic risk engine but log warning
            return SignalReview(
                schema_version="1.0",
                signal_id=payload.signal_id,
                decision=DecisionEnum.PROCEED_TO_SIMULATION,
                confidence=0.5,
                reason_codes=["API_FALLBACK"],
                risk_flags=["KIMI_UNAVAILABLE"],
                reject_reason=None,
                requires_human_review=False
            )

    async def _run_sentiment_scout(self, payload: M8Payload) -> str:
        prompt = f"Analyze sentiment for {payload.symbol} at {payload.timestamp}. Is there any macro news?"
        return await self._call_kimi(prompt, system="You are a market sentiment expert. Keep it brief.")

    async def _run_technical_scout(self, payload: M8Payload) -> str:
        prompt = f"Review technicals: Direction: {payload.direction}, Confluence: {payload.confluence_score}, Dispersion: {payload.mc_dispersion}."
        return await self._call_kimi(prompt, system="You are a quant technical analyst. Assess setup quality.")

    async def _run_risk_scout(self, payload: M8Payload) -> str:
        prompt = f"Assess risk: Crisis Score is {payload.crisis_score}. Spread is {payload.spread}."
        return await self._call_kimi(prompt, system="You are a risk manager. Flag any anomalies.")

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
            system="You are the lead trading orchestrator. You MUST return strictly valid JSON. Do not include markdown code blocks.",
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
            print(f"Failed to parse JSON from Kimi: {e}")
            raise e

    async def _call_kimi(self, prompt: str, system: str = "You are a helpful assistant", response_format: Any = None) -> str:
        kwargs = {
            "model": MOONSHOT_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        
        # moonshot-v1 doesn't consistently support response_format strict json yet, but we try
        if response_format:
            kwargs["response_format"] = response_format
            
        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

ai_review_instance = KimiSwarmService()
