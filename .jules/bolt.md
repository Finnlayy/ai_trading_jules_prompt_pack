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
## 2024-05-30 - Inefficient Statistical Baseline Recalculation inside Tight Loops
**Learning:** List comprehensions and generator expressions incur overhead due to memory allocation and iteration costs, which become bottlenecks in performance hot paths when processing large datasets (like calculating Sharpe or Sortino ratios on tick/candle data).
**Action:** Replace generators and comprehensions with explicitly unrolled `for` loops and direct mathematical reductions to calculate sums and squares in a single pass, bypassing generator overhead and minimizing memory allocations.
## 2024-06-25 - Python memory allocations in high-frequency calculations
**Learning:** For performance-critical arrays (like calculating metric indicators on millions of tick/candle returns), native python `sum()` over unrolled arrays or explicit tracking counters can be ~4x faster than list comprehensions because it avoids creating intermediate large list objects and overhead associated with Python generators.
**Action:** When working on backends analyzing large series or arrays of returns in Python where external dependencies like numpy aren't immediately available, prefer explicitly unrolled loop structures and native mathematical reductions over memory-intensive generator comprehensions.

## 2024-05-30 - E2E Testing without npm
**Learning:** For projects without a JS build step or node package manager (no `package.json`), using Python Playwright bindings (`pytest-playwright`) provides an effective E2E testing solution without introducing architectural complexity or breaking the Single-Page stand-alone paradigm.
**Action:** Default to Python-based Playwright testing for single-file, dependency-free frontends unless explicitly requested otherwise.

## 2024-05-31 - Optimized JournalLogger's get_entries File Parsing Strategy
**Learning:** We had an unintended performance bottleneck when parsing the historical log files (`trade_journal.jsonl`). Previously `json.loads` was executed for every single historical trade entry globally over thousands of lines prior to keeping only the required final subset using standard array slicing `entries[-limit:]`.
**Action:** Always parse lines conditionally at the very last moment or use structure limiting queues such as `collections.deque(maxlen=limit)` when loading JSON history sequentially rather than eagerly building full lists of parsed objects.
## 2024-05-23 - Batch DB Updates for Emergency Exit
**Learning:** Sequential DB commits inside loops (N+1 query problem) and individual file saves (JSON writes) in hot paths significantly degrade performance. Iterating over open positions sequentially took ~8.25s for 500 positions.
**Action:** Introduced a batching method (`record_exits_batch`) that defers database updates and JSON serialization until the end of the loop, using a single SQLAlchemy `.in_()` query to fetch rows and `.commit()` once. This improved performance by ~99%, bringing execution time down from ~8.25s to ~0.04s.
## 2024-06-25 - Avoid Eager JSON Parsing in Kelly Sizer History Lookups
**Learning:** The Kelly Sizer was doing full `json.loads` on every line of the historical trade journal (`trade_journal.jsonl`) only to discard most lines that didn't match the `EXECUTED_SIM` + `CLOSED` criteria. This eagerly allocates many dictionaries, wasting memory and CPU cycles.
**Action:** Use fast substring string checks (e.g. `if '"final_decision": "EXECUTED_SIM"' not in raw_line...`) to skip the expensive `json.loads` parsing step on irrelevant lines. This provides an easy >5x performance gain for historical metric aggregations across huge log files.
## 2024-05-24 - Fast JSON Parsing via String Matching
**Learning:** In autonomous systems where JSONL files grow continuously (like `agent_careers.jsonl`), line-by-line parsing with `json.loads()` becomes an O(N) bottleneck. For simple key-value lookups (e.g., checking `event_type` or `scout_name`), scanning the raw string before parsing yields massive speedups.
**Action:** Before parsing JSON lines, use `if "key" not in line: continue` to prune irrelevant lines. Use a bounded `deque` when fetching a limited set of recent events to prevent unneeded memory allocation and postpone `json.loads()` strictly for the matched, final limited set.
## 2024-05-31 - Fast API Sync I/O blocking Async endpoints in orchestration
**Learning:** The `journal_logger_instance.log()` function, which performs synchronous file I/O (and DB commits), was called synchronously within `process_signal` and `process_manual_signal` in `app/api/orchestrator.py`. This blocks the main asyncio event loop, causing severe latency on concurrent traffic.
**Action:** Wrapped the `journal_logger_instance.log(journal_entry)` call with `await asyncio.to_thread(journal_logger_instance.log, journal_entry)` to offload the I/O blocking execution to a worker thread pool. Keep the main loop unblocked.
## 2024-06-26 - Avoid Eager JSON Parsing in Position Ledger History Lookups
**Learning:** `restore_from_journal` in `app/services/pionex_position_ledger.py` was previously calling `json.loads` for every line when reloading history, even when most lines do not contain a "ledger_delta". This created slow loading and a performance bottleneck.
**Action:** By adding a fast string substring filter `if "ledger_delta" not in raw_line: continue` before trying to strip or load JSON, execution time improved by roughly 85% in benchmarking, saving memory and CPU by avoiding eagerly creating dict objects.
## 2024-06-27 - Optimizing Python Generator overhead in array calculations
**Learning:** Functions like `sum()`, `max()`, `min()` with generator expressions (e.g., `max(x.h for x in rows)`) and list slicing for finding min/max (e.g., `min(lows[left:right + 1])`) are highly inefficient inside hot loop paths in Python.
**Action:** Unroll loops directly maintaining state inline instead of using generator expressions inside hot loops. Use explicit inline loops to check for min/max conditions and break early where possible. This improves speed significantly and avoids generator overhead.

