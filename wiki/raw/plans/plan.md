The issue says "Too Many Parameters" at `app/services/glint_broker.py:260`.

Looking at `_build_entry` in `glint_broker.py`, `pionex_direct_broker.py`, `ctrader_broker.py`, and `ctrader_fix_broker.py`:
```python
    def _build_entry(
        self,
        payload: M8Payload,
        decision: DecisionEnum, # Not used in TradeJournalEntry! (Only in glint and pionex_direct)
        reject_reason: Optional[str], # Not used in TradeJournalEntry!
        ai_decision: AIDecisionEnum,
        final_decision: FinalDecisionEnum,
        simulated_fill: dict[str, Any],
        result: dict[str, Any],
    ) -> TradeJournalEntry:
```
In `TradeJournalEntry` definition, there's no `reject_reason` and `decision` field (there is `ai_decision` mapped to `DecisionEnum` and `final_decision` mapped to `FinalDecisionEnum`).
Wait, actually `TradeJournalEntry` has:
```python
    trade_id: str
    timestamp: str
    symbol: str
    timeframe: str
    direction: DirectionEnum
    entry_price: float
    stop_price: float
    target_price: float
    risk_reward: float
    m8_score: float
    ai_decision: DecisionEnum
    final_decision: FinalDecisionEnum
    simulated_fill: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
```
So `decision` (which is often `DecisionEnum.PROCEED_TO_SIMULATION` or `DecisionEnum.REJECT`) and `reject_reason` are passed to `_build_entry` in `GlintBroker` and `PionexDirectBroker` but they are NEVER USED inside the method.

In `glint_broker.py` `_build_entry`:
```python
    def _build_entry(
        self,
        payload: M8Payload,
        decision: DecisionEnum,
        reject_reason: Optional[str],
        ai_decision: AIDecisionEnum,
        final_decision: FinalDecisionEnum,
        simulated_fill: dict[str, Any],
        result: dict[str, Any],
    ) -> TradeJournalEntry:
        #...
        entry = TradeJournalEntry(
            #...
            ai_decision=DecisionEnum(ai_decision.value),
            final_decision=final_decision,
            simulated_fill=simulated_fill,
            result=result,
        )
```

By removing `decision` and `reject_reason` from the signature of `_build_entry` in `GlintBroker` and `PionexDirectBroker`, we can reduce the number of parameters. This also aligns the signature with `CTraderBroker` and `CTraderFixBroker`, which already don't have `decision` and `reject_reason`.

Let's do a find-and-replace to remove these two parameters from `_build_entry` and all its callers in `glint_broker.py` and `pionex_direct_broker.py`.

Wait, the prompt says "Too Many Parameters".
If we remove `decision` and `reject_reason`, the number of parameters goes from 8 (including `self`) to 6. This might be enough to satisfy the linter.

Let's examine `_build_entry` in `glint_broker.py`:
It is called in 3 places.
