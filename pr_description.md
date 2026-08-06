🎯 **What:** Modified `_send_live_entry` signature in `PionexDirectBroker` to accept the consolidated `KellySizingResult` object instead of its individual attributes `size_base` and `order_value_usdt`. Updated the caller accordingly.
💡 **Why:** To improve code maintainability and cleanliness by reducing parameter count. This solves the "Too Many Parameters" issue.
✅ **Verification:** Verified by executing the full backend test suite (`python -m pytest tests/services/test_pionex_direct_broker.py` and `DATABASE_URL="sqlite:///./app/data/trading.db" bash run_qa.sh`) which passed successfully.
✨ **Result:** A cleaner and more concise method signature that groups cohesive data into a single parameter.
