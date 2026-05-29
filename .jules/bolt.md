## 2024-05-28 - Inefficient File I/O in Property Access
**Learning:** `get_memory()` method in `AILayerMemoryStore` called `_load_state()`, performing synchronous file I/O on every access, causing significant delays.
**Action:** Implement memory caching in `_load_state()` and update the cache in `_save_state()`. This prevents file reads on each access, improving speed significantly (from ~0.21s to ~0.02s for 1000 calls). Keep tests and linting functional.

## 2024-05-28 - Inefficient File I/O in Property Access
**Learning:** `get_memory()` method in `AILayerMemoryStore` called `_load_state()`, performing synchronous file I/O on every access, causing significant delays.
**Action:** Implement memory caching in `_load_state()` and update the cache in `_save_state()`. This prevents file reads on each access, improving speed significantly (from ~0.21s to ~0.02s for 1000 calls). Keep tests and linting functional.
## 2026-05-28 - Fast API Sync I/O blocking Async endpoints
**Learning:** Calling synchronous networking or disk functions directly inside `async def` route handlers in FastAPI blocks the asyncio event loop and starves all other requests, creating massive performance degradation under concurrent load.
**Action:** When a sync method is required, wrap the call with `await asyncio.to_thread(sync_function, args...)` to offload to a worker thread pool, keeping the main loop unblocked.
## 2024-05-29 - Inefficient Statistical Baseline Recalculation inside Tight Loops
**Learning:** The Ljung-Box test function (`ljung_box`) inside `app/services/statistical_battery.py` repeatedly called `_autocorr`, which recalculated the array's mean and variance (`c0`) for every single lag (e.g. 20 times for 20 lags).
**Action:** Inline the autocorrelation logic inside `ljung_box` to compute the mean, centered array, and variance once outside the loop. Then iteratively compute only the specific lag's covariance inside the loop, effectively halving the computation time (~0.20s down to ~0.10s for 100 runs). This avoids redundant O(N) operations inside loops.
## 2024-06-25 - Python memory allocations in high-frequency calculations
**Learning:** For performance-critical arrays (like calculating metric indicators on millions of tick/candle returns), native python `sum()` over unrolled arrays or explicit tracking counters can be ~4x faster than list comprehensions because it avoids creating intermediate large list objects and overhead associated with Python generators.
**Action:** When working on backends analyzing large series or arrays of returns in Python where external dependencies like numpy aren't immediately available, prefer explicitly unrolled loop structures and native mathematical reductions over memory-intensive generator comprehensions.
