I plan to add test coverage for `app/schemas/ai_layer.py` since it currently has untested functions, specifically `utc_now`.

The plan is:
1. Create/update `tests/schemas/test_ai_layer.py`
2. Add test cases for `utc_now` to ensure it returns ISO 8601 strings in UTC.
3. Add test cases for `AIBehaviorProfile` to ensure default values and constraints (like `max_risk_pct > 0.0`) are enforced correctly.
4. Add test cases for `AIChatMessage`, `AIChatRequest`, and `AIChatResponse` to ensure they can be instantiated properly and validators work as expected.
5. Run the full test suite with pytest.
6. Commit the changes.
