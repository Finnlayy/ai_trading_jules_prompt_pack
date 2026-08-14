<<<<<<< HEAD
🎯 What: Added tests to cover `json_dumps` and its default handler `json_dumps_default` in `app/core/utils.py`.
📊 Coverage: Covered standard data types, classes with `isoformat`, `to_dict`, and `model_dump` methods, fallback objects (to `str`), `kwargs` passing, and explicitly providing an overriding `default` argument.
✨ Result: Improved test coverage significantly on a pure function handling JSON serialization, guarding against regression.
=======
🎯 **What:**
<<<<<<< HEAD
Added comprehensive testing for the schemas and utilities located in `app/schemas/ai_layer.py`. Prior to this change, the simple and stateless schema utilities lacked coverage, particularly the `utc_now` helper function and default value constraints.

📊 **Coverage:**
The new test suite in `tests/schemas/test_ai_layer.py` covers the following:
- `utc_now`: Verified to return ISO-formatted timestamps with valid UTC timezones.
- `AIBehaviorProfile`: Validated default initialization, value bounds for `max_risk_pct` (>0.0), and `min_confluence_preference` (0.0 - 100.0).
- `AIChatMessage`: Verified defaults and constraints on valid role literal assignments.
- `AIChatRequest`: Checked message length limits and bounded `bars_count` properties.
- `AIChatResponse`: Assessed base schema instantiations ensuring valid typing cascades.

✨ **Result:**
Improved schema testing reliability across `ai_layer`, increasing full test suite coverage and helping confidently prevent future regression issues regarding payload parsing boundaries.
=======
Extracted inline processing from `_close_position` in `app/services/pionex_direct_broker.py` into dedicated helper methods: `_build_reject_close_entry`, `_calculate_close_pnl_and_side`, `_record_trade_metrics`, and `_execute_live_close_or_rollback`.

💡 **Why:**
The `_close_position` function was doing too many things simultaneously, acting as a "God object" for all aspects of closing a position. Breaking it down structurally limits its length, decreases complexity (cyclomatic and cognitive), and enhances code readability and maintainability.

✅ **Verification:**
Executed Pytest unit tests for the broker implementation. Also ran the extensive backend QA suite which covers other components that could have been potentially impacted by downstream effects. Tests passed successfully.

✨ **Result:**
The `_close_position` logic is now heavily reduced in statement count and reads straightforwardly. This aligns with standard python coding patterns for clean functions without changing the logical behavior or side effects of the code.
>>>>>>> main
>>>>>>> main
