# Jules Execution Checklist

## Step 1: Start With Planning Only

Paste `01_jules_masterprompt.md` into Jules.

Attach or paste:
- `02_research_brief_input.md`
- `03_sigma_m8_context.md`
- `04_agent_roles_and_boundaries.md`
- `05_json_schema_contracts.md`
- `06_validation_and_risk_gates.md`

Instruction:

```text
Do not write code yet. First produce the full architecture, MVP recommendation, module plan, schemas, validation gates, and 30/60/90-day roadmap.
```

## Step 2: Ask Jules for a File Plan

After the planning answer:

```text
Convert the MVP into a concrete repository file plan. For every file, specify purpose, inputs, outputs, dependencies, and tests.
```

## Step 3: Ask Jules for the First Implementation Slice

Recommended first slice:

```text
Implement only the signal ingestion and schema validation layer:
- FastAPI endpoint
- Pydantic schemas
- M8 payload parser
- rejection reason mapper
- unit tests
Do not implement AI calls or broker simulation yet.
```

## Step 4: Add Deterministic Risk Engine

```text
Implement the deterministic risk engine:
- reward/risk validation
- spread gate
- slippage model
- daily drawdown gate
- max trades per day
- cooldown
- duplicate signal rejection
- tests for every reject reason
```

## Step 5: Add Simulation Broker

```text
Implement a simulation broker:
- mock fills
- fee model
- slippage model
- spread handling
- trade journal output
- deterministic replay support
```

## Step 6: Add AI Review Layer

```text
Add AI review as a non-execution layer:
- AI receives signal context
- AI returns schema-validated SignalReview JSON
- deterministic engine may only use enum fields and risk flags
- free text is logged but cannot execute trades
```

## Step 7: Add Kimi Swarm / GPT-5.5 / Manus

Use only after deterministic pipeline passes tests.

Recommended option:

```text
Use GPT-5.5 as orchestrator, Kimi as parallel research workers, and Manus only for autonomous research/report tasks with human approval checkpoints.
```

## Step 8: Final Acceptance Criteria

The MVP is acceptable only if:
- all schemas validate
- invalid AI output is rejected
- duplicate signals are rejected
- lookahead-bias tests pass
- out-of-sample test exists
- walk-forward test exists
- every simulated order has a journal entry
- every rejection has a reason code
- no AI component can place an order directly

