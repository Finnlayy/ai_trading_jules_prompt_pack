import pytest
from datetime import datetime, timezone
from pydantic import BaseModel
from app.core.utils import json_dumps_default

def test_json_dumps_default_datetime():
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    result = json_dumps_default(dt)
    assert result == "2023-01-01T12:00:00+00:00"

def test_json_dumps_default_to_dict():
    class CustomDictObj:
        def to_dict(self):
            return {"key": "value"}

    obj = CustomDictObj()
    result = json_dumps_default(obj)
    assert result == {"key": "value"}

def test_json_dumps_default_model_dump():
    class CustomModel(BaseModel):
        name: str
        age: int

    obj = CustomModel(name="test", age=30)
    result = json_dumps_default(obj)
    assert result == {"name": "test", "age": 30}

def test_json_dumps_default_fallback():
    class CustomObj:
        def __str__(self):
            return "custom_string_representation"

    obj = CustomObj()
    result = json_dumps_default(obj)
    assert result == "custom_string_representation"

def test_json_dumps_default_unhandled_type():
    # Built-in types that aren't natively serializable by json (though typically json handles them before hitting default)
    # the function just calls str() on them
    obj = object()
    result = json_dumps_default(obj)
    assert result == str(obj)
