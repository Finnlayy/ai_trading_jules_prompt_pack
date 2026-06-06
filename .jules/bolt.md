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

## 2024-05-30 - E2E Testing without npm
**Learning:** For projects without a JS build step or node package manager (no `package.json`), using Python Playwright bindings (`pytest-playwright`) provides an effective E2E testing solution without introducing architectural complexity or breaking the Single-Page stand-alone paradigm.
**Action:** Default to Python-based Playwright testing for single-file, dependency-free frontends unless explicitly requested otherwise.

## 2024-05-31 - Optimized JournalLogger's get_entries File Parsing Strategy
**Learning:** We had an unintended performance bottleneck when parsing the historical log files (`trade_journal.jsonl`). Previously `json.loads` was executed for every single historical trade entry globally over thousands of lines prior to keeping only the required final subset using standard array slicing `entries[-limit:]`.
**Action:** Always parse lines conditionally at the very last moment or use structure limiting queues such as `collections.deque(maxlen=limit)` when loading JSON history sequentially rather than eagerly building full lists of parsed objects.
## 2024-06-25 - Avoid Eager JSON Parsing in Kelly Sizer History Lookups
**Learning:** The Kelly Sizer was doing full `json.loads` on every line of the historical trade journal (`trade_journal.jsonl`) only to discard most lines that didn't match the `EXECUTED_SIM` + `CLOSED` criteria. This eagerly allocates many dictionaries, wasting memory and CPU cycles.
**Action:** Use fast substring string checks (e.g. `if '"final_decision": "EXECUTED_SIM"' not in raw_line...`) to skip the expensive `json.loads` parsing step on irrelevant lines. This provides an easy >5x performance gain for historical metric aggregations across huge log files.
## 2024-06-26 - Avoid Eager JSON Parsing in Position Ledger History Lookups
**Learning:** `restore_from_journal` in `app/services/pionex_position_ledger.py` was previously calling `json.loads` for every line when reloading history, even when most lines do not contain a "ledger_delta". This created slow loading and a performance bottleneck.
**Action:** By adding a fast string substring filter `if "ledger_delta" not in raw_line: continue` before trying to strip or load JSON, execution time improved by roughly 85% in benchmarking, saving memory and CPU by avoiding eagerly creating dict objects.
## 2024-06-27 - Optimizing Python Generator overhead in array calculations
**Learning:** Functions like `sum()`, `max()`, `min()` with generator expressions (e.g., `max(x.h for x in rows)`) and list slicing for finding min/max (e.g., `min(lows[left:right + 1])`) are highly inefficient inside hot loop paths in Python.
**Action:** Unroll loops directly maintaining state inline instead of using generator expressions inside hot loops. Use explicit inline loops to check for min/max conditions and break early where possible. This improves speed significantly and avoids generator overhead.

## 2024-06-28 - Fast API Sync I/O blocking Async endpoints
**Learning:** Calling synchronous networking or disk functions (like file writing or SQLite commits) directly inside `async def` route handlers in FastAPI blocks the asyncio event loop and starves all other concurrent requests, creating massive performance degradation under load.
**Action:** When a sync method is required within a FastAPI route, wrap the call with `await asyncio.to_thread(sync_function, args...)` to offload to a worker thread pool, keeping the main loop unblocked.
