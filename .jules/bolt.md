## 2026-05-28 - Fast API Sync I/O blocking Async endpoints
**Learning:** Calling synchronous networking or disk functions directly inside `async def` route handlers in FastAPI blocks the asyncio event loop and starves all other requests, creating massive performance degradation under concurrent load.
**Action:** When a sync method is required, wrap the call with `await asyncio.to_thread(sync_function, args...)` to offload to a worker thread pool, keeping the main loop unblocked.
