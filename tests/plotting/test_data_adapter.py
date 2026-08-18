"""Tests for pyscattviz.plotting._data_adapter — data type conversion."""

import numpy as np
import pandas as pd


def test_to_array_ndarray():
    from pyscattviz.plotting._data_adapter import to_array

    arr = np.array([1, 2, 3])
    result, label = to_array(arr)
    np.testing.assert_array_equal(result, arr)
    assert label is None


def test_to_array_list():
    from pyscattviz.plotting._data_adapter import to_array

    result, label = to_array([1, 2, 3])
    np.testing.assert_array_equal(result, [1, 2, 3])
    assert label is None


def test_to_array_series():
    from pyscattviz.plotting._data_adapter import to_array

    s = pd.Series([10, 20, 30], name="intensity")
    result, label = to_array(s)
    np.testing.assert_array_equal(result, [10, 20, 30])
    assert label == "intensity"


def test_to_array_dataframe_with_key():
    from pyscattviz.plotting._data_adapter import to_array

    df = pd.DataFrame({"q": [0.1, 0.2], "I": [100, 200]})
    result, label = to_array(df, key="I")
    np.testing.assert_array_equal(result, [100, 200])
    assert label == "I"


def test_to_array_single_column_df():
    from pyscattviz.plotting._data_adapter import to_array

    df = pd.DataFrame({"intensity": [1, 2, 3]})
    result, label = to_array(df)
    np.testing.assert_array_equal(result, [1, 2, 3])
    assert label == "intensity"


def test_extract_xy_arrays():
    from pyscattviz.plotting._data_adapter import extract_xy

    x_arr, y_arr, xl, yl = extract_xy(x=[1, 2], y=[3, 4])
    np.testing.assert_array_equal(x_arr, [1, 2])
    np.testing.assert_array_equal(y_arr, [3, 4])


def test_extract_xy_dataframe():
    from pyscattviz.plotting._data_adapter import extract_xy

    df = pd.DataFrame({"q": [0.1, 0.2], "I": [100, 200]})
    x_arr, y_arr, xl, yl = extract_xy(data=df, x="q", y="I")
    np.testing.assert_array_equal(x_arr, [0.1, 0.2])
    np.testing.assert_array_equal(y_arr, [100, 200])
    assert xl == "q"
    assert yl == "I"


def test_extract_xy_y_only():
    from pyscattviz.plotting._data_adapter import extract_xy

    x_arr, y_arr, xl, yl = extract_xy(y=[10, 20, 30])
    assert x_arr is None
    np.testing.assert_array_equal(y_arr, [10, 20, 30])


def test_detect_dtype():
    from pyscattviz.plotting._data_adapter import detect_dtype

    assert detect_dtype(np.array([1])) == "ndarray"
    assert detect_dtype([1, 2]) == "list"
    assert detect_dtype(pd.Series([1])) == "series"
    assert detect_dtype(pd.DataFrame({"a": [1]})) == "dataframe"
