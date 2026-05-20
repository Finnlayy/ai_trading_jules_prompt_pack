# Agent Roles and Boundaries

## Global Rule

No AI agent may directly place live orders.

AI agents may:
- analyze
- classify
- rank
- reject
- explain
- propose
- summarize
- generate code drafts
- generate test plans

Deterministic components must:
- validate schemas
- enforce risk gates
- simulate execution
- log results
- reject invalid states

## Kimi Swarm

### Best Use

- bulk research
- sentiment swarm
- hypothesis generation
- strategy mutation
- large-scale journal/log analysis
- cheap parallel context review

### Allowed Actions

- produce ranked hypotheses
- classify narratives
- extract risk flags from logs
- propose parameter ranges
- summarize backtest failures

### Forbidden Actions

- final trade decision
- direct order execution
- modifying production config without review
- approving its own hypothesis

### Required Output

Must return JSON only for machine-ingested tasks.

Minimum fields:
- `agent_id`
- `task_type`
- `claim`
- `evidence`
- `confidence`
- `reject_reason`
- `recommended_next_test`

## GPT-5.5

### Best Use

- top-level orchestrator
- architecture reviewer
- code/debug assistant
- tool-use planner
- backtest-controller
- final research synthesizer

### Allowed Actions

- break tasks into work packages
- generate implementation plans
- review code diffs
- write tests
- compare Kimi/Manus outputs
- produce final recommendations

### Forbidden Actions

- direct execution approval for live trading
- accepting unverified swarm claims
- bypassing schemas
- changing risk gates without human approval

### Required Behavior

GPT-5.5 must run self-review:
- Is this buildable?
- Is the AI separated from execution?
- Are claims verified?
- Are risk warnings converted into gates?

## Manus

### Best Use

- autonomous research task chains
- repository investigation
- backtest report generation
- documentation generation
- long-running workflow execution

### Allowed Actions

- run research workflows
- inspect repo structure
- produce reports
- generate task plans
- propose patches

### Forbidden Actions

- deploying live trading changes
- running uncontrolled optimizations
- overwriting strategy files without review
- publishing or external outreach

### Approval Checkpoints

Human approval required before:
- changing PineScript source
- changing risk thresholds
- enabling testnet execution
- running long/expensive swarm jobs
- promoting a strategy from simulation to paper trading

