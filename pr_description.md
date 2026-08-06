🎯 **What:**
Added comprehensive testing for the schemas and utilities located in `app/schemas/ai_layer.py`. Prior to this change, the simple and stateless schema utilities lacked coverage, particularly the `utc_now` helper function and default value constraints.

📊 **Coverage:**
The new test suite in `tests/schemas/test_ai_layer.py` covers the following:
- `utc_now`: Verified to return ISO-formatted timestamps with valid UTC timezones.
- `AIBehaviorProfile`: Validated default initialization, value bounds for `max_risk_pct` (>0.0), and `min_confluence_preference` (0.0 - 100.0).
- `AIChatMessage`: Verified defaults and constraints on valid role literal assignments.
- `AIChatRequest`: Checked message length limits and bounded `bars_count` properties.
- `AIChatResponse`: Assessed base schema instantiations ensuring valid typing cascades.

✨ **Result:**
Improved schema testing reliability across `ai_layer`, increasing full test suite coverage and helping confidently prevent future regression issues regarding payload parsing boundaries.
