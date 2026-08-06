🎯 **What:**
Refactored `CTraderFixConfig` in `app/services/ctrader_fix_broker.py` to use a `@dataclass`. This resolves a code health issue where the `__init__` method had too many parameters, making it cumbersome and harder to maintain.

💡 **Why:**
By migrating from a manual `__init__` with many arguments to a Python `dataclass`, we drastically reduce boilerplate code, simplify default parameter assignment mapped to environment configurations (`app.core.config`), and improve code readability while retaining the post-initialization conditional logic in `__post_init__`.

✅ **Verification:**
Verified the fix by compiling the Python file manually (`python -m py_compile`) and running the full pytest test suite on the backend services (`pytest tests/services/`) without any regressions or test failures.

✨ **Result:**
The `CTraderFixConfig` is now simpler, cleaner, easier to instantiate, and leverages standard Python data modeling constructs without altering the functionality.
