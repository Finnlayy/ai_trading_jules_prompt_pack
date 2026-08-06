🎯 What: Added tests to cover `json_dumps` and its default handler `json_dumps_default` in `app/core/utils.py`.
📊 Coverage: Covered standard data types, classes with `isoformat`, `to_dict`, and `model_dump` methods, fallback objects (to `str`), `kwargs` passing, and explicitly providing an overriding `default` argument.
✨ Result: Improved test coverage significantly on a pure function handling JSON serialization, guarding against regression.
