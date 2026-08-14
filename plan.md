1. **Enhance Test Coverage for `app/schemas/ai_layer.py`:**
   - Modify `tests/schemas/test_ai_layer.py` to cover all schemas (`AIBehaviorProfile`, `AIChatMessage`, `AIChatRequest`, `AIChatResponse`).
   - Add specific tests for validation rules (e.g. `max_risk_pct > 0.0`, `min_confluence_preference` constraints).
   - Ensure the `utc_now` helper function behaves properly across defaults.
2. **Run Tests to Verify:**
   - Run `python -m pytest tests/schemas/test_ai_layer.py`
3. **Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.**
4. **Create PR description & Submit:**
   - Commit changes and submit a PR properly formatted as a testing improvement PR.
