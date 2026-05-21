# PINE SCRIPT STUDIO & THE GAUNTLET: Master Architecture Document

## 1. Executive Summary

This document serves as the Single Source of Truth for the "Pine Script Studio" ecosystem and "The Drawdown Survival Gauntlet" (Season 1). The core philosophy is **"The High-Performance Constructor's Garage"**—a clinical, engineering-focused platform devoid of casino-like gamification.

The architecture enforces an iron-clad separation of concerns:
- **The Judge (Deterministic Python Backend):** The execution engine that processes ticks, enforces the rules of the Gauntlet, and calculates the Battle-Royale formula. It is immune to AI hallucinations.
- **The Swarm (AI Analysts):** A read-only analytical layer that consumes strictly validated JSON logs from The Judge to generate esports commentary and insights, driven by the narrative of loss-aversion and survival.

## 2. Core Architecture: The Iron Separation

### The Judge (Deterministic Python Backend)
- **Role:** Execution Engine, Tick Processor, and Rule Enforcer.
- **Inputs:** Tick data, webhook signals (from Pine Script Studio), OHLCV data.
- **Responsibilities:**
  - Execute trades deterministically based on incoming signals.
  - Apply realistic slippage, spread, and fee models (Freq-Penalty).
  - Enforce the "Guillotine" (instant termination if Max Drawdown reaches -25%).
  - Maintain the strict separation of In-Sample (IS) and Out-of-Sample (OOS) data pipelines.
  - Calculate the Gauntlet Scoring Formula.
  - Export state and trade logs strictly via the Data Handoff JSON Schema.

### The Swarm (AI Analysts)
- **Role:** Commentators and Post-Trade Analysts.
- **Inputs:** Data Handoff JSON Schema (provided by The Judge).
- **Responsibilities:**
  - Parse the deterministic logs to understand *why* a strategy survived or was liquidated.
  - Generate esports-style commentary focusing on robust engineering vs. curve-fitting.
  - Provide analytical context for the audience (e.g., explaining a death by Freq-Penalty due to lack of ATR-trailing).
- **Restrictions:** Absolutely no execution capability. Cannot alter The Judge's state or the scoring formula.

## 3. Gauntlet Scoring & Mechanics (Season 1)

The Gauntlet is a public survival tournament designed to test algorithmic robustness.

### Data Segregation Pipeline
- **In-Sample (IS) Qualifiers:** 48 hours. Competitors tune their algorithms on known historical datasets (e.g., specific market crashes).
- **Out-of-Sample (OOS) Finale:** The live event runs on completely unseen, cryptographically locked datasets to instantly destroy curve-fitted strategies.

### The Battle-Royale Formula
The ultimate metric for survival and victory:
`Total Score = (Sortino Ratio * Regime Resilience Bonus) - (Drawdown Penalty + Over-Trading Penalty)`

- **Sortino Ratio:** Primary metric. Penalizes downside volatility while rewarding protective upside. Must be > 2.0 to be competitive.
- **Regime Resilience Bonus:** Rewards strategies that maintain a consistent Profit Factor across different market regimes (e.g., High Volatility Trend, Low Volatility Chop).
- **Drawdown Penalty:** Incremental deductions as drawdown increases.
- **Over-Trading Penalty (Freq-Penalty):** Deductions for excessive trades, simulating realistic transaction costs and slippage. Kills high-frequency "noise" bots.

### The Guillotine
- A deterministic kill-switch hardcoded into The Judge.
- If a strategy's real-time equity exceeds a Maximum Drawdown of **-25%**, it is instantly "Liquidated" and removed from the Gauntlet.

## 4. Sub-Agent Directives

### Agent 1: The Quant Architect (Algo & Logic)
- **Focus:** Develop the reference strategy "Neo-Quantum SMC v6 (Apex Edition)".
- **Environment:** Pine Script v6.
- **Rules:** No repainting, no future leaks, only confirmed bars (`barstate.isconfirmed`), explicit booleans.
- **Logic:**
  - Maker-Logic (Shadow Orders in Breaker Blocks).
  - Displacement-Filter (Breakout candle > 1 ATR + Volume).
  - Regime-Filter (Standby mode when CHOP > 61.8).
  - Session-Routing (Trade only in liquidity killzones; avoid toxic sessions).
- **Risk Management:** Volume-scaled time-decay, dynamic breakeven, Kelly-Warmup (first 15 trades at 1% base risk).

### Agent 2: Backend Systems Engineer (The Judge)
- **Focus:** Build the Python backend.
- **Logic:** Tick processing engine with zero data leakage.
- **State Management:** Implement the Guillotine and IS/OOS segregation.
- **Integration:** Design and implement the JSON schema for Data Handoff to The Swarm.

### Agent 3: UI/UX Engineer (Frontend & Desktop App)
- **Focus:** Design "Pine Script Studio" with the "Neural Flow" interface.
- **Aesthetic:** Anti-Casino. Dark terminal design (gray, black, matte mint). No neon red/green. Industrial, tactile audio feedback (relay clicks).
- **Psychology:** The engine must communicate in the *Subjunctive Mood* (e.g., "The simulated win rate would have been...") to prevent overconfidence.
- **Features:** "The Disbelief Gauntlet" – visual stress tests showing naked KPIs (Sharpe, Sortino, Hurst, DER) alongside a Slippage-Injector and Liquidity Vacuum.

### Agent 4: AI Swarm & Community Architect
- **Focus:** esports commentary and community management.
- **Logic:** Validate JSON to prevent crashes. Explain deterministic deaths clearly based on the logs.
- **Narrative:** Focus on "Loss Aversion." Build tension around surviving extreme chaos simulations rather than chasing profit.

## 5. Execution Roadmap

1. **Establish Master Architecture (Completed):** Finalize `project_plan.md`.
2. **Backend Structure:** Outline `08_backend_judge_outline.py` detailing tick processing, the Guillotine, and the scoring formula.
3. **UI/UX Design:** Draft `09_ui_ux_disbelief_gauntlet.md` for the Neural Flow interface and subjunctive mood rules.
4. **Data Handoff:** Define `10_data_handoff_schema.json` to safely bridge The Judge and The Swarm.
