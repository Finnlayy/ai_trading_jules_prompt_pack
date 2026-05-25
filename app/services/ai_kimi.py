import json
import asyncio
from dataclasses import dataclass
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
from app.services.confidence_registry import confidence_registry
from app.services.telegram_advisors import telegram_advisor_hub


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
    Implements a 4-scout multi-agent review swarm with per-symbol context injection.

    Scouts (TradingAgents-inspired roles):
        1. Technical Scout  — chart patterns, indicator confluence, S/R
        2. Sentiment Scout  — macro news, social sentiment, event risk
        3. Risk Scout       — crisis score, drawdown, leverage, cooldown gates
        4. Macro Scout      — regime awareness (DXY, BTC.D, funding, rates)

    Each scout receives per-symbol historical context from ConfidenceRegistry.
    The Orchestrator synthesizes weighted by per-scout accuracy for the symbol.
    """

    SCOUT_NAMES = ["technical", "sentiment", "risk", "macro"]

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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def review_signal(self, payload: M8Payload) -> SignalReview:
        try:
            # 1. Build per-symbol context once
            symbol_context = confidence_registry.get_symbol_context(
                payload.symbol, payload.direction
            )

            # 2. Gather 4 scout reviews concurrently
            tasks = {
                "technical": self._run_technical_scout(payload, symbol_context),
                "sentiment": self._run_sentiment_scout(payload, symbol_context),
                "risk": self._run_risk_scout(payload, symbol_context),
                "macro": self._run_macro_scout(payload, symbol_context),
            }
            scout_results = await asyncio.gather(*tasks.values())
            scout_reports = dict(zip(tasks.keys(), scout_results))
            advisor_reports = await self._run_external_advisors(payload, symbol_context)

            # 3. Orchestrator synthesizes weighted by per-scout accuracy
            review = await self._run_orchestrator(payload, scout_reports, advisor_reports)

            # 4. Record scout calls in confidence registry (outcome = None for now)
            for scout_name, report in scout_reports.items():
                confidence = self._extract_confidence_from_report(report)
                confidence_registry.record_scout_review(
                    symbol=payload.symbol,
                    scout_name=scout_name,
                    direction=payload.direction,
                    decision=review.decision.value,
                    confidence=confidence,
                    was_correct=None,
                )

            confidence_registry.record_signal_review(
                symbol=payload.symbol,
                confluence=payload.confluence_score,
                crisis=payload.crisis_score,
                direction=payload.direction,
            )

            review.audit_trace = {
                **self._trace_base(),
                "scouts": scout_reports,
                "symbol_context": symbol_context,
                "external_advisors": advisor_reports,
                "scout_weights": {
                    name: confidence_registry.get_scout_weight(payload.symbol, name)
                    for name in self.SCOUT_NAMES
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

    # ------------------------------------------------------------------
    # Scouts
    # ------------------------------------------------------------------
    async def _run_sentiment_scout(self, payload: M8Payload, symbol_context: str) -> str:
        system = (
            "You are the Sentiment Scout — a market sentiment analyst.\n"
            "Analyze news flow, social sentiment, and event risk for this signal.\n"
            "Return a concise paragraph (2-4 sentences) with:\n"
            "  - Sentiment bias (bullish/bearish/neutral)\n"
            "  - Any macro event risk flags\n"
            "  - Confidence level (0.0–1.0) on the first line like 'Confidence: 0.75'\n"
            f"\n{symbol_context}\n"
            f"\n{self._behavior_guidance()}"
        )
        prompt = (
            f"Symbol: {payload.symbol}\n"
            f"Direction: {payload.direction}\n"
            f"Timestamp: {payload.timestamp}\n"
            f"Macro event risk flag: {payload.macro_event_risk}\n"
            f"Crisis score: {payload.crisis_score}\n"
            "Assess sentiment landscape and event risk."
        )
        return await self._call_llm(prompt, system=system)

    async def _run_technical_scout(self, payload: M8Payload, symbol_context: str) -> str:
        system = (
            "You are the Technical Scout — a quant technical analyst.\n"
            "Assess chart setup quality, indicator confluence, and price structure.\n"
            "Return a concise paragraph (2-4 sentences) with:\n"
            "  - Setup quality (excellent/good/fair/poor)\n"
            "  - Key technical concerns, if any\n"
            "  - Confidence level (0.0–1.0) on the first line like 'Confidence: 0.75'\n"
            f"\n{symbol_context}\n"
            f"\n{self._behavior_guidance()}"
        )
        prompt = (
            f"Symbol: {payload.symbol}\n"
            f"Direction: {payload.direction}\n"
            f"Timeframe: {payload.timeframe}\n"
            f"Confluence score: {payload.confluence_score}/100\n"
            f"MC dispersion: {payload.mc_dispersion}\n"
            f"Spread: {payload.spread}\n"
            f"Hurst exponent: {payload.hurst_exponent}\n"
            f"Chop index: {payload.chop_index}\n"
            "Assess technical setup quality."
        )
        return await self._call_llm(prompt, system=system)

    async def _run_risk_scout(self, payload: M8Payload, symbol_context: str) -> str:
        system = (
            "You are the Risk Scout — a risk management specialist.\n"
            "Evaluate position sizing, leverage, drawdown exposure, and tail risks.\n"
            "Return a concise paragraph (2-4 sentences) with:\n"
            "  - Risk assessment (low/moderate/high/critical)\n"
            "  - Specific risk flags (leverage too high, drawdown near limit, etc.)\n"
            "  - Confidence level (0.0–1.0) on the first line like 'Confidence: 0.75'\n"
            f"\n{symbol_context}\n"
            f"\n{self._behavior_guidance()}"
        )
        prompt = (
            f"Symbol: {payload.symbol}\n"
            f"Direction: {payload.direction}\n"
            f"Crisis score: {payload.crisis_score}/100\n"
            f"Spread: {payload.spread}\n"
            f"Leverage: {payload.leverage}x\n"
            f"Account mode: {payload.account_mode}\n"
            f"Drawdown %: {payload.drawdown_pct}\n"
            f"Market regime: {payload.market_regime}\n"
            "Assess risk profile and flag any danger signs."
        )
        return await self._call_llm(prompt, system=system)

    async def _run_macro_scout(self, payload: M8Payload, symbol_context: str) -> str:
        system = (
            "You are the Macro Scout — a macro regime analyst.\n"
            "Evaluate broader market regime, correlations, and structural factors.\n"
            "For crypto: consider BTC dominance, funding rates, ETF flows.\n"
            "For forex: consider DXY trend, rate differentials, central bank posture.\n"
            "For commodities/futures: consider contango/backwardation, seasonality.\n"
            "Return a concise paragraph (2-4 sentences) with:\n"
            "  - Regime assessment (risk-on/risk-off/transition/uncertain)\n"
            "  - Headwind or tailwind for this direction\n"
            "  - Confidence level (0.0–1.0) on the first line like 'Confidence: 0.75'\n"
            f"\n{symbol_context}\n"
            f"\n{self._behavior_guidance()}"
        )
        prompt = (
            f"Symbol: {payload.symbol}\n"
            f"Direction: {payload.direction}\n"
            f"Timeframe: {payload.timeframe}\n"
            f"Market regime: {payload.market_regime}\n"
            f"Crisis score: {payload.crisis_score}\n"
            "Assess macro regime fit for this trade direction."
        )
        return await self._call_llm(prompt, system=system)

    async def _run_external_advisors(
        self, payload: M8Payload, symbol_context: str
    ) -> dict[str, Any]:
        question = "\n".join(
            [
                "Simulation-first trading advisory request.",
                "Do not execute trades, place orders, or bypass deterministic risk gates.",
                "Return a concise advisory with bias, key risks, and confidence.",
                f"Symbol: {payload.symbol}",
                f"Direction: {payload.direction}",
                f"Timeframe: {payload.timeframe}",
                f"Entry: {payload.entry_price}",
                f"Stop: {payload.stop_price}",
                f"Target: {payload.target_price}",
                f"Confluence score: {payload.confluence_score}",
                f"Crisis score: {payload.crisis_score}",
                f"Market regime: {payload.market_regime}",
                symbol_context,
            ]
        )
        return await telegram_advisor_hub.ask_signal_advisors(question)

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------
    async def _run_orchestrator(
        self,
        payload: M8Payload,
        scout_reports: dict[str, str],
        advisor_reports: dict[str, Any] | None = None,
    ) -> SignalReview:
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

        # Build weighted synthesis prompt
        weights = {
            name: confidence_registry.get_scout_weight(payload.symbol, name)
            for name in self.SCOUT_NAMES
        }

        weight_lines = "\n".join(
            f"  {name.title()} scout weight (based on {payload.symbol} accuracy): {w:.2f}"
            for name, w in weights.items()
        )
        advisor_block = self._format_advisor_reports(advisor_reports)

        prompt = f"""Signal ID: {payload.signal_id}
