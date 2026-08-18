"""
2D plotting: images, heatmaps, and pcolormesh.

Display 2D arrays as images with smart defaults — auto-contrast,
log-scale, z-transforms, colorbars, and mask overlays.

Adapted from ``show_img`` / ``show_imgz`` in pyScatt by Y.G.@CFN and
the NanoOrganizer image viewer.

Examples
--------
>>> import pyscattviz.plotting as pv
>>> import numpy as np
>>> img = np.random.exponential(10, (100, 100))
>>> pv.imshow(img, log=True, colorbar=True, cmap='pv_vge_hdr')
"""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.colors import LogNorm
from matplotlib.ticker import LogFormatter

from pyscattviz.plotting._data_adapter import to_array
from pyscattviz.plotting.labels import sanitize_label
from pyscattviz.plotting.transforms import radial_map, z_range, z_transform

__all__ = [
    "imshow",
    "imshow_z",
    "heatmap",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_ax(ax, figsize=None):
    """Return (fig, ax), creating a new figure if needed."""
    if ax is None:
        fs = figsize or (7, 6)
        fig, ax = plt.subplots(figsize=fs)
    elif isinstance(ax, (list, tuple)):
        fig, ax = ax  # legacy [fig, ax] convention
    else:
        fig = ax.get_figure()
    return fig, ax


def _apply_zlim(image, zlim, logs=False):
    """Compute vmin/vmax from percentile-based zlim."""
    if logs:
        flat = image[image > 0].ravel()
    else:
        flat = image.ravel()
    if len(flat) == 0:
        return None, None
    n = len(flat)
    z1, z2 = zlim
    sorted_vals = np.sort(flat)
    vmin = sorted_vals[int(n * z1)]
    idx2 = int(n * z2)
    if idx2 >= n:
        idx2 = n - 1
    vmax = sorted_vals[idx2]
    if z2 > 1:
        vmax *= z2
    return float(vmin), float(vmax)


# ---------------------------------------------------------------------------
# imshow
# ---------------------------------------------------------------------------


def imshow(
    image,
    ax: Axes | None = None,
    interactive: bool = False,
    **kwargs,
) -> Axes | Any:
    """Display a 2D array as an image.

    Parameters
    ----------
    image : array-like
        2-D array to display.
    ax : Axes, optional
        Axes to plot on.  If *None*, creates a new figure.
    interactive : bool
        If *True*, return a plotly ``Figure``.
    **kwargs
        Display options:

        - **cmap** : str — colormap (default ``'viridis'``).
        - **vmin**, **vmax** : float — explicit intensity limits.
        - **zlim** : tuple of float — percentile-based auto-range, e.g.
          ``(0.01, 0.99)`` clips bottom/top 1 %.
        - **log** : bool — use logarithmic color scale.
        - **colorbar** : bool — show colorbar.
        - **extent** : tuple — ``(left, right, bottom, top)`` data coords.
        - **origin** : str — ``'lower'`` (default) or ``'upper'``.
        - **interpolation** : str — ``'nearest'``, ``'bilinear'``, etc.
        - **aspect** : str or float — ``'auto'``, ``'equal'``, or numeric.
        - **title**, **xlabel**, **ylabel** : str.
        - **show_ticks** : bool — show axis ticks (default *True*).
        - **figsize** : tuple.
        - **save** : str or Path — save figure to this path.
        - **colorbar_fontsize** : float — tick label size on colorbar.

    Returns
    -------
    ax : Axes or plotly Figure

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> import numpy as np
    >>> img = np.random.exponential(10, (100, 100))
    >>> pv.imshow(img, colorbar=True)

    Log-scale with custom colormap:

    >>> pv.imshow(img, log=True, cmap='pv_vge_hdr', zlim=(0.01, 0.99))

    Interactive:

    >>> fig = pv.imshow(img, interactive=True)
    """
    image_arr, _ = to_array(image)
    image_arr = np.atleast_2d(image_arr).astype(float)

    if interactive:
        return _imshow_plotly(image_arr, **kwargs)

    # --- Matplotlib path ---
    fig, ax = _get_ax(ax, kwargs.get("figsize"))

    cmap = kwargs.get("cmap", "viridis")
    vmin = kwargs.get("vmin")
    vmax = kwargs.get("vmax")
    zlim = kwargs.get("zlim")
    log = kwargs.get("log", False)
    origin = kwargs.get("origin", "lower")
    interpolation = kwargs.get("interpolation", "nearest")
    extent = kwargs.get("extent")
    aspect = kwargs.get("aspect", "auto")
    show_ticks = kwargs.get("show_ticks", True)
    show_colorbar = kwargs.get("colorbar", False)
    colorbar_fontsize = kwargs.get("colorbar_fontsize", 8)

    # Percentile-based limits
    if zlim is not None and vmin is None and vmax is None:
        vmin, vmax = _apply_zlim(image_arr, zlim, logs=log)

    if log:
        img_safe = image_arr.copy()
        pos_min = img_safe[img_safe > 0].min() if np.any(img_safe > 0) else 1e-10
        img_safe[img_safe <= 0] = pos_min / 10.0
        norm = LogNorm(vmin=vmin or pos_min, vmax=vmax)
        im = ax.imshow(
            img_safe,
            origin=origin,
            cmap=cmap,
            interpolation=interpolation,
            norm=norm,
            extent=extent,
        )
    else:
        im = ax.imshow(
            image_arr,
            origin=origin,
            cmap=cmap,
            interpolation=interpolation,
            vmin=vmin,
            vmax=vmax,
            extent=extent,
        )

    ax.set_aspect(aspect)

    if show_colorbar:
        cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.03, aspect=30)
        cbar.ax.tick_params(labelsize=colorbar_fontsize)
        if log:
            cbar.formatter = LogFormatter(labelOnlyBase=False)
            cbar.update_ticks()

    if not show_ticks:
        ax.set_xticks([])
        ax.set_yticks([])

    # Labels
    title = kwargs.get("title")
    if title is not None:
        ax.set_title(sanitize_label(title))
    xlabel = kwargs.get("xlabel")
    if xlabel is not None:
        ax.set_xlabel(sanitize_label(xlabel))
    ylabel = kwargs.get("ylabel")
    if ylabel is not None:
        ax.set_ylabel(sanitize_label(ylabel))

    if kwargs.get("xlim") is not None:
        ax.set_xlim(kwargs["xlim"])
    if kwargs.get("ylim") is not None:
        ax.set_ylim(kwargs["ylim"])

    if not fig.get_constrained_layout():
        fig.tight_layout()

    save = kwargs.get("save")
    if save:
        from pyscattviz.plotting.io import save_fig as _save

        _save(fig, save)

    return ax


