import pytest
from app.core.config import (
    _as_bool,
    _as_float,
    _as_optional_float,
    _as_int,
    _as_csv_list,
)

def test_as_bool():
    assert _as_bool(None) is False
    assert _as_bool(None, default=True) is True

    # Truthy values
    assert _as_bool("1") is True
    assert _as_bool("true") is True
    assert _as_bool("TRUE") is True
    assert _as_bool("yes") is True
    assert _as_bool("on") is True

    # Falsy values
    assert _as_bool("0") is False
    assert _as_bool("false") is False
    assert _as_bool("no") is False
    assert _as_bool("off") is False
    assert _as_bool("random_string") is False
    assert _as_bool("") is False

def test_as_float():
    assert _as_float(None, 1.5) == 1.5
    assert _as_float("3.14", 1.5) == 3.14
    assert _as_float("10", 1.5) == 10.0
    assert _as_float("-2.5", 1.5) == -2.5

    # Error paths
    assert _as_float("invalid", 1.5) == 1.5
    assert _as_float("", 1.5) == 1.5

def test_as_optional_float():
    assert _as_optional_float(None) is None
    assert _as_optional_float("") is None
    assert _as_optional_float("   ") is None

    # Valid values
    assert _as_optional_float("3.14") == 3.14
    assert _as_optional_float("10") == 10.0

    # Error paths
    assert _as_optional_float("invalid") is None

def test_as_int():
    assert _as_int(None, 42) == 42
    assert _as_int("100", 42) == 100
    assert _as_int("-5", 42) == -5

    # Error paths (invalid for int, but float string falls back to default because int("3.14") raises ValueError)
    assert _as_int("invalid", 42) == 42
    assert _as_int("3.14", 42) == 42
    assert _as_int("", 42) == 42

def test_as_csv_list():
    assert _as_csv_list(None) == []
    assert _as_csv_list("") == []

    # Valid paths
    assert _as_csv_list("a,b,c") == ["A", "B", "C"]
    assert _as_csv_list(" a , b , c ") == ["A", "B", "C"]
    assert _as_csv_list("AAPL,MSFT") == ["AAPL", "MSFT"]

    # Empty parts are ignored
    assert _as_csv_list("a,,c") == ["A", "C"]
    assert _as_csv_list("a,  ,c") == ["A", "C"]
