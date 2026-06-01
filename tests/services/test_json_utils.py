import numpy as np
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