# ---------------------------------------------------------------------------
# imshow_z
# ---------------------------------------------------------------------------


def imshow_z(
    image,
    x=None,
    y=None,
    ax: Axes | None = None,
    z_mode: str = "linear",
    z_adj: float = 1.0,
    interactive: bool = False,
    **kwargs,
) -> Axes | Any:
    """Display a 2D array with a z-transform applied before rendering.

    The data is first transformed (log, gamma, radial, or linear), then
    normalized to [0, 1] for display.

    Parameters
    ----------
    image : array-like
        2-D array to display.
    x, y : array-like, optional
        Coordinate arrays for ``pcolormesh`` display.  If both are given,
        renders with ``pcolormesh``; otherwise uses ``imshow``.
    ax : Axes, optional
        Axes to plot on.
    z_mode : str
        Transform mode: ``'linear'``, ``'log'``, ``'gamma'``, ``'radial'``.
    z_adj : float
        Adjustment parameter (gamma exponent or radial power).
    interactive : bool
        If *True*, return a plotly Figure.
    **kwargs
        Same as :func:`imshow`, plus:

        - **ztrim** : tuple — percentile trim ``(lo, hi)`` for auto-range
          (default ``(0.01, 0.01)``).
        - **center** : tuple — ``(x0, y0)`` center for radial mode.
        - **shading** : str — pcolormesh shading (``'flat'``, ``'auto'``).

    Returns
    -------
    ax : Axes or plotly Figure

    Examples
    --------
    Log-gamma display:

    >>> import pyscattviz.plotting as pv
    >>> import numpy as np
    >>> img = np.random.exponential(100, (128, 128))
    >>> pv.imshow_z(img, z_mode='gamma', z_adj=0.3, colorbar=True)

    With coordinate arrays (pcolormesh):

    >>> x = np.linspace(-5, 5, 129)
    >>> y = np.linspace(-5, 5, 129)
    >>> pv.imshow_z(img, x=x, y=y, z_mode='log')
    """
    image_arr, _ = to_array(image)
    image_arr = np.atleast_2d(image_arr).astype(float)

    ztrim = kwargs.pop("ztrim", (0.01, 0.01))
    center = kwargs.pop("center", None)
    shading = kwargs.pop("shading", "auto")

    vmin = kwargs.get("vmin")
    vmax = kwargs.get("vmax")

    # Compute display range
    zmin, zmax = z_range(image_arr, ztrim=ztrim)
    if vmin is not None:
        zmin = vmin
    if vmax is not None:
        zmax = vmax

    # Radial map
    r_map = None
    if z_mode == "radial":
        r_map = radial_map(image_arr.shape, center=center)

    # Transform
    Z = z_transform(image_arr, mode=z_mode, adj=z_adj, vmin=zmin, vmax=zmax, r_map=r_map)

    if interactive:
        return _imshow_z_plotly(Z, x=x, y=y, zmin=zmin, zmax=zmax, **kwargs)

    # --- Matplotlib ---
    fig, ax = _get_ax(ax, kwargs.get("figsize"))

    cmap = kwargs.get("cmap", "viridis")
    origin = kwargs.get("origin", "lower")
    interpolation = kwargs.get("interpolation", "nearest")
    extent = kwargs.get("extent")
    aspect = kwargs.get("aspect", "auto")
    show_ticks = kwargs.get("show_ticks", True)
    show_colorbar = kwargs.get("colorbar", False)
    colorbar_fontsize = kwargs.get("colorbar_fontsize", 8)

    if x is not None and y is not None:
        x_arr, _ = to_array(x)
        y_arr, _ = to_array(y)
        im = ax.pcolormesh(x_arr, y_arr, Z, cmap=cmap, vmin=0, vmax=1, shading=shading)
    else:
        im = ax.imshow(
            Z,
            origin=origin,
            cmap=cmap,
            interpolation=interpolation,
            vmin=0,
            vmax=1,
            extent=extent,
        )

    ax.set_aspect(aspect)

    if show_colorbar:
        # Custom tick labels showing real values
        n_ticks = 5
        tick_values = np.linspace(0, 1, n_ticks)
        real_labels = np.linspace(zmin, zmax, n_ticks)
        cbar = fig.colorbar(im, ax=ax, ticks=tick_values, fraction=0.04, pad=0.03, aspect=30)
        cbar.ax.set_yticklabels(
            [f"{v:.1f}" for v in real_labels],
            size=colorbar_fontsize,
        )

    if not show_ticks:
        ax.set_xticks([])
        ax.set_yticks([])

    title = kwargs.get("title")
    if title is not None:
        ax.set_title(sanitize_label(title))
    xlabel = kwargs.get("xlabel")
    if xlabel is not None:
        ax.set_xlabel(sanitize_label(xlabel))
    ylabel = kwargs.get("ylabel")
    if ylabel is not None:
        ax.set_ylabel(sanitize_label(ylabel))

    if not fig.get_constrained_layout():
        fig.tight_layout()

    save = kwargs.get("save")
    if save:
        from pyscattviz.plotting.io import save_fig as _save

        _save(fig, save)

    return ax


