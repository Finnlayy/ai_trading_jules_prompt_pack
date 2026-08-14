# Implementation Plan: Per-Scout AI Swarm Providers & Multi-Model Concurrency

This plan enables the multi-agent trading bot's AI layer to distribute scout evaluations across multiple providers and models simultaneously. Specifically, it enables users running multiple models or instances in LM Studio (e.g., `google/gemma-4-e2b:3` and `google/gemma-4-e2b:2`) to allocate different scouts to different instances concurrently, speeding up execution and unlocking targeted swarm intelligence.

---

## User Review Required

> [!NOTE]
> We will add support for the following environment variables to `.env` to configure per-scout providers and models:
> - `AI_PROVIDER_TECHNICAL`, `AI_PROVIDER_SENTIMENT`, `AI_PROVIDER_RISK`, `AI_PROVIDER_MACRO`, `AI_PROVIDER_EXECUTION`, `AI_PROVIDER_CORRELATION`
> - `AI_MODEL_TECHNICAL`, `AI_MODEL_SENTIMENT`, `AI_MODEL_RISK`, `AI_MODEL_MACRO`, `AI_MODEL_EXECUTION`, `AI_MODEL_CORRELATION`
>
> If a scout does not have a scout-specific provider/model configured, it will cleanly fall back to the primary default `AI_PROVIDER` and corresponding default model (`LMSTUDIO_MODEL`, `OPENAI_MODEL`, etc.).

---

## Proposed Changes

### Configuration Layer

#### [MODIFY] [config.py](file:///g:/Downloads_Sortiert_2026-05-20/ai_trading_jules_prompt_pack/app/core/config.py)
* Add and export typed environment variables for each scout's provider and model override.

---

### AI Service Layer

#### [MODIFY] [ai_kimi.py](file:///g:/Downloads_Sortiert_2026-05-20/ai_trading_jules_prompt_pack/app/services/ai_kimi.py)
* Update `_run_generic_scout`, `_run_sentiment_scout`, `_run_technical_scout`, `_run_risk_scout`, and `_run_macro_scout` to call a scout-specific `_call_llm_for_scout(scout_name, prompt, system, response_format)` method.
* Implement `_call_llm_for_scout` to dynamically resolve the configured provider and model name for the specific scout, initializing a targeted `AsyncOpenAI` client pointing to the appropriate endpoint.
* Log which provider and model instance were utilized for each scout call to provide clear diagnostic visibility in the server logs.

---

## Verification Plan

### Automated Tests
1. **Scout Mock Verification**:
   * Run the existing test suite: `python -m pytest tests/services/test_ai_kimi.py` to ensure no regressions in mocked or fallback behavior.
2. **Dynamic Multi-Model Test Script**:
   * Write and execute a temporary verification script that calls `KimiSwarmService` with technical, sentiment, risk, and macro scouts mapped to different LM Studio models (`google/gemma-4-e2b:3` and `google/gemma-4-e2b:2`) to verify that they run concurrently and resolve their respective instances.

### Manual Verification
1. Trigger a signal review and verify in the FastAPI server console logs that each scout displays its resolved provider and model instance correctly.
