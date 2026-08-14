from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.academy_policy.backtesting.data_adapter import (
    numpy_to_dataframe,
    dataframe_to_backtrader_feed,
    dataframe_to_vectorbt_format,
)


@pytest.fixture
def sample_numpy_data():
    # 10 steps, 5 features
    return np.random.rand(10, 5)


@pytest.fixture
def sample_dataframe(sample_numpy_data):
    index = pd.date_range("2026-06-01 12:00:00", periods=10, freq="1min")
    cols = ["scout_index", "difficulty", "total_reward", "accuracy", "close"]
    df = pd.DataFrame(sample_numpy_data, index=index, columns=cols)
    # Ensure close has realistic positive prices, and total_reward has floats
    df["close"] = df["close"] * 100 + 100
    df["scout_index"] = (df["scout_index"] * 16).astype(int)
    df["difficulty"] = (df["difficulty"] * 3).astype(int) + 1
    return df


def test_numpy_to_dataframe_valid(sample_numpy_data):
    columns = ["f1", "f2", "f3", "f4", "f5"]
    index = pd.date_range("2026-06-01", periods=10, freq="D")
    df = numpy_to_dataframe(sample_numpy_data, columns=columns, index=index)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 10
    assert list(df.columns) == columns
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index[0] == index[0]


def test_numpy_to_dataframe_auto_index_and_columns(sample_numpy_data):
    df = numpy_to_dataframe(sample_numpy_data)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 10
    assert df.shape[1] == 5
    assert isinstance(df.index, pd.DatetimeIndex)
    assert all(df.columns == [f"feature_{i}" for i in range(5)])


def test_numpy_to_dataframe_empty():
    empty_arr = np.array([])
    with pytest.raises(ValueError, match="Input array is empty"):
        numpy_to_dataframe(empty_arr)


def test_numpy_to_dataframe_nan_handling():
    nan_arr = np.array([[1.0, np.nan], [np.nan, 3.0]])
    df = numpy_to_dataframe(nan_arr)
    assert df.shape == (2, 2)
    # Check that NaNs are preserved or handled as required (letting them remain, or optionally filling)
    assert pd.isna(df.iloc[0, 1])


def test_numpy_to_dataframe_dimension_validation():
    # 3D array should raise ValueError
    arr_3d = np.ones((2, 2, 2))
    with pytest.raises(ValueError, match="Input array must be 1D or 2D"):
        numpy_to_dataframe(arr_3d)


def test_dataframe_to_backtrader_feed(sample_dataframe):
    feed = dataframe_to_backtrader_feed(sample_dataframe)
    # Check that it returns a valid Backtrader PandasData feed
    import backtrader as bt
    assert issubclass(type(feed), bt.feed.DataBase)
    
    # Check custom lines are registered
    assert hasattr(feed.p, "scout_index")
    assert hasattr(feed.p, "total_reward")


def test_dataframe_to_backtrader_feed_missing_ohlcv(sample_dataframe):
    # Remove close column to test mock/fallback OHLCV creation
    df_no_close = sample_dataframe.drop(columns=["close"])
    feed = dataframe_to_backtrader_feed(df_no_close)
    
    import backtrader as bt
    assert issubclass(type(feed), bt.feed.DataBase)


def test_dataframe_to_vectorbt_format(sample_dataframe):
    vbt_df = dataframe_to_vectorbt_format(sample_dataframe)
    assert isinstance(vbt_df, pd.DataFrame)
    assert isinstance(vbt_df.index, pd.DatetimeIndex)
    # VectorBT needs a clean dataframe with proper datetime index
    assert not vbt_df.isna().any().any()
