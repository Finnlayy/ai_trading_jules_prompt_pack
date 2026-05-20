# JSON Schema Contracts

These are starter contracts Jules should refine into production schemas.

## AI Signal Review

```json
{
  "type": "object",
  "required": [
    "schema_version",
    "signal_id",
    "decision",
    "confidence",
    "reason_codes",
    "risk_flags",
    "reject_reason",
    "requires_human_review"
  ],
  "properties": {
    "schema_version": { "type": "string" },
    "signal_id": { "type": "string" },
    "decision": { "enum": ["PROCEED_TO_SIMULATION", "REJECT", "HUMAN_REVIEW"] },
    "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
    "reason_codes": {
      "type": "array",
      "items": { "type": "string" }
    },
    "risk_flags": {
      "type": "array",
      "items": { "type": "string" }
    },
    "reject_reason": { "type": ["string", "null"] },
    "requires_human_review": { "type": "boolean" }
  }
}
```

## Risk Flag

```json
{
  "type": "object",
  "required": [
    "flag_code",
    "severity",
    "source",
    "evidence",
    "action"
  ],
  "properties": {
    "flag_code": { "type": "string" },
    "severity": { "enum": ["INFO", "WARNING", "CRITICAL"] },
    "source": { "enum": ["M8", "RISK_ENGINE", "AI_REVIEW", "BROKER_SIM", "DATA_PIPELINE"] },
    "evidence": { "type": "string" },
    "action": { "enum": ["LOG_ONLY", "REDUCE_SIZE", "REJECT", "HALT_SIMULATION", "HUMAN_REVIEW"] }
  }
}
```

## Trade Journal Entry

```json
{
  "type": "object",
  "required": [
    "trade_id",
    "timestamp",
    "symbol",
    "timeframe",
    "direction",
    "entry_price",
    "stop_price",
    "target_price",
    "risk_reward",
    "m8_score",
    "ai_decision",
    "final_decision",
    "simulated_fill",
    "result"
  ],
  "properties": {
    "trade_id": { "type": "string" },
    "timestamp": { "type": "string" },
    "symbol": { "type": "string" },
    "timeframe": { "type": "string" },
    "direction": { "enum": ["LONG", "SHORT"] },
    "entry_price": { "type": "number" },
    "stop_price": { "type": "number" },
    "target_price": { "type": "number" },
    "risk_reward": { "type": "number" },
    "m8_score": { "type": "number" },
    "ai_decision": { "enum": ["PROCEED_TO_SIMULATION", "REJECT", "HUMAN_REVIEW"] },
    "final_decision": { "enum": ["EXECUTED_SIM", "REJECTED", "SKIPPED"] },
    "simulated_fill": { "type": "object" },
    "result": { "type": ["object", "null"] }
  }
}
```

## Strategy Hypothesis

```json
{
  "type": "object",
  "required": [
    "hypothesis_id",
    "source_agent",
    "setup",
    "trigger",
    "invalidation",
    "target",
    "no_trade_conditions",
    "test_plan",
    "expected_failure_mode"
  ],
  "properties": {
    "hypothesis_id": { "type": "string" },
    "source_agent": { "type": "string" },
    "setup": { "type": "string" },
    "trigger": { "type": "string" },
    "invalidation": { "type": "string" },
    "target": { "type": "string" },
    "no_trade_conditions": {
      "type": "array",
      "items": { "type": "string" }
    },
    "test_plan": { "type": "string" },
    "expected_failure_mode": { "type": "string" }
  }
}
```

## Backtest Summary

```json
{
  "type": "object",
  "required": [
    "backtest_id",
    "dataset",
    "period",
    "trade_count",
    "profit_factor",
    "max_drawdown",
    "sharpe",
    "baseline_comparison",
    "passed",
    "reject_reason"
  ],
  "properties": {
    "backtest_id": { "type": "string" },
    "dataset": { "type": "string" },
    "period": { "type": "string" },
    "trade_count": { "type": "integer" },
    "profit_factor": { "type": "number" },
    "max_drawdown": { "type": "number" },
    "sharpe": { "type": "number" },
    "baseline_comparison": { "type": "string" },
    "passed": { "type": "boolean" },
    "reject_reason": { "type": ["string", "null"] }
  }
}
```

