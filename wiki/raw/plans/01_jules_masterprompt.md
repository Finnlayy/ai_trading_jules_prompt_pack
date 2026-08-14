# Jules Masterprompt: AI-Agentic Simulated Trading Ecosystem

```text
Act as a senior AI trading-system architect, quant engineering lead, and skeptical project planner.

Your task:
Create a complete, implementation-ready project plan for an AI-assisted simulated trading ecosystem based on the attached/context-provided research brief and Sigma PineScript context.

This is a high-stakes technical planning task. Be sharp but fair. Avoid hype. No boilerplate warnings. Every risk must become a concrete engineering requirement, test, gate, fallback, or rejection rule.

<context>
We want to build a simulation-first AI trading ecosystem in 2026.

Core idea:
Use deterministic trading logic for execution and risk, while AI agents such as Kimi Swarm, GPT-5.5, and/or Manus support research, pattern recognition, sentiment analysis, backtest orchestration, code generation, journaling, and risk-flag detection.

Important principle:
LLMs must never directly place live orders. They may propose, classify, explain, score, reject, or summarize. Final execution must remain deterministic and schema-validated.

Existing PineScript base:
We have a Sigma Trading System with:
- EMH-LAC regime engine
- Kelly sizing
- walk-forward optimization
- crisis scanner
- dashboard
- alert engine
- Monte Carlo module
- newly added M8 Execution Quality Gate with:
  - confluence score
  - max trades per day
  - entry cooldown
  - optional relative volume filter
  - max crisis score
  - Monte Carlo dispersion filter
  - optional MC direction alignment
  - structured simulation alert payloads
</context>

<mission>
Write a complete project plan for building an AI-agentic simulated trading system that uses one or more of:

1. Kimi Swarm
   - bulk research
   - many-agent strategy exploration
   - sentiment swarm
   - parameter hypothesis generation
   - large-scale log/journal analysis

2. GPT-5.5
   - high-level orchestrator
   - code/debug assistant
   - agentic backtest controller
   - architecture reviewer
   - tool-use planner

3. Manus
   - autonomous research workflow
   - end-to-end task execution
   - repo/codebase operations
   - backtest report generation

The output must not be a generic essay. It must be a buildable engineering plan.
</mission>

<scope>
Primary scope is simulated trading only:
- historical backtesting
- walk-forward testing
- out-of-sample testing
- paper trading
- exchange testnet
- mock broker
- replay simulation
- structured journaling

Live trading is out of scope except as a future human-approved extension.
</scope>

<required_analysis>
Think step by step internally, then produce a concise structured plan.

Cover:

1. Target Architecture
Design the full architecture:
- PineScript/Sigma signal source
- webhook or export layer
- Python/FastAPI ingestion layer
- deterministic risk engine
- simulation broker
- market data store
- AI agent layer
- backtest runner
- journal/review layer
- dashboard/reporting layer

2. Agent Roles
Define exact roles for:
- Kimi Swarm
- GPT-5.5
- Manus

For each role specify:
- input data
- output format
- allowed actions
- forbidden actions
- validation method
- failure fallback

3. Agent Workflow
Design the workflow as if-then stages:
- market data ingestion
- Sigma signal generation
- M8 quality-gate interpretation
- AI context review
- deterministic reject/proceed decision
- simulated execution
- journaling
- post-trade review
- strategy refinement

4. Schema Contracts
Define JSON schemas for:
- AI signal review
- risk flags
- trade journal entry
- strategy hypothesis
- backtest result summary
- rejection reason

Every AI output must be machine-validated.
No free-text AI output may directly influence execution.

5. Kimi Swarm Plan
If Kimi Swarm is used, design:
- number/type of agents
- swarm tasks
- how agents avoid duplicate work
- how results are ranked
- how bad hypotheses are rejected
- how outputs are merged into one research report

Example swarm roles:
- sentiment scout
- macro scout
- technical-pattern scout
- strategy mutator
- backtest critic
- risk critic
- journal reviewer

6. GPT-5.5 Plan
If GPT-5.5 is used, define:
- when it acts as orchestrator
- when it reviews code
- when it writes tests
- when it critiques results
- when it must ask for human approval
- how it validates tool outputs

7. Manus Plan
If Manus is used, define:
- autonomous research tasks
- repository tasks
- backtest-report tasks
- documentation tasks
- limits on autonomy
- checkpoints requiring human approval

8. Implementation Roadmap
Create a 30/60/90-day implementation plan.

For each phase include:
- concrete deliverables
- files/modules to build
- tests to run
- acceptance criteria
- failure criteria
- estimated complexity

9. MVP Recommendation
Recommend one MVP only.

The MVP must be realistic for one developer or a small team:
- 1h or 4h timeframe
- simulation-first
- Sigma/PineScript signal input
- Python risk/simulation backend
- one AI review layer
- deterministic final decision
- journal/review loop

10. Validation Plan
Define exact validation requirements:
- out-of-sample test
- walk-forward test
- baseline comparison
- fees model
- slippage model
- spread model
- order-fill assumptions
- data leakage checks
- lookahead-bias checks
- minimum trade count
- rejection criteria

11. Risk Gates
Avoid generic risk language.
Turn every risk into a concrete gate.

Examples:
- Reject if no invalidation level exists.
- Reject if reward/risk < 2.0.
- Reject if spread > configured threshold.
- Reject if AI output fails schema validation.
- Reject if Kimi/GPT/Manus disagree with deterministic market state.
- Reject if M8 score < threshold.
- Reject if MC dispersion exceeds threshold.
- Reject if simulated daily drawdown exceeds limit.

12. Decision Matrix
Compare three deployment options:
A. Kimi Swarm only
B. GPT-5.5 orchestrator + Kimi workers
C. Manus autonomous research + GPT/Kimi reviewers

For each option score:
- realism
- cost
- complexity
- reliability
- debugging burden
- simulation value
- production-readiness
</required_analysis>

<tone>
Be direct, technical, and skeptical.
If an idea is hype, call it hype and replace it with a buildable version.
Do not say "trading is risky" unless you convert it into a specific engineering rule.
Do not recommend autonomous live order execution.
</tone>

<output_format>
Return the answer in this structure:

1. Executive Summary
2. Recommended System Architecture
3. Agent Role Design
4. Kimi Swarm Plan
5. GPT-5.5 Plan
6. Manus Plan
7. End-to-End Workflow
8. JSON Schema Contracts
9. MVP Build Plan
10. 30/60/90-Day Roadmap
11. Validation and Simulation Plan
12. Risk Gates and Rejection Rules
13. Decision Matrix
14. Concrete Next Actions
15. Open Questions

Use markdown tables where helpful.
Use precise engineering language.
No filler.
No boilerplate.
</output_format>

<self_review>
Before final output, critique your own plan:
- Is the MVP actually buildable?
- Are AI roles separated from deterministic execution?
- Are all warnings converted into gates/tests?
- Are the agent outputs schema-validated?
- Are Kimi/GPT/Manus used where they add real value?
- Is anything still hype?

Revise before final answer.
</self_review>
```

