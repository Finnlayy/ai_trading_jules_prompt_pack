import numpy as np
import pytest

from app.services.json_utils import sanitize_for_json


def test_sanitize_native_types():
    assert sanitize_for_json(1) == 1
    assert sanitize_for_json(1.5) == 1.5
    assert sanitize_for_json(True) is True
    assert sanitize_for_json(False) is False
    assert sanitize_for_json("test") == "test"
    assert sanitize_for_json(None) is None

def test_sanitize_numpy_booleans():
    assert sanitize_for_json(np.bool_(True)) is True
    assert sanitize_for_json(np.bool_(False)) is False
    assert type(sanitize_for_json(np.bool_(True))) is bool

def test_sanitize_numpy_integers():
    int64_val = np.int64(42)
    int32_val = np.int32(-10)

    sanitized_64 = sanitize_for_json(int64_val)
    sanitized_32 = sanitize_for_json(int32_val)

    assert sanitized_64 == 42
    assert type(sanitized_64) is int

    assert sanitized_32 == -10
    assert type(sanitized_32) is int

def test_sanitize_numpy_floats():
    float64_val = np.float64(3.14)
    float32_val = np.float32(-2.5)

    sanitized_64 = sanitize_for_json(float64_val)
    sanitized_32 = sanitize_for_json(float32_val)

    assert sanitized_64 == 3.14
    assert type(sanitized_64) is float

    assert sanitized_32 == -2.5
    assert type(sanitized_32) is float

def test_sanitize_numpy_arrays():
    arr_1d = np.array([1, 2, 3])
    sanitized_1d = sanitize_for_json(arr_1d)
    assert sanitized_1d == [1, 2, 3]
    assert type(sanitized_1d) is list

    arr_2d = np.array([[1.1, 2.2], [3.3, 4.4]])
    sanitized_2d = sanitize_for_json(arr_2d)
    assert sanitized_2d == [[1.1, 2.2], [3.3, 4.4]]
    assert type(sanitized_2d) is list
    assert type(sanitized_2d[0]) is list

def test_sanitize_nested_dict():
    nested_dict = {
        "int": np.int64(1),
        "float": np.float32(2.5),
        "bool": np.bool_(True),
        "array": np.array([1, 2, 3]),
        "nested": {
            "inner_int": np.int32(10)
        }
    }

    expected = {
        "int": 1,
        "float": 2.5,
        "bool": True,
        "array": [1, 2, 3],
        "nested": {
            "inner_int": 10
        }
    }

    sanitized = sanitize_for_json(nested_dict)
    assert sanitized == expected
    assert type(sanitized["int"]) is int
    assert type(sanitized["float"]) is float
    assert type(sanitized["bool"]) is bool
    assert type(sanitized["array"]) is list
    assert type(sanitized["nested"]["inner_int"]) is int

def test_sanitize_nested_lists_and_tuples():
    nested_list = [np.int64(1), [np.float32(2.5)], (np.bool_(True), np.array([1, 2]))]

    expected = [1, [2.5], [True, [1, 2]]]

    sanitized = sanitize_for_json(nested_list)
    assert sanitized == expected
    assert type(sanitized[0]) is int
    assert type(sanitized[1][0]) is float
    assert type(sanitized[2][0]) is bool
    assert type(sanitized[2][1]) is list
