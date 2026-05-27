## 2024-05-24 - Async non-blocking file I/O for Journal Logger
**Learning:** Synchronous file I/O operations (`open(...).write()`) within `async def` API routes block the event loop and serialize concurrent requests, destroying throughput in async Python frameworks (like FastAPI).
**Action:** Use `await asyncio.to_thread(func)` to offload synchronous, blocking standard library operations out of the main thread to maintain ultra-low latency.

## 2024-05-24 - Async non-blocking file I/O for Journal Logger
**Learning:** Synchronous file I/O operations (`open(...).write()`) within `async def` API routes block the event loop and serialize concurrent requests, destroying throughput in async Python frameworks (like FastAPI).
**Action:** Use `await asyncio.to_thread(func)` to offload synchronous, blocking standard library operations out of the main thread to maintain ultra-low latency.