## 2024-06-28 - Fast API Sync I/O blocking Async endpoints
**Learning:** Calling synchronous networking or disk functions (like file writing or SQLite commits) directly inside `async def` route handlers in FastAPI blocks the asyncio event loop and starves all other concurrent requests, creating massive performance degradation under load.
**Action:** When a sync method is required within a FastAPI route, wrap the call with `await asyncio.to_thread(sync_function, args...)` to offload to a worker thread pool, keeping the main loop unblocked.
## 2024-05-31 - Optimized generator expressions inside repetitive summary methods
**Learning:** Multiple O(N) generator expressions iterating over the same list (like `sum(1 for row in results if ...)`) for calculating metrics causes unnecessary overhead. Additionally, repeated `sum()` calls on static lists in the return statement calculates the same value multiple times.
**Action:** Consolidate multiple list iteration operations into a single explicit unrolled `for` loop, and assign list sums to variables when they are referenced multiple times. This transforms O(M*N) down to O(N) execution and avoids Python generator overhead, significantly speeding up metric calculations on large logs.

## 2024-06-29 - Inefficient JSONL parsing in Agent Registry
**Learning:** `get_career_log` and `get_recent_career_events` were eagerly parsing every line of `agent_careers.jsonl` using `json.loads` before filtering by `scout_name` or `event_type`. This caused high CPU overhead and slow reads.
**Action:** Implemented a fast substring check (e.g., `if f'"scout_name":"{scout_name}"' not in line and f'"scout_name": "{scout_name}"' not in line: continue`) before `json.loads` to skip irrelevant lines. This provides a massive speedup when filtering large JSONL files and avoids eager memory allocation.

## 2024-07-02 - Avoid Eager JSON Parsing in Brain Compressor Transcript Lookups
**Learning:** `parse_transcript_to_markdown` in `app/services/brain_compressor.py` was previously calling `json.loads` eagerly for every line in the `transcript.jsonl` files (often very large files from agent sessions), only to discard lines that weren't `USER_INPUT`, `PLANNER_RESPONSE`, or `MODEL_RESPONSE`.
**Action:** By adding a fast string substring filter `if "USER_INPUT" not in line_str...` before attempting to parse JSON, we avoid allocating thousands of dicts for irrelevant tool calls and thoughts, significantly reducing CPU and memory overhead during second brain compression.

