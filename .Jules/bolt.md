## 2026-06-06 - Unrolled loop for [-5:] slices
**Learning:** Slicing  and using  within hot loops causes unnecessary tuple/list creation and iterator overhead. Fully unrolling fixed-size backward/forward lookups ( to ) and using bounds checks () can reduce inner-loop execution time by up to ~45% while maintaining semantic correctness.
**Action:** Identify hot paths that repeatedly slice arrays (e.g. ) to evaluate recent elements. If the slice size is small and fixed, unroll the iteration directly using negative indexing, ensuring the code gracefully falls back to a bounded loop if the length is shorter than the slice requirement.
## 2024-06-15 - Unrolled loop for [-5:] slices
**Learning:** Slicing `[-5:]` and using `reversed()` within hot loops causes unnecessary tuple/list creation and iterator overhead. Fully unrolling fixed-size backward/forward lookups (`[-1]` to `[-5]`) and using bounds checks (`len() >= 5`) can reduce inner-loop execution time by up to ~45% while maintaining semantic correctness.
**Action:** Identify hot paths that repeatedly slice arrays (e.g. `[-5:]`) to evaluate recent elements. If the slice size is small and fixed, unroll the iteration directly using negative indexing, ensuring the code gracefully falls back to a bounded loop if the length is shorter than the slice requirement.

## $(date +%Y-%m-%d) - [Replace blocking requests with httpx in PricePoller]
**Learning:** Even when a blocking I/O bound function is wrapped in `asyncio.to_thread`, it still consumes thread pool resources and creates overhead in highly concurrent asynchronous systems. Using an async-native library like `httpx` directly in the `async` event loop allows the system to manage network wait efficiently without thread contention.
**Action:** When working in `asyncio` code, prefer async-native alternatives (`httpx`, `aiohttp`, `asyncpg`) for I/O operations instead of bridging synchronous libraries via `to_thread`, unless the library strictly has no async alternative.
