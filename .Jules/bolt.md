
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