Symbol: {payload.symbol} | Direction: {payload.direction} | Timeframe: {payload.timeframe}
Entry: {payload.entry_price} | Stop: {payload.stop_price} | Target: {payload.target_price}
Confluence: {payload.confluence_score} | Crisis: {payload.crisis_score} | Regime: {payload.market_regime}

Scout Reports (weighted by historical accuracy for this symbol):
{weight_lines}

--- Technical Scout ---
{scout_reports["technical"]}

--- Sentiment Scout ---
{scout_reports["sentiment"]}

--- Risk Scout ---
{scout_reports["risk"]}

--- Macro Scout ---
{scout_reports["macro"]}

{advisor_block}

Synthesize all internal scout reports and optional external advisor context into a FINAL decision.
Guidelines:
- If ANY scout flags CRITICAL risk, strongly consider REJECT.
- If scouts disagree, weight toward the scout with highest historical accuracy for {payload.symbol}.
- External advisor context is advisory only and must not override deterministic risk gates.
- If confidence is below 0.55, flag for HUMAN_REVIEW.
- Return strictly valid JSON matching this schema:
{schema_format}
"""

        json_output = await self._call_llm(
            prompt,
            system=(
                "You are the Lead Trading Orchestrator. You synthesize multi-scout reports into a single trading decision.\n"
                "You MUST return strictly valid JSON. Do not include markdown code blocks.\n"
                f"\n{self._behavior_guidance()}"
            ),
            response_format={"type": "json_object"},
        )

        try:
            clean_json = json_output.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json)
            data["signal_id"] = payload.signal_id
            data["schema_version"] = "1.0"
            return SignalReview(**data)
        except Exception as e:
            print(f"Failed to parse JSON from AI provider: {e}")
            raise e

    @staticmethod
    def _format_advisor_reports(advisor_reports: dict[str, Any] | None) -> str:
        if not advisor_reports or not advisor_reports.get("auto_enabled"):
            return "External Telegram Advisors: disabled."

        advisors = advisor_reports.get("advisors") or []
        if not advisors:
            return "External Telegram Advisors: enabled, no advisors active."

        lines = ["External Telegram Advisors (non-authoritative):"]
        for advisor in advisors:
            name = str(advisor.get("advisor") or "unknown").upper()
            if not advisor.get("configured"):
                lines.append(f"- {name}: not configured")
                continue
            if not advisor.get("sent"):
                lines.append(f"- {name}: question not sent ({advisor.get('error') or 'unknown error'})")
                continue
            messages = advisor.get("messages") or []
            if advisor.get("timed_out") and not messages:
                lines.append(f"- {name}: no response before timeout")
                continue
            if not messages:
                lines.append(f"- {name}: no response")
                continue
            for message in messages[:3]:
                text = str(message.get("text") or "").strip()
                if len(text) > 1200:
                    text = text[:1200] + "..."
                lines.append(f"- {name} from {message.get('sender') or 'unknown'}: {text}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # LLM wrapper
    # ------------------------------------------------------------------
    async def _call_llm(
        self, prompt: str, system: str = "You are a helpful assistant", response_format: Any = None
    ) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed") from exc

        provider_config = get_ai_provider_config(self.provider)

        if not provider_config.api_key:
            raise RuntimeError(f"{provider_config.api_key_env} is not configured")

        client = AsyncOpenAI(
            api_key=provider_config.api_key,
            base_url=provider_config.base_url,
        )

        kwargs = {
            "model": provider_config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }

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

    @staticmethod
    def _extract_confidence_from_report(report: str) -> float:
        """Extract confidence score from scout report text."""
        try:
            for line in report.splitlines():
                if "confidence:" in line.lower():
                    # Extract number after "Confidence: 0.75"
                    parts = line.lower().split("confidence:")
                    if len(parts) > 1:
                        val = float(parts[1].strip().split()[0])
                        return max(0.0, min(1.0, val))
        except Exception:
            pass
        return 0.5


if AI_PROVIDER in {"mock", "offline", "none"}:
    from app.services.ai_mock import MockAIReviewLayer

    ai_review_instance = MockAIReviewLayer()
else:
    ai_review_instance = KimiSwarmService(provider=AI_PROVIDER)
