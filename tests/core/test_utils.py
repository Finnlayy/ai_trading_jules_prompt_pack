<<<<<<< HEAD
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
=======
<<<<<<< HEAD
import asyncio
import json
import os
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock, patch

from app.core.utils import (
    strip_html,
    json_dumps_default,
    json_dumps,
    write_json_async,
    append_jsonl_async,
    execute_with_db,
    iso_from_pubdate
)

def test_strip_html():
    assert strip_html("<div>Hello</div>") == "Hello"
    assert strip_html("<p>Paragraph</p>") == "Paragraph"
    assert strip_html("No tags here") == "No tags here"
    assert strip_html(None) == ""
    assert strip_html("") == ""
    assert strip_html("<span><bold>Multiple</bold></span>") == "Multiple"
    assert strip_html("<a href='http://example.com'>Link</a>") == "Link"
    assert strip_html("A < B") == "A" # Simple test, actually strip_html logic makes it "A " because in_tag becomes true at < and never false since there is no >. Let's see: for ch in "A < B": "A " ... < in_tag=True, space, B ... returns "A "

class DummyIsoFormat:
    def isoformat(self):
        return "2023-01-01T00:00:00Z"

class DummyToDict:
    def to_dict(self):
        return {"key": "value"}

class DummyModelDump:
    def model_dump(self):
        return {"dump": "data"}

class DummyStr:
    def __str__(self):
        return "dummy_string"

def test_json_dumps_default():
    assert json_dumps_default(DummyIsoFormat()) == "2023-01-01T00:00:00Z"
    assert json_dumps_default(DummyToDict()) == {"key": "value"}
    assert json_dumps_default(DummyModelDump()) == {"dump": "data"}
    assert json_dumps_default(DummyStr()) == "dummy_string"
    assert json_dumps_default(123) == "123"

def test_json_dumps():
    # Test normal JSON serialization
    assert json_dumps({"a": 1}) == '{"a": 1}'
    # Test custom default handler
    payload = {"date": DummyIsoFormat(), "dict": DummyToDict()}
    expected = '{"date": "2023-01-01T00:00:00Z", "dict": {"key": "value"}}'
    assert json_dumps(payload) == expected

@pytest.mark.asyncio
async def test_write_json_async(tmp_path):
    filepath = tmp_path / "test.json"
    payload = {"foo": "bar"}
    await write_json_async(str(filepath), payload)

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data == payload

@pytest.mark.asyncio
async def test_append_jsonl_async(tmp_path):
    filepath = tmp_path / "test.jsonl"
    payload1 = {"id": 1}
    payload2 = {"id": 2}

    await append_jsonl_async(str(filepath), payload1)
    await append_jsonl_async(str(filepath), payload2)

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) == 2
    assert json.loads(lines[0]) == payload1
    assert json.loads(lines[1]) == payload2

def test_execute_with_db():
    mock_db = MagicMock()
    def mock_get_db():
        yield mock_db

    with patch("app.core.utils.get_db", side_effect=mock_get_db, create=True) as p1:
        # Actually in app/core/utils.py execute_with_db has `from app.db import get_db`
        # We need to mock app.db.get_db.
        pass

    with patch("app.db.get_db", side_effect=mock_get_db):
        def dummy_func(db, arg1, kwarg1=None):
            assert db is mock_db
            return f"Result {arg1} {kwarg1}"

        res = execute_with_db(dummy_func, "foo", kwarg1="bar")
        assert res == "Result foo bar"

def test_iso_from_pubdate():
    # Test valid GMT RSS date
    assert iso_from_pubdate("Mon, 06 Sep 2009 16:20:00 GMT") == "2009-09-06T16:20:00+00:00"

    # Test valid +0000 RSS date
    assert iso_from_pubdate("Mon, 06 Sep 2009 16:20:00 +0000") == "2009-09-06T16:20:00+00:00"

    # Test ISO date string (actually falls back to %Y-%m-%dT%H:%M:%S)
    assert iso_from_pubdate("2023-01-01T12:00:00Z") == "2023-01-01T12:00:00+00:00"

    # Test invalid string format
    assert iso_from_pubdate("Invalid Date String") == "Invalid Date String"
=======
import pytest
<<<<<<< HEAD
from unittest.mock import patch, MagicMock
from app.core.utils import execute_with_db

def test_execute_with_db_success():
    """Test execute_with_db successfully calls the function and closes the session."""
    mock_db = MagicMock()

    # We use a state dictionary to track the generator state instead of
    # setting attributes on a generator or function directly.
    state = {"closed": False}

    def mock_get_db():
        yield mock_db
        state["closed"] = True

    def sample_func(db, arg1, kwarg1=None):
        assert db is mock_db
        assert arg1 == "hello"
        assert kwarg1 == "world"
        return "success"

    # Patch the correct import location
    with patch("app.db.get_db", mock_get_db):
        result = execute_with_db(sample_func, "hello", kwarg1="world")

        assert result == "success"
        assert state["closed"] is True

def test_execute_with_db_exception():
    """Test execute_with_db properly closes the session even if an exception is raised."""
    mock_db = MagicMock()

    state = {"closed": False}

    def mock_get_db():
        yield mock_db
        state["closed"] = True

    def error_func(db):
        raise ValueError("Simulated error")

    # Patch the correct import location
    with patch("app.db.get_db", mock_get_db):
        with pytest.raises(ValueError, match="Simulated error"):
            execute_with_db(error_func)

        assert state["closed"] is True
=======
from app.core.utils import iso_from_pubdate

def test_iso_from_pubdate_rss_format():
    """Test standard RSS pubDate format."""
    text = "Mon, 06 Sep 2009 16:20:00 +0000"
    expected = "2009-09-06T16:20:00+00:00"
    assert iso_from_pubdate(text) == expected

def test_iso_from_pubdate_gmt_suffix():
    """Test RSS pubDate format with GMT suffix."""
    text = "Mon, 06 Sep 2009 16:20:00 GMT"
    expected = "2009-09-06T16:20:00+00:00"
    assert iso_from_pubdate(text) == expected

def test_iso_from_pubdate_iso_format():
    """Test standard ISO-like date string."""
    text = "2009-09-06T16:20:00"
    expected = "2009-09-06T16:20:00+00:00"
    assert iso_from_pubdate(text) == expected

def test_iso_from_pubdate_iso_format_with_trailing():
    """Test ISO-like date string with trailing chars (e.g., timezone/milliseconds)."""
    text = "2009-09-06T16:20:00.123Z"
    expected = "2009-09-06T16:20:00+00:00"
    assert iso_from_pubdate(text) == expected

def test_iso_from_pubdate_unparsable():
    """Test unparsable string fallback."""
    text = "unparsable date string"
    assert iso_from_pubdate(text) == text

def test_iso_from_pubdate_whitespace():
    """Test stripping whitespace."""
    text = "  Mon, 06 Sep 2009 16:20:00 +0000  "
    expected = "2009-09-06T16:20:00+00:00"
    assert iso_from_pubdate(text) == expected
>>>>>>> main
>>>>>>> main
>>>>>>> main