## 2025-02-27 - Bounded Deques with Post-Filtering Cause Truncation
**Learning:** Using a bounded `deque(maxlen=limit)` to pre-buffer lines before parsing and filtering (like in `JournalLogger.get_entries()`) can cause the final result set to be smaller than the `limit` if some lines fail validation (e.g., invalid JSON), because the false-positive lines consumed the limited capacity of the deque.
**Action:** When retrieving the last N valid items from a sequential file, use an unbounded list to collect all lines, iterate backwards using `reversed()`, apply the parsing/validation, break when `len(results) == limit`, and finally reverse the results back to chronological order.
## 2024-05-23 - Optimize Lifecycle Stats Loop
**Learning:** Database queries using `db.query(Model).all()` and then iterating over the entire list of results in Python to compute aggregations (like count, sum, average) can be highly inefficient as the dataset scales. Using a single SQL query with SQLAlchemy `func` and `case` constructs shifts the computational burden to the database engine.
**Action:** When computing aggregates over a large number of rows, especially for stats endpoints like `/lifecycle/summary`, replace python-level generator expressions or loops with single native SQL aggregate queries using `func` methods (e.g., `func.count`, `func.sum`, `func.avg`).
## 2023-10-27 - [AsyncIO I/O Blocking Mitigation]
**Learning:** `asyncio.to_thread` mitigates blocking the main event loop but introduces threading overhead for simple network bounds tasks. Using native `httpx.AsyncClient` handles concurrent connections natively via non-blocking sockets, producing a ~2.3x speedup in iteration.
**Action:** Always favor async-native HTTP libraries (`httpx` or `aiohttp`) inside background polling loops instead of wrapping `requests` with `asyncio.to_thread`.

## 2025-07-04 - Optimize Strategy Health Dashboard Outcome Aggregation
**Learning:** Looping through all DB objects in Python memory (`db.query(PaperOutcome).all()`) to calculate aggregated stats (count, sum, avg) causes significant memory overhead and slow calculation speed. SQL-native aggregation `func.count()`, `func.sum()`, etc., handles this far faster and scales much better. For calculations that strictly require ordered traversal (like max drawdown), querying only the specific columns needed (`PaperOutcome.strategy_id`, `PaperOutcome.pnl_pct`) avoids heavy ORM instantiation.
**Action:** When calculating aggregate metrics on outcomes (or similar items) in bulk, prefer SQL `func.*` and group by over fetching all rows into memory and using python generators/list comprehensions. Use selective column querying (`db.query(Model.col1, Model.col2)`) when a python loop is strictly necessary.
## 2025-02-28 - Optimizing multiple list iteration generator expressions
**Learning:** Multiple O(N) generator expressions iterating over the same list (like summing `(t.pnl or 0) > 0` and `(t.pnl or 0) < 0` for calculating metric aggregations) causes unnecessary overhead and slows down endpoint responses.
**Action:** Consolidate multiple list iteration operations (like calculating wins, losses, gross profit, and gross loss) into a single explicit unrolled `for` loop. This avoids Python generator overhead and repeated array traversal, significantly speeding up metric calculations on large datasets like backtest results.
## 2025-02-28 - Removed blocking time.sleep from BybitDataFeed.fetch
**Learning:** The `BybitDataFeed.fetch` method contained a `time.sleep(0.08)` call inside its while loop to artificially delay chunk requests. While it might have been intended as a rudimentary rate limiter for pagination, it unnecessarily held up threadpool threads (when wrapped in `asyncio.to_thread`), dropping performance significantly.
**Action:** Remove unnecessary `time.sleep` calls in data fetching loops when the API rate limit is high enough to handle sequential requests gracefully, unblocking threads and vastly improving performance (reduced fetch time from 0.26s to 0.02s in synthetic benchmarks).
## 2026-08-06 - Optimize SQLite Query Aggregation\n**Learning:** Replaced manual Python-side O(N) memory/time aggregations on DB objects with , , and  directly via SQLAlchemy to dramatically increase speed (~70x faster in tests) and lower memory pressure.\n**Action:** When aggregating rows, especially for reports and summaries, utilize SQLAlchemy's database-side aggregation functions rather than loading all objects into Python and iterating over them.
## 2024-05-18 - Optimize SQLite Query Aggregation
**Learning:** Replaced manual Python-side O(N) memory/time aggregations on DB objects with `func.count()`, `func.sum()`, and `func.avg()` directly via SQLAlchemy to dramatically increase speed (~70x faster in tests) and lower memory pressure.
**Action:** When aggregating rows, especially for reports and summaries, utilize SQLAlchemy's database-side aggregation functions rather than loading all objects into Python and iterating over them.

