🎯 **What:**
Extracted inline processing from `_close_position` in `app/services/pionex_direct_broker.py` into dedicated helper methods: `_build_reject_close_entry`, `_calculate_close_pnl_and_side`, `_record_trade_metrics`, and `_execute_live_close_or_rollback`.

💡 **Why:**
The `_close_position` function was doing too many things simultaneously, acting as a "God object" for all aspects of closing a position. Breaking it down structurally limits its length, decreases complexity (cyclomatic and cognitive), and enhances code readability and maintainability.

✅ **Verification:**
Executed Pytest unit tests for the broker implementation. Also ran the extensive backend QA suite which covers other components that could have been potentially impacted by downstream effects. Tests passed successfully.

✨ **Result:**
The `_close_position` logic is now heavily reduced in statement count and reads straightforwardly. This aligns with standard python coding patterns for clean functions without changing the logical behavior or side effects of the code.