# ---------------------------------------------------------------------------
# heatmap
# ---------------------------------------------------------------------------


def heatmap(
    data,
    x=None,
    y=None,
    ax: Axes | None = None,
    interactive: bool = False,
    **kwargs,
) -> Axes | Any:
    """2D heatmap via pcolormesh or seaborn.

    If *data* is a pandas DataFrame, uses seaborn's ``heatmap``.
    Otherwise uses ``pcolormesh`` for array data.

    Parameters
    ----------
    data : array-like or DataFrame
        2-D data to display.
    x, y : array-like, optional
        Coordinate arrays for pcolormesh axes.
    ax : Axes, optional
        Axes to plot on.
    interactive : bool
        If *True*, return a plotly ``Figure``.
    **kwargs
        Display options:

        - **cmap** : str — colormap (default ``'viridis'``).
        - **vmin**, **vmax** : float — intensity limits.
        - **colorbar** : bool — show colorbar (default *True*).
        - **annot** : bool — annotate cells (seaborn/DataFrame mode only).
        - **fmt** : str — annotation format string.
        - **shading** : str — pcolormesh shading.
        - **xlabel**, **ylabel**, **title** : str.
        - **figsize** : tuple.
        - **save** : str or Path.

    Returns
    -------
    ax : Axes or plotly Figure

    Examples
    --------
    Array heatmap:

    >>> import pyscattviz.plotting as pv
    >>> import numpy as np
    >>> data = np.random.rand(20, 30)
    >>> pv.heatmap(data, title='Random Heatmap')

    With coordinates:

    >>> x = np.linspace(0, 1, 31)
    >>> y = np.linspace(0, 2, 21)
    >>> pv.heatmap(data, x=x, y=y, cmap='plasma')

    DataFrame (seaborn):

    >>> import pandas as pd
    >>> df = pd.DataFrame(np.random.rand(5, 5), columns=list('ABCDE'))
    >>> pv.heatmap(df, annot=True, fmt='.2f')
    """
    from pyscattviz.plotting._data_adapter import detect_dtype

    dtype = detect_dtype(data)

    if interactive:
        return _heatmap_plotly(data, x=x, y=y, dtype=dtype, **kwargs)

    fig, ax = _get_ax(ax, kwargs.get("figsize"))

    cmap = kwargs.get("cmap", "viridis")
    vmin = kwargs.get("vmin")
    vmax = kwargs.get("vmax")
    show_colorbar = kwargs.get("colorbar", True)
    shading = kwargs.get("shading", "auto")

    if dtype == "dataframe":
        import seaborn as sns

        annot = kwargs.get("annot", False)
        fmt = kwargs.get("fmt", ".2g")
        sns.heatmap(
            data, ax=ax, cmap=cmap, vmin=vmin, vmax=vmax, annot=annot, fmt=fmt, cbar=show_colorbar
        )
    else:
        data_arr, _ = to_array(data)
        data_arr = np.atleast_2d(data_arr).astype(float)

        if x is not None and y is not None:
            x_arr, _ = to_array(x)
            y_arr, _ = to_array(y)
            im = ax.pcolormesh(
                x_arr, y_arr, data_arr, cmap=cmap, vmin=vmin, vmax=vmax, shading=shading
            )
        else:
            im = ax.pcolormesh(data_arr, cmap=cmap, vmin=vmin, vmax=vmax, shading=shading)

        if show_colorbar:
            fig.colorbar(im, ax=ax, fraction=0.04, pad=0.03)

    title = kwargs.get("title")
    if title is not None:
        ax.set_title(sanitize_label(title))
    xlabel = kwargs.get("xlabel")
    if xlabel is not None:
        ax.set_xlabel(sanitize_label(xlabel))
    ylabel = kwargs.get("ylabel")
    if ylabel is not None:
        ax.set_ylabel(sanitize_label(ylabel))

    if not fig.get_constrained_layout():
        fig.tight_layout()

    save = kwargs.get("save")
    if save:
        from pyscattviz.plotting.io import save_fig as _save

        _save(fig, save)

    return ax


