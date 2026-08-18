"""
Internal data-type detection and conversion layer.

All pyScattViz plot functions accept flexible inputs — numpy arrays, lists,
pandas Series, or DataFrames.  This module normalizes them to numpy arrays
while extracting labels (column names, Series names) for use as automatic
axis labels and legends.

This module is **internal** (prefixed with ``_``); users never need to
import it directly.
"""

from __future__ import annotations

import numpy as np

__all__: list[str] = []  # internal module — nothing public


def detect_dtype(data) -> str:
    """Detect the input data type.

    Returns
    -------
    dtype : str
        One of ``'ndarray'``, ``'series'``, ``'dataframe'``, ``'list'``.
    """
    type_name = type(data).__name__
    module = type(data).__module__

    if isinstance(data, np.ndarray):
        return "ndarray"
    if module.startswith("pandas"):
        if type_name == "DataFrame":
            return "dataframe"
        if type_name == "Series":
            return "series"
    if isinstance(data, (list, tuple)):
        return "list"
    return "ndarray"  # fallback — let np.asarray handle it


def to_array(data, key: str | None = None) -> tuple[np.ndarray, str | None]:
    """Convert any supported input to a numpy array.

    Parameters
    ----------
    data : array-like, Series, or DataFrame
        Input data.
    key : str, optional
        Column name to extract when *data* is a DataFrame.

    Returns
    -------
    arr : np.ndarray
        The data as a numpy array.
    label : str or None
        Extracted label (Series.name, DataFrame column name, etc.).
    """
    dtype = detect_dtype(data)

    if dtype == "series":
        return np.asarray(data.values), getattr(data, "name", None)

    if dtype == "dataframe":
        if key is not None:
            col = data[key]
            return np.asarray(col.values), str(key)
        # Single-column DataFrame → treat as series
        if data.shape[1] == 1:
            col = data.iloc[:, 0]
            return np.asarray(col.values), str(data.columns[0])
        # Multi-column → return values, no single label
        return np.asarray(data.values), None

    # ndarray, list, tuple, or anything else
    return np.asarray(data), None


def extract_xy(
    data=None,
    x=None,
    y=None,
) -> tuple[np.ndarray | None, np.ndarray, str | None, str | None]:
    """Smart extraction of x, y arrays from various input forms.

    Accepts:

    * Two separate arrays for *x* and *y*.
    * A DataFrame with column name strings for *x* and *y*.
    * *y* only (x will be ``None``).

    Parameters
    ----------
    data : DataFrame, optional
        If provided, *x* and *y* should be column name strings.
    x : array-like or str, optional
        X-axis data or column name.
    y : array-like or str
        Y-axis data or column name.

    Returns
    -------
    x_arr : np.ndarray or None
        X-axis array (None if not provided).
    y_arr : np.ndarray
        Y-axis array.
    x_label : str or None
        Label derived from column name or Series name.
    y_label : str or None
        Label derived from column name or Series name.
    """
    if data is not None and detect_dtype(data) == "dataframe":
        # DataFrame mode: x and y are column names
        if y is None:
            raise ValueError("'y' column name is required when 'data' is a DataFrame")
        y_arr, y_label = to_array(data, key=y)
        if x is not None:
            x_arr, x_label = to_array(data, key=x)
        else:
            x_arr, x_label = None, None
        return x_arr, y_arr, x_label, y_label

    # Direct array mode
    y_arr, y_label = to_array(y) if y is not None else (None, None)
    x_arr, x_label = to_array(x) if x is not None else (None, None)
    return x_arr, y_arr, x_label, y_label
