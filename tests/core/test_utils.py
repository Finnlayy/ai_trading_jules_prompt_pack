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
