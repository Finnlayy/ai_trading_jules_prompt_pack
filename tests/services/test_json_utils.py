import numpy as np
<<<<<<< HEAD
from app.services.json_utils import sanitize_for_json

def test_sanitize_ndarray():
    arr = np.array([1, 2, 3])
    result = sanitize_for_json(arr)
    assert isinstance(result, list)
    assert result == [1, 2, 3]

def test_sanitize_bool():
    b1 = np.bool_(True)
    b2 = np.bool_(False)
    assert isinstance(sanitize_for_json(b1), bool)
    assert sanitize_for_json(b1) is True
    assert isinstance(sanitize_for_json(b2), bool)
    assert sanitize_for_json(b2) is False

def test_sanitize_integer():
    i1 = np.int64(42)
    i2 = np.int32(-10)
    res1 = sanitize_for_json(i1)
    res2 = sanitize_for_json(i2)
    assert isinstance(res1, int)
    assert res1 == 42
    assert isinstance(res2, int)
    assert res2 == -10

def test_sanitize_floating():
    f1 = np.float64(3.14)
    f2 = np.float32(-0.5)
    res1 = sanitize_for_json(f1)
    res2 = sanitize_for_json(f2)
    assert isinstance(res1, float)
    assert res1 == 3.14
    assert isinstance(res2, float)
    assert res2 == -0.5

def test_sanitize_dict():
    d = {
        "arr": np.array([1, 2]),
        "val": np.int64(100),
        "nested": {"bool_val": np.bool_(True)}
    }
    result = sanitize_for_json(d)
    assert isinstance(result, dict)
    assert isinstance(result["arr"], list)
    assert result["arr"] == [1, 2]
    assert isinstance(result["val"], int)
    assert result["val"] == 100
    assert isinstance(result["nested"], dict)
    assert isinstance(result["nested"]["bool_val"], bool)
    assert result["nested"]["bool_val"] is True

def test_sanitize_iterable():
    lst = [np.int64(1), np.float64(2.5)]
    tup = (np.bool_(False), np.array([3, 4]))

    res_lst = sanitize_for_json(lst)
    assert isinstance(res_lst, list)
    assert isinstance(res_lst[0], int)
    assert res_lst[0] == 1
    assert isinstance(res_lst[1], float)
    assert res_lst[1] == 2.5

    res_tup = sanitize_for_json(tup)
    assert isinstance(res_tup, list)
    assert isinstance(res_tup[0], bool)
    assert res_tup[0] is False
    assert isinstance(res_tup[1], list)
    assert res_tup[1] == [3, 4]

def test_sanitize_native_types():
    data = {
        "str": "hello",
        "int": 42,
        "float": 3.14,
        "bool": True,
        "none": None,
        "list": [1, 2, 3],
        "dict": {"a": 1}
    }
    result = sanitize_for_json(data)
    assert result == data
=======
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
>>>>>>> main
