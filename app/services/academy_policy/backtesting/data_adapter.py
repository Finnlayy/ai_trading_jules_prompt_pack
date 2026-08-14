from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
import backtrader as bt


PPO_CUSTOM_LINES = (
    "scout_index",
    "difficulty",
    "total_reward",
    "accuracy",
    "calibration",
    "ab_lift",
)


class PPOPandasData(bt.feeds.PandasData):
    """
    Custom Backtrader PandasData feed that supports standard price lines
    along with extra PPO policy and KPI fields as data lines.
    """
    lines = PPO_CUSTOM_LINES
    
    params = (
        ("scout_index", -1),
        ("difficulty", -1),
        ("total_reward", -1),
        ("accuracy", -1),
        ("calibration", -1),
        ("ab_lift", -1),
    )


def numpy_to_dataframe(
    array: np.ndarray,
    columns: list[str] | None = None,
    index: pd.DatetimeIndex | None = None,
) -> pd.DataFrame:
    """
    Converts a numpy array (1D or 2D) representing observation states or policy outputs
    into a pandas DataFrame with DatetimeIndex and structured columns.
    
    Args:
        array: Numpy array to convert (1D or 2D).
        columns: Optional list of column names.
        index: Optional DatetimeIndex.
        
    Returns:
        pd.DataFrame: Properly shaped and indexed pandas DataFrame.
        
    Raises:
        ValueError: If input array is empty or has unsupported dimensions.
    """
    if array is None or array.size == 0:
        raise ValueError("Input array is empty")
        
    if array.ndim not in (1, 2):
        raise ValueError("Input array must be 1D or 2D")
        
    # Convert 1D array to 2D
    if array.ndim == 1:
        data = array.reshape(-1, 1)
    else:
        data = array

    num_rows, num_cols = data.shape

    # Construct DatetimeIndex if missing
    if index is None:
        index = pd.date_range("2026-06-01 12:00:00", periods=num_rows, freq="1min")
    elif len(index) != num_rows:
        raise ValueError(f"Index length ({len(index)}) must match array rows ({num_rows})")

    # Construct Column Names if missing
    if columns is None:
        columns = [f"feature_{i}" for i in range(num_cols)]
    elif len(columns) != num_cols:
        raise ValueError(f"Columns length ({len(columns)}) must match array columns ({num_cols})")

    df = pd.DataFrame(data, index=index, columns=columns)
    return df


def dataframe_to_backtrader_feed(df: pd.DataFrame) -> bt.feeds.PandasData:
    """
    Converts a pandas DataFrame into a Backtrader-compatible PandasData feed,
    injecting custom lines for PPO policy actions, rewards, and KPI tracking.
    
    Mock/fallback OHLCV values are generated if not present in the input DataFrame
    to allow the Backtrader engine to run simulations.
    """
    working_df = df.copy()
    
    # Check and generate standard OHLCV columns if missing
    if "close" not in working_df.columns:
        working_df["close"] = 1.0
        
    if "open" not in working_df.columns:
        working_df["open"] = working_df["close"]
        
    if "high" not in working_df.columns:
        working_df["high"] = working_df["close"]
        
    if "low" not in working_df.columns:
        working_df["low"] = working_df["close"]
        
    if "volume" not in working_df.columns:
        working_df["volume"] = 0.0
        
    if "openinterest" not in working_df.columns:
        working_df["openinterest"] = 0.0

    # Ensure custom PPO lines are populated
    for line in PPO_CUSTOM_LINES:
        if line not in working_df.columns:
            working_df[line] = 0.0

    # PPO integration point
    # We feed the dataframe to our custom PPOPandasData feed class
    feed = PPOPandasData(
        dataname=working_df,
        datetime=None,  # Use index
        open="open",
        high="high",
        low="low",
        close="close",
        volume="volume",
        openinterest="openinterest",
        scout_index="scout_index",
        difficulty="difficulty",
        total_reward="total_reward",
        accuracy="accuracy",
        calibration="calibration",
        ab_lift="ab_lift",
    )
    return feed


def dataframe_to_vectorbt_format(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans and prepares a pandas DataFrame for ingestion into VectorBT,
    handling index consistency, resolving NaNs, and filtering necessary columns.
    """
    if df.empty:
        raise ValueError("Input DataFrame is empty")

    working_df = df.copy()

    # VectorBT requires a clean, non-null index and columns
    # Fill any NaNs with 0.0 or forward fill
    working_df = working_df.ffill().fillna(0.0)

    return working_df
