"""
Data transforms for visualization (z-scaling, normalization, radial maps).

These functions prepare 2D array data for display — computing percentile
ranges, applying log/gamma/radial transforms, etc.  Adapted from
Y.G.@CFN plots.py (pyCHX/pyScatt).

Examples
--------
>>> import numpy as np
>>> from pyscattviz.plotting.transforms import z_range, z_transform
>>> img = np.random.exponential(10, (100, 100))
>>> vmin, vmax = z_range(img, ztrim=(0.01, 0.01))
>>> normed = z_transform(img, mode='log', vmin=vmin, vmax=vmax)
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "z_range",
    "z_transform",
    "radial_map",
]


def z_range(
    data: np.ndarray,
    ztrim: tuple[float, float] = (0.01, 0.01),
    zmin: float | None = None,
    zmax: float | None = None,
) -> tuple[float, float]:
    """Compute display range from data percentiles.

    Parameters
    ----------
    data : np.ndarray
        Input data (any shape — will be flattened internally).
    ztrim : tuple of float
        ``(lower_fraction, upper_fraction)`` to trim from each end.
        For example ``(0.01, 0.01)`` clips the bottom/top 1 %.
    zmin : float, optional
        Override the lower bound.  If *None*, computed from *ztrim*.
    zmax : float, optional
        Override the upper bound.  If *None*, computed from *ztrim*.

    Returns
    -------
    vmin : float
        Lower display bound.
    vmax : float
        Upper display bound.

    Examples
    --------
    >>> import numpy as np
    >>> from pyscattviz.plotting.transforms import z_range
    >>> data = np.random.normal(50, 10, (200, 200))
    >>> vmin, vmax = z_range(data)
    >>> print(f"Display range: [{vmin:.1f}, {vmax:.1f}]")
    Display range: [...]
    """
    values = np.sort(data.ravel())
    if np.ma.is_masked(values):
        values = values.compressed()

    n = len(values)
    if zmin is None:
        zmin = values[int(n * ztrim[0])]
    if zmax is None:
        idx = -int(n * ztrim[1])
        if idx >= 0:
            idx = -1
        zmax = values[idx]

    if zmax <= zmin:
        zmax = values[-1] if len(values) > 0 else zmin + 1.0
    return float(zmin), float(zmax)


def z_transform(
    data: np.ndarray,
    mode: str = "linear",
    adj: float = 1.0,
    vmin: float = 0.0,
    vmax: float = 1.0,
    r_map: np.ndarray | None = None,
) -> np.ndarray:
    """Transform 2D data for false-color display.

    Returns an array normalized to [0, 1], suitable for mapping through a
    colormap.

    Parameters
    ----------
    data : np.ndarray
        Input data.
    mode : str
        Transform mode:

        * ``'linear'`` — simple min-max scaling (*adj* ignored).
        * ``'log'`` — logarithmic scaling (*adj* ignored).
        * ``'gamma'`` — log-gamma correction; *adj* is the ``log_gamma``
          value (0.2-0.5 gives nice log-like response).
        * ``'radial'`` — multiply by ``r**adj`` before scaling (for data
          that decays from a center).
    adj : float
        Mode-specific adjustment (see *mode*).
    vmin, vmax : float
        Clipping bounds applied **before** the transform.
    r_map : np.ndarray, optional
        Radial distance map (required when ``mode='radial'``).
        See :func:`radial_map`.

    Returns
    -------
    Z : np.ndarray
        Normalized array in [0, 1].

    Examples
    --------
    >>> import numpy as np
    >>> from pyscattviz.plotting.transforms import z_transform, z_range
    >>> img = np.random.exponential(100, (64, 64))
    >>> lo, hi = z_range(img)
    >>> Z = z_transform(img, mode='gamma', adj=0.3, vmin=lo, vmax=hi)
    >>> Z.min(), Z.max()
    (0.0, ...)
    """
    data = np.asarray(data, dtype=float)

    if mode == "log":
        safe_min = max(vmin, 0.5)
        log_min = np.log(safe_min)
        log_max = np.log(max(vmax, safe_min + 1e-10))
        Z = (np.log(np.clip(data, safe_min, None)) - log_min) / (log_max - log_min)
    elif mode == "gamma":
        log_gamma = adj
        c = np.exp(1.0 / log_gamma) - 1.0
        Z = (data - vmin) / (vmax - vmin)
        Z = np.clip(Z, 0, None)
        Z = log_gamma * np.log(Z * c + 1.0)
    elif mode == "radial":
        if r_map is None:
            raise ValueError("r_map is required for mode='radial'")
        Z = data * np.power(r_map, adj)
        Z = (Z - vmin) / (vmax - vmin)
    else:  # linear (default)
        Z = (data - vmin) / (vmax - vmin)

    Z = np.nan_to_num(Z, nan=0.0, posinf=1.0, neginf=0.0)
    return np.clip(Z, 0.0, 1.0)


def radial_map(
    shape: tuple[int, int],
    center: tuple[float, float] | None = None,
) -> np.ndarray:
    """Compute a map of pixel distances from *center*.

    Parameters
    ----------
    shape : tuple of int
        ``(rows, cols)`` of the image.
    center : tuple of float, optional
        ``(x0, y0)`` origin in pixel coordinates.  Defaults to the image
        center.

    Returns
    -------
    R : np.ndarray
        2-D array of radial distances (in pixels).

    Examples
    --------
    >>> from pyscattviz.plotting.transforms import radial_map
    >>> R = radial_map((100, 100))
    >>> R.shape
    (100, 100)
    >>> R[50, 50]  # near center
    0.0
    """
    dim_y, dim_x = shape
    if center is None:
        x0, y0 = dim_x / 2.0, dim_y / 2.0
    else:
        x0, y0 = center

    x = np.arange(dim_x) - x0
    y = np.arange(dim_y) - y0
    X, Y = np.meshgrid(x, y)
    return np.sqrt(X**2 + Y**2)
