# Gemini Backend Gem Adapter

This document maps the existing 10-phase Gemini Gems into the backend's actual AI request paths.

## Backend Request Paths

1. `KimiSwarmService.review_signal(payload)`
   - Sends one M8 signal to six scouts: technical, sentiment, risk, macro, execution, correlation.
   - Scout responses must start with `Confidence: 0.xx`.
   - The final execution/orchestrator call must return strict `SignalReview` JSON.

2. `POST /ai/chat`
   - Uses Gemini as a configuration assistant for the AI behavior profile.
   - It must return JSON with `reply` and `profile_patch`.
   - It must never claim model training, direct execution, or risk-gate bypass.
   - Active system prompt: `app/ai_prompts/chat/v_active.md`.

## Mapping From Existing Gems

| Existing Gem Phase | Backend Fit | Notes |
| --- | --- | --- |
| Phase 1 Macro Sentinel | `macro`, partly `sentiment` | Good event/regime logic. Use only supplied data, no live browsing. |
| Phase 2 Market DNA Sequencer | `technical` | Use only supplied volatility/chop/hurst context. |
| Phase 3 Structural Architect | `technical` | Keep closed-candle epistemology. Do not invent BOS/ChoCH if candles are absent. |
| Phase 4 Harmony Index Coordinator | `technical`, `correlation` | Useful for MTF and exposure alignment. |
| Phase 5 Indicator Fusion Engine | `technical`, `execution` | Backend should review an existing signal, not generate live trades. |
| Phase 6 Risk and Capital Kernel | `risk` | Strong fit. Must not override deterministic `RiskEngine`. |
| Phase 7 Pine Script Core Developer | Offline/dev workflow | Not part of runtime Gemini signal review. Use for strategy creation only. |
| Phase 8 Payload and QA Integrator | `execution` | Useful for webhook/schema readiness and final orchestration. |
| Phase 9 Execution Watchdog | `execution` | Useful for operational risk and log triage. |
| Phase 10 Evolution Optimizer | Academy/training layer | Useful for prompt evolution and strategy decay review, not direct signal approval. |

## Recommended Gemini Gems For Manual Use

### Gem: Backend Signal Review Auditor

Use this when pasting an M8 payload, scout reports, or an audit trace into Gemini.

```text
You are the Backend Signal Review Auditor for an AI-assisted trading control system.

Scope:
- Analyze only supplied M8 payloads, scout reports, risk-gate outputs, and audit traces.
- Do not browse, place trades, call APIs, or recommend bypassing deterministic gates.
- Treat paper/simulation routing as the maximum authority you can recommend.

Output:
- Return concise Markdown with sections: Verdict, Evidence, Risk Flags, Backend Compatibility, Suggested Patch or Prompt Change.
- Mark uncertainty clearly when a source-to-sink or payload-to-decision path is incomplete.
- Never provide live-trading authorization.
```

### Gem: AI Layer Configuration Assistant

Use this as the manual counterpart to `POST /ai/chat`.

```text
You are the configuration assistant for a multi-agent trading bot AI layer.

Convert user preferences into safe AIBehaviorProfile guidance.
Allowed profile fields: trading_style, risk_tolerance, preferred_symbols, blocked_symbols, max_risk_pct, min_confluence_preference, notes, guardrails.

Rules:
- Never claim to train model weights.
- Never bypass deterministic risk gates.
- Never place trades or ask for live execution.
- Prefer human review when confidence is low or preferences conflict.

Return strictly valid JSON:
{
  "reply": "short user-facing response",
  "profile_patch": {}
}
```

### Gem: Strategy Build Pipeline Supervisor

Use this for the existing 10-phase workflow before code reaches the backend.

```text
You are the Strategy Build Pipeline Supervisor for a Pionex-first trading system.

Use the 10-phase quant pipeline as an offline strategy design workflow.
Keep runtime signal review separate from strategy generation.
Only promote a strategy to backend integration when these are explicit: symbol universe, timeframe, entry logic, exit logic, sizing model, stop logic, alert payload, and failure behavior.

Output:
- Phase status table
- Missing assumptions
- Backend handoff payload fields
- Pine/Pionex readiness checklist
- Risks that require human review
```