# ---------------------------------------------------------------------------
# Plotly backends
# ---------------------------------------------------------------------------


def _imshow_plotly(image, **kwargs):
    """Plotly backend for imshow."""
    import plotly.express as px

    log = kwargs.get("log", False)
    img = image.copy()
    if log:
        pos_min = img[img > 0].min() if np.any(img > 0) else 1e-10
        img[img <= 0] = pos_min / 10.0
        img = np.log10(img)

    fig = px.imshow(
        img,
        color_continuous_scale=kwargs.get("cmap", "viridis"),
        origin=kwargs.get("origin", "lower"),
        aspect=kwargs.get("aspect", "auto"),
    )
    layout_kw = {}
    if "title" in kwargs:
        layout_kw["title"] = kwargs["title"]
    if "xlabel" in kwargs:
        layout_kw["xaxis_title"] = kwargs["xlabel"]
    if "ylabel" in kwargs:
        layout_kw["yaxis_title"] = kwargs["ylabel"]
    fig.update_layout(**layout_kw)
    return fig


def _imshow_z_plotly(Z, x=None, y=None, zmin=0, zmax=1, **kwargs):
    """Plotly backend for imshow_z."""
    import plotly.express as px

    fig = px.imshow(
        Z,
        color_continuous_scale=kwargs.get("cmap", "viridis"),
        origin=kwargs.get("origin", "lower"),
        aspect=kwargs.get("aspect", "auto"),
    )
    layout_kw = {}
    if "title" in kwargs:
        layout_kw["title"] = kwargs["title"]
    fig.update_layout(**layout_kw)
    return fig


def _heatmap_plotly(data, x=None, y=None, dtype="ndarray", **kwargs):
    """Plotly backend for heatmap."""
    import plotly.express as px

    if dtype == "dataframe":
        z = data.values
        x_labels = list(data.columns)
        y_labels = list(data.index)
    else:
        z, _ = to_array(data)
        z = np.atleast_2d(z).astype(float)
        x_labels = None
        y_labels = None

    fig = px.imshow(
        z,
        x=x_labels,
        y=y_labels,
        color_continuous_scale=kwargs.get("cmap", "viridis"),
    )
    layout_kw = {}
    if "title" in kwargs:
        layout_kw["title"] = kwargs["title"]
    if "xlabel" in kwargs:
        layout_kw["xaxis_title"] = kwargs["xlabel"]
    if "ylabel" in kwargs:
        layout_kw["yaxis_title"] = kwargs["ylabel"]
    fig.update_layout(**layout_kw)
    return fig
