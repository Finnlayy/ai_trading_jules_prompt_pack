## 2024-05-28 - Inefficient File I/O in Property Access
**Learning:** `get_memory()` method in `AILayerMemoryStore` called `_load_state()`, performing synchronous file I/O on every access, causing significant delays.
**Action:** Implement memory caching in `_load_state()` and update the cache in `_save_state()`. This prevents file reads on each access, improving speed significantly (from ~0.21s to ~0.02s for 1000 calls). Keep tests and linting functional.

## 2024-05-28 - Inefficient File I/O in Property Access
**Learning:** `get_memory()` method in `AILayerMemoryStore` called `_load_state()`, performing synchronous file I/O on every access, causing significant delays.
**Action:** Implement memory caching in `_load_state()` and update the cache in `_save_state()`. This prevents file reads on each access, improving speed significantly (from ~0.21s to ~0.02s for 1000 calls). Keep tests and linting functional.
