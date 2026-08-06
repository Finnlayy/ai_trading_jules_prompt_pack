import json
import pytest
from datetime import datetime, date
from app.core.utils import json_dumps, json_dumps_default

class MockToDict:
    def to_dict(self):
        return {"mock": "to_dict"}

class MockModelDump:
    def model_dump(self):
        return {"mock": "model_dump"}

class MockStrOnly:
    def __str__(self):
        return "mock_str"

def test_json_dumps_standard_types():
    data = {"str": "hello", "int": 1, "bool": True, "list": [1, 2], "none": None}
    result = json_dumps(data)
    assert json.loads(result) == data

def test_json_dumps_datetime():
    dt = datetime(2023, 1, 1, 12, 0, 0)
    result = json_dumps({"dt": dt})
    assert json.loads(result) == {"dt": "2023-01-01T12:00:00"}

def test_json_dumps_date():
    d = date(2023, 1, 1)
    result = json_dumps({"d": d})
    assert json.loads(result) == {"d": "2023-01-01"}

def test_json_dumps_to_dict():
    obj = MockToDict()
    result = json_dumps({"obj": obj})
    assert json.loads(result) == {"obj": {"mock": "to_dict"}}

def test_json_dumps_model_dump():
    obj = MockModelDump()
    result = json_dumps({"obj": obj})
    assert json.loads(result) == {"obj": {"mock": "model_dump"}}

def test_json_dumps_str_fallback():
    obj = MockStrOnly()
    result = json_dumps({"obj": obj})
    assert json.loads(result) == {"obj": "mock_str"}

def test_json_dumps_kwargs():
    data = {"a": 1}
    result = json_dumps(data, indent=4)
    assert result == '{\n    "a": 1\n}'

def test_json_dumps_override_default():
    def custom_default(obj):
        return "custom"

    obj = MockStrOnly()
    result = json_dumps({"obj": obj}, default=custom_default)
    assert json.loads(result) == {"obj": "custom"}
