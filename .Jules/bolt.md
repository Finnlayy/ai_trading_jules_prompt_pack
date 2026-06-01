
## 2024-05-18 - AILayerMemoryStore Testing
**Learning:** Adding test coverage to state management classes in `app/services/` that write to a file system is easily mocked using pytest's `tmp_path` fixture.
**Action:** Use `tmp_path` instead of mocking the underlying `pathlib.Path` or `open` operations when unit testing simple file stores.