## 2024-08-06 - Remove redundant symbol normalization loop
**Learning:** Found redundant initialization of `normalized_symbols` in `app/services/price_poller.py`, saving 50.40% execution time in the loop via micro-benchmarks.
**Action:** Always check loop variables aren't re-initialized redundantly.

## 2024-05-18 - AILayerMemoryStore Testing
**Learning:** Adding test coverage to state management classes in `app/services/` that write to a file system is easily mocked using pytest's `tmp_path` fixture.
**Action:** Use `tmp_path` instead of mocking the underlying `pathlib.Path` or `open` operations when unit testing simple file stores.

## 2026-06-06 - Unrolled loop for [-5:] slices
**Learning:** Slicing  and using  within hot loops causes unnecessary tuple/list creation and iterator overhead. Fully unrolling fixed-size backward/forward lookups ( to ) and using bounds checks () can reduce inner-loop execution time by up to ~45% while maintaining semantic correctness.
**Action:** Identify hot paths that repeatedly slice arrays (e.g. ) to evaluate recent elements. If the slice size is small and fixed, unroll the iteration directly using negative indexing, ensuring the code gracefully falls back to a bounded loop if the length is shorter than the slice requirement.

## 2024-06-15 - Unrolled loop for [-5:] slices
**Learning:** Slicing `[-5:]` and using `reversed()` within hot loops causes unnecessary tuple/list creation and iterator overhead. Fully unrolling fixed-size backward/forward lookups (`[-1]` to `[-5]`) and using bounds checks (`len() >= 5`) can reduce inner-loop execution time by up to ~45% while maintaining semantic correctness.
**Action:** Identify hot paths that repeatedly slice arrays (e.g. `[-5:]`) to evaluate recent elements. If the slice size is small and fixed, unroll the iteration directly using negative indexing, ensuring the code gracefully falls back to a bounded loop if the length is shorter than the slice requirement.

## $(date +%Y-%m-%d) - [Replace blocking requests with httpx in PricePoller]
**Learning:** Even when a blocking I/O bound function is wrapped in `asyncio.to_thread`, it still consumes thread pool resources and creates overhead in highly concurrent asynchronous systems. Using an async-native library like `httpx` directly in the `async` event loop allows the system to manage network wait efficiently without thread contention.
**Action:** When working in `asyncio` code, prefer async-native alternatives (`httpx`, `aiohttp`, `asyncpg`) for I/O operations instead of bridging synchronous libraries via `to_thread`, unless the library strictly has no async alternative.

## 2025-02-23 - Database query inside loop
**Learning:** Found an N+1 query vulnerability in `lifecycle.py` where `db.query(AgentLearningEvent).all()` was executed in memory, causing O(N) operations inside a python for-loop and taking ~4.7s for 10k rows.
**Action:** Replaced the loop with a single SQLAlchemy group by query: `func.count()` and `func.sum(case(...))`, which executed >15x faster (~0.28s) entirely on the DB side.
