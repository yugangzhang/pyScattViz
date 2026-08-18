"""
3D plotting: surfaces, wireframes, scatter, and contours.

Provides convenient wrappers for matplotlib 3D plots and plotly interactive
3D visualizations.  Scattered data is automatically interpolated to a grid.

Adapted from the NanoOrganizer 3D plotter by Y.G.@CFN.

Examples
--------
>>> import pyscattviz.plotting as pv
>>> import numpy as np
>>> x = np.linspace(-5, 5, 50)
>>> y = np.linspace(-5, 5, 50)
>>> X, Y = np.meshgrid(x, y)
>>> Z = np.sin(np.sqrt(X**2 + Y**2))
>>> pv.surface(X, Y, Z, cmap='pv_vge', title='Ripple')
"""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from pyscattviz.plotting._data_adapter import to_array
from pyscattviz.plotting.utils import create_meshgrid

__all__ = [
    "surface",
    "wireframe",
    "scatter3d",
    "contour",
    "surface_contour",
    "make_demo_data",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_3d_ax(ax, figsize=None):
    """Return (fig, ax3d), creating a 3D figure if needed."""
    if ax is None:
        fs = figsize or (10, 7)
        fig = plt.figure(figsize=fs)
        ax = fig.add_subplot(111, projection="3d")
    else:
        fig = ax.get_figure()
    return fig, ax


def _ensure_grid(x, y, z, n_grid=80):
    """Ensure x, y, z form a 2-D grid.  Interpolates scattered data."""
    x_arr, _ = to_array(x)
    y_arr, _ = to_array(y)
    z_arr, _ = to_array(z)

    # Already 2-D grids
    if x_arr.ndim == 2 and y_arr.ndim == 2 and z_arr.ndim == 2:
        return x_arr, y_arr, z_arr

    # 1-D arrays — meshgrid or scattered
    x_arr = x_arr.ravel()
    y_arr = y_arr.ravel()
    z_arr = z_arr.ravel()
    return create_meshgrid(x_arr, y_arr, z_arr, n_grid=n_grid)


def _apply_labels_3d(ax, **kw):
    """Apply axis labels and view angles to a 3D axes."""
    if kw.get("xlabel"):
        ax.set_xlabel(kw["xlabel"], fontsize=12, labelpad=10)
    if kw.get("ylabel"):
        ax.set_ylabel(kw["ylabel"], fontsize=12, labelpad=10)
    if kw.get("zlabel"):
        ax.set_zlabel(kw["zlabel"], fontsize=12, labelpad=10)
    if kw.get("title"):
        ax.set_title(kw["title"], fontsize=14, pad=20)
    elev = kw.get("elev", 30)
    azim = kw.get("azim", -60)
    ax.view_init(elev=elev, azim=azim)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def surface(
    x,
    y,
    z,
    ax=None,
    interactive: bool = False,
    **kwargs,
) -> Any:
    """3D surface plot.

    Automatically grids scattered data via interpolation.

    Parameters
    ----------
    x, y, z : array-like
        Data arrays.  Can be 2-D meshgrids or 1-D arrays (will be gridded).
    ax : Axes3D, optional
        Existing 3D axes.
    interactive : bool
        If *True*, return a plotly Figure.
    **kwargs
        - **cmap** : str — colormap (default ``'viridis'``).
        - **alpha** : float — surface transparency.
        - **colorbar** : bool — show colorbar (default *True*).
        - **elev**, **azim** : float — view angles.
        - **xlabel**, **ylabel**, **zlabel**, **title** : str.
        - **figsize** : tuple.
        - **save** : str or Path.

    Returns
    -------
    ax : Axes3D or plotly Figure

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> X, Y, Z = pv.make_demo_data('ripple')
    >>> pv.surface(X, Y, Z, cmap='plasma', title='Ripple Surface')
    """
    X, Y, Z = _ensure_grid(x, y, z)

    if interactive:
        return _surface_plotly(X, Y, Z, **kwargs)

    fig, ax = _get_3d_ax(ax, kwargs.get("figsize"))
    cmap = kwargs.get("cmap", "viridis")
    alpha = kwargs.get("alpha", 0.8)

    surf = ax.plot_surface(X, Y, Z, cmap=cmap, alpha=alpha, linewidth=0.3, antialiased=True)
    if kwargs.get("colorbar", True):
        fig.colorbar(surf, ax=ax, shrink=0.5, aspect=10)

    _apply_labels_3d(ax, **kwargs)

    save = kwargs.get("save")
    if save:
        from pyscattviz.plotting.io import save_fig as _save

        _save(fig, save)

    return ax


def wireframe(
    x,
    y,
    z,
    ax=None,
    interactive: bool = False,
    **kwargs,
) -> Any:
    """3D wireframe mesh plot.

    Parameters
    ----------
    x, y, z : array-like
        Data arrays (2-D grids or 1-D scattered).
    ax : Axes3D, optional
    interactive : bool
    **kwargs
        - **color** : str — wire color (default ``'black'``).
        - **lw** : float — line width.
        - **alpha** : float.
        - **elev**, **azim**, **xlabel**, **ylabel**, **zlabel**, **title**.
        - **figsize**, **save**.

    Returns
    -------
    ax : Axes3D or plotly Figure

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> X, Y, Z = pv.make_demo_data('saddle')
    >>> pv.wireframe(X, Y, Z, title='Saddle Wireframe')
    """
    X, Y, Z = _ensure_grid(x, y, z)

    if interactive:
        return _wireframe_plotly(X, Y, Z, **kwargs)

    fig, ax = _get_3d_ax(ax, kwargs.get("figsize"))
    color = kwargs.get("color", "black")
    lw = kwargs.get("lw", 0.5)
    alpha = kwargs.get("alpha", 0.8)

    ax.plot_wireframe(X, Y, Z, color=color, linewidth=lw, alpha=alpha)
    _apply_labels_3d(ax, **kwargs)

    save = kwargs.get("save")
    if save:
        from pyscattviz.plotting.io import save_fig as _save

        _save(fig, save)

    return ax


def scatter3d(
    x,
    y,
    z,
    c=None,
    ax=None,
    interactive: bool = False,
    **kwargs,
) -> Any:
    """3D scatter plot with optional color-mapping.

    Parameters
    ----------
    x, y, z : array-like
        1-D coordinate arrays.
    c : array-like, optional
        Values for color mapping.  Defaults to *z*.
    ax : Axes3D, optional
    interactive : bool
    **kwargs
        - **cmap** : str — colormap.
        - **s** : float — marker size (default 20).
        - **alpha** : float.
        - **colorbar** : bool.
        - **elev**, **azim**, **xlabel**, **ylabel**, **zlabel**, **title**.
        - **figsize**, **save**.

    Returns
    -------
    ax : Axes3D or plotly Figure

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> import numpy as np
    >>> rng = np.random.default_rng(0)
    >>> x, y, z = rng.normal(size=(3, 200))
    >>> pv.scatter3d(x, y, z, c=z, cmap='coolwarm')
    """
    x_arr, _ = to_array(x)
    y_arr, _ = to_array(y)
    z_arr, _ = to_array(z)
    x_arr, y_arr, z_arr = x_arr.ravel(), y_arr.ravel(), z_arr.ravel()

    if c is not None:
        c_arr, _ = to_array(c)
        c_arr = c_arr.ravel()
    else:
        c_arr = z_arr

    if interactive:
        return _scatter3d_plotly(x_arr, y_arr, z_arr, c_arr, **kwargs)

    fig, ax = _get_3d_ax(ax, kwargs.get("figsize"))
    cmap = kwargs.get("cmap", "viridis")
    s = kwargs.get("s", 20)
    alpha = kwargs.get("alpha", 0.8)

    sc = ax.scatter(x_arr, y_arr, z_arr, c=c_arr, cmap=cmap, s=s, alpha=alpha)
    if kwargs.get("colorbar", True):
        fig.colorbar(sc, ax=ax, shrink=0.5, aspect=10)

    _apply_labels_3d(ax, **kwargs)

    save = kwargs.get("save")
    if save:
        from pyscattviz.plotting.io import save_fig as _save

        _save(fig, save)

    return ax


def contour(
    x,
    y,
    z,
    ax=None,
    interactive: bool = False,
    **kwargs,
) -> Any:
    """2D filled contour plot (top-down projection of 3D data).

    Parameters
    ----------
    x, y, z : array-like
        Data arrays.
    ax : Axes, optional
        A regular 2D axes (not 3D).
    interactive : bool
    **kwargs
        - **cmap** : str — colormap.
        - **levels** : int — number of contour levels (default 20).
        - **alpha** : float.
        - **show_lines** : bool — overlay contour lines (default *True*).
        - **colorbar** : bool.
        - **xlabel**, **ylabel**, **title**.
        - **figsize**, **save**.

    Returns
    -------
    ax : Axes or plotly Figure

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> X, Y, Z = pv.make_demo_data('gaussian')
    >>> pv.contour(X, Y, Z, levels=15, cmap='inferno')
    """
    X, Y, Z = _ensure_grid(x, y, z)

    if interactive:
        return _contour_plotly(X, Y, Z, **kwargs)

    if ax is None:
        fig, ax = plt.subplots(figsize=kwargs.get("figsize", (8, 6)))
    else:
        fig = ax.get_figure()

    cmap = kwargs.get("cmap", "viridis")
    levels = kwargs.get("levels", 20)
    alpha = kwargs.get("alpha", 0.9)
    show_lines = kwargs.get("show_lines", True)

    cf = ax.contourf(X, Y, Z, levels=levels, cmap=cmap, alpha=alpha)
    if show_lines:
        ax.contour(X, Y, Z, levels=levels, colors="black", linewidths=0.5, alpha=0.3)

    if kwargs.get("colorbar", True):
        fig.colorbar(cf, ax=ax)

    if kwargs.get("title"):
        ax.set_title(kwargs["title"])
    if kwargs.get("xlabel"):
        ax.set_xlabel(kwargs["xlabel"])
    if kwargs.get("ylabel"):
        ax.set_ylabel(kwargs["ylabel"])

    if not fig.get_constrained_layout():
        fig.tight_layout()

    save = kwargs.get("save")
    if save:
        from pyscattviz.plotting.io import save_fig as _save

        _save(fig, save)

    return ax


def surface_contour(
    x,
    y,
    z,
    ax=None,
    interactive: bool = False,
    **kwargs,
) -> Any:
    """Combined surface with projected contour below.

    Parameters
    ----------
    x, y, z : array-like
        Data arrays.
    ax : Axes3D, optional
    interactive : bool
    **kwargs
        Same as :func:`surface`, plus:

        - **contour_levels** : int — number of contour levels.

    Returns
    -------
    ax : Axes3D or plotly Figure

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> X, Y, Z = pv.make_demo_data('volcano')
    >>> pv.surface_contour(X, Y, Z, cmap='turbo')
    """
    X, Y, Z = _ensure_grid(x, y, z)

    if interactive:
        return _surface_plotly(X, Y, Z, **kwargs)  # plotly surface is already interactive

    fig, ax = _get_3d_ax(ax, kwargs.get("figsize"))
    cmap = kwargs.get("cmap", "viridis")
    alpha = kwargs.get("alpha", 0.8)
    levels = kwargs.get("contour_levels", 10)

    surf = ax.plot_surface(X, Y, Z, cmap=cmap, alpha=alpha, linewidth=0.3, antialiased=True)
    z_offset = np.nanmin(Z) - (np.nanmax(Z) - np.nanmin(Z)) * 0.1
    ax.contour(X, Y, Z, levels=levels, cmap=cmap, linewidths=0.8, offset=z_offset)

    if kwargs.get("colorbar", True):
        fig.colorbar(surf, ax=ax, shrink=0.5, aspect=10)

    _apply_labels_3d(ax, **kwargs)

    save = kwargs.get("save")
    if save:
        from pyscattviz.plotting.io import save_fig as _save

        _save(fig, save)

    return ax


# ---------------------------------------------------------------------------
# Synthetic demo data
# ---------------------------------------------------------------------------


def make_demo_data(
    kind: str = "ripple",
    n: int = 50,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate synthetic 3D data for demos and testing.

    Parameters
    ----------
    kind : str
        One of:

        * ``'gaussian'`` — Gaussian bump.
        * ``'ripple'`` — ``sin(sqrt(x^2 + y^2))``.
        * ``'saddle'`` — ``x^2 - y^2``.
        * ``'volcano'`` — ring-shaped peak.
    n : int
        Grid size per axis.

    Returns
    -------
    X, Y, Z : np.ndarray
        2-D meshgrid arrays.

    Examples
    --------
    >>> from pyscattviz.plotting.plot3d import make_demo_data
    >>> X, Y, Z = make_demo_data('gaussian', n=80)
    >>> X.shape
    (80, 80)
    """
    x = np.linspace(-5, 5, n)
    y = np.linspace(-5, 5, n)
    X, Y = np.meshgrid(x, y)

    funcs = {
        "gaussian": lambda: np.exp(-(X**2 + Y**2) / 10),
        "ripple": lambda: np.sin(np.sqrt(X**2 + Y**2)),
        "saddle": lambda: X**2 - Y**2,
        "volcano": lambda: -np.exp(-(X**2 + Y**2) / 10) + 0.1 * (X**2 + Y**2),
    }

    if kind not in funcs:
        raise ValueError(f"Unknown kind {kind!r}. Choose from: {list(funcs)}")

    Z = funcs[kind]()
    return X, Y, Z


# ---------------------------------------------------------------------------
# Plotly backends
# ---------------------------------------------------------------------------


def _surface_plotly(X, Y, Z, **kwargs):
    import plotly.graph_objects as go

    fig = go.Figure(
        data=[
            go.Surface(
                x=X,
                y=Y,
                z=Z,
                colorscale=kwargs.get("cmap", "viridis"),
                opacity=kwargs.get("alpha", 0.9),
            )
        ]
    )
    layout_kw = _plotly_layout_3d(**kwargs)
    fig.update_layout(**layout_kw)
    return fig


def _wireframe_plotly(X, Y, Z, **kwargs):
    import plotly.graph_objects as go

    # Plotly wireframe via line traces
    lines = []
    color = kwargs.get("color", "black")
    for i in range(X.shape[0]):
        lines.append(
            go.Scatter3d(
                x=X[i, :],
                y=Y[i, :],
                z=Z[i, :],
                mode="lines",
                line=dict(color=color, width=2),
                showlegend=False,
            )
        )
    for j in range(X.shape[1]):
        lines.append(
            go.Scatter3d(
                x=X[:, j],
                y=Y[:, j],
                z=Z[:, j],
                mode="lines",
                line=dict(color=color, width=2),
                showlegend=False,
            )
        )
    fig = go.Figure(data=lines)
    layout_kw = _plotly_layout_3d(**kwargs)
    fig.update_layout(**layout_kw)
    return fig


def _scatter3d_plotly(x, y, z, c, **kwargs):
    import plotly.graph_objects as go

    fig = go.Figure(
        data=[
            go.Scatter3d(
                x=x,
                y=y,
                z=z,
                mode="markers",
                marker=dict(
                    size=kwargs.get("s", 4),
                    color=c,
                    colorscale=kwargs.get("cmap", "viridis"),
                    opacity=kwargs.get("alpha", 0.8),
                    colorbar=dict(title="value"),
                ),
            )
        ]
    )
    layout_kw = _plotly_layout_3d(**kwargs)
    fig.update_layout(**layout_kw)
    return fig


def _contour_plotly(X, Y, Z, **kwargs):
    import plotly.graph_objects as go

    fig = go.Figure(
        data=[
            go.Contour(
                x=X[0, :],
                y=Y[:, 0],
                z=Z,
                colorscale=kwargs.get("cmap", "viridis"),
                contours=dict(
                    coloring="heatmap",
                    showlabels=True,
                ),
            )
        ]
    )
    layout_kw = {}
    if kwargs.get("title"):
        layout_kw["title"] = kwargs["title"]
    if kwargs.get("xlabel"):
        layout_kw["xaxis_title"] = kwargs["xlabel"]
    if kwargs.get("ylabel"):
        layout_kw["yaxis_title"] = kwargs["ylabel"]
    fig.update_layout(**layout_kw)
    return fig


def _plotly_layout_3d(**kwargs):
    layout = {}
    if kwargs.get("title"):
        layout["title"] = kwargs["title"]
    scene = {}
    if kwargs.get("xlabel"):
        scene["xaxis_title"] = kwargs["xlabel"]
    if kwargs.get("ylabel"):
        scene["yaxis_title"] = kwargs["ylabel"]
    if kwargs.get("zlabel"):
        scene["zaxis_title"] = kwargs["zlabel"]
    if scene:
        layout["scene"] = scene
    return layout
