<<<<<<< HEAD
1. **Create and implement tests in `tests/core/test_utils.py`**
   - Use `run_in_bash_session` with `cat << 'EOF' > tests/core/test_utils.py` to create the test file and implement test cases for the utility functions defined in `app/core/utils.py`.
   - Implement tests for `strip_html` covering normal strings, HTML tags, multiple tags, and `None`.
   - Implement tests for `json_dumps_default` and `json_dumps` testing objects with `isoformat`, `to_dict`, `model_dump`, and fallback behavior.
   - Implement tests for `write_json_async` and `append_jsonl_async` using pytest's `tmp_path` fixture and `pytest.mark.asyncio`.
   - Implement tests for `execute_with_db` mocking `app.db.get_db` to yield a dummy session.
   - Implement tests for `iso_from_pubdate` covering valid dates (with GMT and +0000), ISO dates without timezone, and invalid formats.
2. **Execute tests**
   - Use `run_in_bash_session` to execute `python -m pytest tests/core/test_utils.py` to ensure the new tests pass and catch any regressions.
3. **Complete pre-commit steps**
   - Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.
4. **Submit the PR**
   - Create a PR with the title "🧪 Add tests for app/core/utils.py" and the correct description format.
=======
1. **Enhance Test Coverage for `app/schemas/ai_layer.py`:**
   - Modify `tests/schemas/test_ai_layer.py` to cover all schemas (`AIBehaviorProfile`, `AIChatMessage`, `AIChatRequest`, `AIChatResponse`).
   - Add specific tests for validation rules (e.g. `max_risk_pct > 0.0`, `min_confluence_preference` constraints).
   - Ensure the `utc_now` helper function behaves properly across defaults.
2. **Run Tests to Verify:**
   - Run `python -m pytest tests/schemas/test_ai_layer.py`
3. **Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.**
4. **Create PR description & Submit:**
   - Commit changes and submit a PR properly formatted as a testing improvement PR.
>>>>>>> main
