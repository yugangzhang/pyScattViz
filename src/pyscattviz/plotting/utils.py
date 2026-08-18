"""
General-purpose helper utilities for pyscattviz.plotting.

Small, composable functions used across the package: finding nearest values,
building meshgrids from scattered data, detecting file delimiters, etc.

Examples
--------
>>> from pyscattviz.plotting.utils import find_nearest
>>> import numpy as np
>>> idx, val = find_nearest(np.array([1, 3, 7, 10]), 6.5)
>>> idx, val
(2, 7)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.interpolate import griddata

__all__ = [
    "find_nearest",
    "create_meshgrid",
    "smart_delimiter",
]


def find_nearest(
    array: np.ndarray,
    value: float,
) -> tuple[int, float]:
    """Find the index and value of the element nearest to *value*.

    Parameters
    ----------
    array : array-like
        1-D array of values to search.
    value : float
        Target value.

    Returns
    -------
    idx : int
        Index of the nearest element.
    nearest : float
        The element value at *idx*.

    Examples
    --------
    >>> from pyscattviz.plotting.utils import find_nearest
    >>> import numpy as np
    >>> arr = np.array([0.01, 0.02, 0.05, 0.1])
    >>> find_nearest(arr, 0.03)
    (1, 0.02)
    """
    array = np.asarray(array)
    idx = int(np.argmin(np.abs(array - value)))
    return idx, float(array[idx])


def create_meshgrid(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    n_grid: int = 100,
    method: str = "cubic",
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Create a regular meshgrid from (possibly scattered) x, y, z data.

    If the data is already on a regular grid (i.e.
    ``len(unique_x) * len(unique_y) == len(z)``), it is simply reshaped.
    Otherwise, ``scipy.interpolate.griddata`` is used to interpolate onto
    a regular grid.

    Parameters
    ----------
    x, y, z : array-like
        1-D arrays of equal length giving data coordinates and values.
    n_grid : int
        Number of grid points along each axis when interpolating.
    method : str
        Interpolation method (``'linear'``, ``'nearest'``, ``'cubic'``).

    Returns
    -------
    X, Y : np.ndarray
        2-D meshgrid arrays.
    Z : np.ndarray
        2-D values on the grid.

    Examples
    --------
    >>> import numpy as np
    >>> from pyscattviz.plotting.utils import create_meshgrid
    >>> rng = np.random.default_rng(42)
    >>> x = rng.uniform(-5, 5, 200)
    >>> y = rng.uniform(-5, 5, 200)
    >>> z = np.sin(np.sqrt(x**2 + y**2))
    >>> X, Y, Z = create_meshgrid(x, y, z, n_grid=50)
    >>> X.shape
    (50, 50)
    """
    x, y, z = np.asarray(x), np.asarray(y), np.asarray(z)

    ux = np.unique(x)
    uy = np.unique(y)

    # Check if already gridded
    if len(ux) * len(uy) == len(z):
        X, Y = np.meshgrid(np.sort(ux), np.sort(uy))
        # Sort and reshape z to match
        order = np.lexsort((x, y))
        Z = z[order].reshape(len(uy), len(ux))
        return X, Y, Z

    # Scattered data — interpolate
    xi = np.linspace(x.min(), x.max(), n_grid)
    yi = np.linspace(y.min(), y.max(), n_grid)
    X, Y = np.meshgrid(xi, yi)
    Z = griddata((x, y), z, (X, Y), method=method)
    return X, Y, Z


def smart_delimiter(filepath: str | Path) -> str:
    """Detect the delimiter of a tabular text file.

    Reads the first few lines and checks for tab, comma, or whitespace
    separation.

    Parameters
    ----------
    filepath : str or Path
        Path to the text file.

    Returns
    -------
    delimiter : str
        One of ``'\\t'``, ``','``, or ``None`` (whitespace).

    Examples
    --------
    >>> from pyscattviz.plotting.utils import smart_delimiter
    >>> delim = smart_delimiter('data.csv')   # doctest: +SKIP
    >>> delim
    ','
    """
    filepath = Path(filepath)
    with filepath.open() as fh:
        lines = [fh.readline() for _ in range(5)]

    sample = "".join(lines)
    if "\t" in sample:
        return "\t"
    if "," in sample:
        return ","
    return None  # whitespace
