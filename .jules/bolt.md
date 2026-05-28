## 2024-05-28 - Inefficient File I/O in Property Access
**Learning:** `get_memory()` method in `AILayerMemoryStore` called `_load_state()`, performing synchronous file I/O on every access, causing significant delays.
**Action:** Implement memory caching in `_load_state()` and update the cache in `_save_state()`. This prevents file reads on each access, improving speed significantly (from ~0.21s to ~0.02s for 1000 calls). Keep tests and linting functional.

## 2024-05-28 - Inefficient File I/O in Property Access
**Learning:** `get_memory()` method in `AILayerMemoryStore` called `_load_state()`, performing synchronous file I/O on every access, causing significant delays.
**Action:** Implement memory caching in `_load_state()` and update the cache in `_save_state()`. This prevents file reads on each access, improving speed significantly (from ~0.21s to ~0.02s for 1000 calls). Keep tests and linting functional.
## 2026-05-28 - Fast API Sync I/O blocking Async endpoints
**Learning:** Calling synchronous networking or disk functions directly inside `async def` route handlers in FastAPI blocks the asyncio event loop and starves all other requests, creating massive performance degradation under concurrent load.
**Action:** When a sync method is required, wrap the call with `await asyncio.to_thread(sync_function, args...)` to offload to a worker thread pool, keeping the main loop unblocked.
