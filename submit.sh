#!/bin/bash
git checkout -b fix/test-json-utils
git add tests/services/test_json_utils.py
git commit -m "🧪 [testing improvement] Add comprehensive tests for json_utils

🎯 What: The testing gap addressed for sanitize_for_json in app/services/json_utils.py.
📊 Coverage: Covered Numpy scalar types (int64, int32, float64, float32, bool_), numpy arrays, native python types, and deeply nested structures (lists, dicts, tuples).
✨ Result: 100% test coverage of the function ensuring all JSON serialization edge cases convert safely."
