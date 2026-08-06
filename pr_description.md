🎯 **What:**
Refactored `CTraderFixConfig` in `app/services/ctrader_fix_broker.py` into a Python `@dataclass`. This resolves a "Too Many Parameters" code health warning on its `__init__` method. It also simplified instantiations in `app/api/ctrader_fix.py` and `app/services/broker_factory.py` by removing explicit config parameter mapping and instead relying entirely on the default values inherited from `app.core.config`.

💡 **Why:**
The original `__init__` constructor had 8 parameters. This made the class harder to maintain and triggered static analysis warnings. By converting it to a `@dataclass`, we eliminate the verbose constructor boiler plate while maintaining strict typing and default values fallback logic in `__post_init__`, resulting in significantly cleaner class instantiations across the codebase.

✅ **Verification:**
- The refactored class was isolated tested and passed via `python -m pytest tests/api/test_ctrader_fix.py`.
- The full backend test suite was run (`DATABASE_URL="sqlite:///./app/data/trading.db" bash run_qa.sh`) with 679 tests passing, confirming that behavior for cTrader FIX API was preserved.
- Instantiations in api/ and services/ have been successfully simplified.

✨ **Result:**
Cleaner, more maintainable dependency injection for cTrader FIX API with zero functional regressions.
