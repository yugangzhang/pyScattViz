"""
1D plotting: lines, scatter, error bars, fits.

The workhorse module for plotting one-dimensional data — I(q), spectra,
kinetics, time series, etc.  Every function accepts numpy arrays, lists,
pandas Series, or DataFrames and returns a matplotlib ``Axes`` (or a plotly
``Figure`` when ``interactive=True``).

Adapted from ``plot1D`` / ``plot_xy_with_fit`` in pyScatt by Y.G.@CFN.

Examples
--------
>>> import pyscattviz.plotting as pv
>>> import numpy as np
>>> x = np.linspace(0, 10, 200)
>>> pv.plot1d(np.sin(x), x=x, title='Sine Wave')
"""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes

from pyscattviz.plotting._data_adapter import extract_xy, to_array
from pyscattviz.plotting.labels import sanitize_label
from pyscattviz.plotting.style import get_color_cycle, get_marker_cycle

__all__ = [
    "plot1d",
    "plot1d_with_fit",
    "plot1d_multi",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_ax(ax, figsize=None):
    """Return (fig, ax), creating a new figure if *ax* is None."""
    if ax is None:
        fs = figsize or (8, 5)
        fig, ax = plt.subplots(figsize=fs)
    else:
        fig = ax.get_figure()
    return fig, ax


def _apply_common(ax, **kw):
    """Apply common axis decorations from kwargs."""
    if kw.get("logx") or kw.get("logxy"):
        ax.set_xscale("log")
    if kw.get("logy") or kw.get("logxy"):
        ax.set_yscale("log")
    if "xlim" in kw and kw["xlim"] is not None:
        ax.set_xlim(kw["xlim"])
    if "ylim" in kw and kw["ylim"] is not None:
        ax.set_ylim(kw["ylim"])
    if "xlabel" in kw and kw["xlabel"] is not None:
        ax.set_xlabel(sanitize_label(kw["xlabel"]))
    if "ylabel" in kw and kw["ylabel"] is not None:
        ax.set_ylabel(sanitize_label(kw["ylabel"]))
    if "title" in kw and kw["title"] is not None:
        ax.set_title(sanitize_label(kw["title"]))
    if "grid" in kw:
        if kw["grid"]:
            ax.grid(True, alpha=0.3)
        else:
            ax.grid(False)


def _plot1d_plotly(y, x=None, yerr=None, **kwargs):
    """Plotly backend for plot1d (interactive mode)."""
    import plotly.graph_objects as go

    x_arr = x if x is not None else np.arange(len(y))
    marker = kwargs.get("marker") or kwargs.get("m")
    color = kwargs.get("color") or kwargs.get("c")
    legend = kwargs.get("legend")
    ls = kwargs.get("ls", "-")

    mode = "lines+markers" if marker else "lines"
    if ls == "" or ls == "none" or ls is None:
        mode = "markers"

    trace_kw = dict(x=x_arr, y=y, name=legend or "", mode=mode)
    if color:
        trace_kw["line"] = dict(color=color)
        trace_kw["marker"] = dict(color=color)

    fig = go.Figure()
    if yerr is not None:
        yerr = np.asarray(yerr)
        trace_kw["error_y"] = dict(type="data", array=yerr, visible=True)
    fig.add_trace(go.Scatter(**trace_kw))

    layout_kw = {}
    if kwargs.get("logx") or kwargs.get("logxy"):
        layout_kw["xaxis_type"] = "log"
    if kwargs.get("logy") or kwargs.get("logxy"):
        layout_kw["yaxis_type"] = "log"
    if "title" in kwargs:
        layout_kw["title"] = kwargs["title"]
    if "xlabel" in kwargs:
        layout_kw["xaxis_title"] = kwargs["xlabel"]
    if "ylabel" in kwargs:
        layout_kw["yaxis_title"] = kwargs["ylabel"]
    if "xlim" in kwargs and kwargs["xlim"] is not None:
        layout_kw["xaxis_range"] = list(kwargs["xlim"])
    if "ylim" in kwargs and kwargs["ylim"] is not None:
        layout_kw["yaxis_range"] = list(kwargs["ylim"])

    fig.update_layout(**layout_kw)
    return fig


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plot1d(
    y,
    x=None,
    yerr=None,
    ax: Axes | None = None,
    data=None,
    interactive: bool = False,
    **kwargs,
) -> Axes | Any:
    """Plot 1D data as line, scatter, or line+scatter.

    Parameters
    ----------
    y : array-like, Series, or str
        Y-axis data.  If *data* is a DataFrame, pass a column name string.
    x : array-like, Series, or str, optional
        X-axis data.  If *None*, uses ``np.arange(len(y))``.
    yerr : array-like, optional
        Error bars.  Symmetric (1-D) or asymmetric ``(lo, hi)`` tuple.
    ax : matplotlib.axes.Axes, optional
        Axes to plot on.  If *None*, creates a new figure.
    data : DataFrame, optional
        If provided, *x* and *y* are interpreted as column name strings.
    interactive : bool
        If *True*, return a plotly ``Figure`` instead of matplotlib ``Axes``.
    **kwargs
        Styling and decoration:

        - **logx**, **logy**, **logxy** : bool — log-scale axes.
        - **marker** (or **m**) : str — marker style (e.g. ``'o'``).
        - **color** (or **c**) : str — line/marker color.
        - **ls** : str — line style (default ``'-'``).
        - **lw** : float — line width.
        - **alpha** : float — transparency (0–1).
        - **markersize** : float — marker size.
        - **xlim**, **ylim** : tuple — axis limits.
        - **xlabel**, **ylabel**, **title** : str — labels.
        - **legend** : str — legend label for this curve.
        - **legend_size** : float — legend font size.
        - **figsize** : tuple — figure size (only when *ax* is None).
        - **grid** : bool — show grid.
        - **save** : str or Path — save figure to this path.

    Returns
    -------
    ax : matplotlib.axes.Axes
        The axes with the plot (matplotlib mode).
    fig : plotly.graph_objects.Figure
        Interactive figure (plotly mode, when ``interactive=True``).

    Examples
    --------
    Simple line plot:

    >>> import pyscattviz.plotting as pv
    >>> import numpy as np
    >>> x = np.linspace(0, 10, 100)
    >>> pv.plot1d(np.sin(x), x=x, title='Sine Wave')

    Log-log scatter with error bars:

    >>> q = np.logspace(-3, 0, 200)
    >>> I = 1e4 * q**-2
    >>> pv.plot1d(I, x=q, logxy=True, marker='o', ls='', ylabel='I(q)')

    From a DataFrame:

    >>> import pandas as pd
    >>> df = pd.DataFrame({'q': q, 'I': I})
    >>> pv.plot1d(data=df, x='q', y='I', logxy=True)

    Interactive (plotly):

    >>> fig = pv.plot1d(np.sin(x), x=x, interactive=True)
    >>> fig.show()
    """
    # Resolve data
    x_arr, y_arr, x_label, y_label = extract_xy(data=data, x=x, y=y)

    if y_arr is None:
        raise ValueError("y data is required")

    if x_arr is None:
        x_arr = np.arange(len(y_arr))

    yerr_arr = None
    if yerr is not None:
        yerr_arr, _ = to_array(yerr)

    # Auto-fill labels from data adapter
    kwargs.setdefault("xlabel", x_label)
    kwargs.setdefault("ylabel", y_label)
    if "legend" not in kwargs and y_label is not None:
        kwargs["legend"] = y_label

    # --- Plotly path ---
    if interactive:
        return _plot1d_plotly(y_arr, x=x_arr, yerr=yerr_arr, **kwargs)

    # --- Matplotlib path ---
    fig, ax = _get_ax(ax, kwargs.get("figsize"))

    marker = kwargs.get("marker") or kwargs.get("m")
    color = kwargs.get("color") or kwargs.get("c")
    ls = kwargs.get("ls", "-")
    lw = kwargs.get("lw")
    alpha = kwargs.get("alpha", 1.0)
    markersize = kwargs.get("markersize")
    legend = kwargs.get("legend")

    if yerr_arr is None:
        ax.plot(
            x_arr,
            y_arr,
            marker=marker,
            color=color,
            ls=ls,
            lw=lw,
            markersize=markersize,
            alpha=alpha,
            label=legend if legend else None,
        )
    else:
        ax.errorbar(
            x_arr,
            y_arr,
            yerr_arr,
            marker=marker,
            color=color,
            ls=ls,
            lw=lw,
            markersize=markersize,
            alpha=alpha,
            label=legend if legend else None,
        )

    _apply_common(ax, **kwargs)

    legend_size = kwargs.get("legend_size")
    if legend:
        ax.legend(loc="best", fontsize=legend_size)

    # Save if requested
    save = kwargs.get("save")
    if save:
        from pyscattviz.plotting.io import save_fig as _save

        _save(fig, save)

    return ax


def plot1d_with_fit(
    x,
    y,
    xf,
    yf,
    ax: Axes | None = None,
    interactive: bool = False,
    **kwargs,
) -> Axes | Any:
    """Plot data with an overlay fit curve.

    Parameters
    ----------
    x, y : array-like
        Measured data points.
    xf, yf : array-like
        Fit curve (typically denser than data).
    ax : Axes, optional
        Axes to plot on.
    interactive : bool
        If *True*, return a plotly Figure.
    **kwargs
        Passed through to :func:`plot1d` for both curves.  Additional:

        - **fit_color** : str — color of the fit line (default ``'red'``).
        - **fit_label** : str — legend label for fit (default ``'fit'``).
        - **data_label** : str — legend label for data (default ``'data'``).
        - **txts** : str — text annotation (e.g. fit parameters).

    Returns
    -------
    ax : Axes or plotly Figure

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> import numpy as np
    >>> x = np.linspace(0, 5, 30)
    >>> y = 2.5 * np.exp(-x / 1.5) + np.random.normal(0, 0.1, 30)
    >>> xf = np.linspace(0, 5, 200)
    >>> yf = 2.5 * np.exp(-xf / 1.5)
    >>> pv.plot1d_with_fit(x, y, xf, yf, ylabel='Signal')
    """
    x_arr, _ = to_array(x)
    y_arr, _ = to_array(y)
    xf_arr, _ = to_array(xf)
    yf_arr, _ = to_array(yf)

    fit_color = kwargs.pop("fit_color", "red")
    fit_label = kwargs.pop("fit_label", "fit")
    data_label = kwargs.pop("data_label", "data")
    txts = kwargs.pop("txts", None)

    if interactive:
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_arr,
                y=y_arr,
                mode="markers",
                name=data_label,
                marker=dict(color="black"),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=xf_arr,
                y=yf_arr,
                mode="lines",
                name=fit_label,
                line=dict(color=fit_color),
            )
        )
        layout_kw = {}
        if kwargs.get("logx") or kwargs.get("logxy"):
            layout_kw["xaxis_type"] = "log"
        if kwargs.get("logy") or kwargs.get("logxy"):
            layout_kw["yaxis_type"] = "log"
        if "title" in kwargs:
            layout_kw["title"] = kwargs["title"]
        if "xlabel" in kwargs:
            layout_kw["xaxis_title"] = kwargs["xlabel"]
        if "ylabel" in kwargs:
            layout_kw["yaxis_title"] = kwargs["ylabel"]
        fig.update_layout(**layout_kw)
        return fig

    # Matplotlib
    fig, ax = _get_ax(ax, kwargs.get("figsize"))

    ax.plot(x_arr, y_arr, "o", color="black", label=data_label, markersize=4)
    ax.plot(xf_arr, yf_arr, "-", color=fit_color, label=fit_label, lw=2)

    _apply_common(ax, **kwargs)
    ax.legend(loc="best")

    if txts is not None:
        ax.text(
            0.02,
            0.2,
            txts,
            fontsize=10,
            transform=ax.transAxes,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

    if not fig.get_constrained_layout():
        fig.tight_layout()

    save = kwargs.get("save")
    if save:
        from pyscattviz.plotting.io import save_fig as _save

        _save(fig, save)

    return ax


def plot1d_multi(
    datasets: list[dict | tuple],
    ax: Axes | None = None,
    interactive: bool = False,
    **kwargs,
) -> Axes | Any:
    """Plot multiple 1D curves on the same axes with auto-styling.

    Parameters
    ----------
    datasets : list
        Each element is one of:

        * ``dict`` with keys ``'x'``, ``'y'``, and optional ``'yerr'``,
          ``'label'``, ``'color'``, ``'marker'``, ``'ls'``, etc.
        * ``(x, y)`` tuple.
        * ``(x, y, yerr)`` tuple.
        * ``(x, y, label)`` tuple where *label* is a string.

    ax : Axes, optional
        Axes to plot on.
    interactive : bool
        If *True*, return a plotly Figure.
    **kwargs
        Common settings applied to all curves (``logx``, ``logy``,
        ``xlim``, ``ylim``, ``xlabel``, ``ylabel``, ``title``, ``grid``,
        ``figsize``, ``save``).

    Returns
    -------
    ax : Axes or plotly Figure

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> import numpy as np
    >>> x = np.linspace(0, 10, 100)
    >>> pv.plot1d_multi([
    ...     {'x': x, 'y': np.sin(x), 'label': 'sin'},
    ...     {'x': x, 'y': np.cos(x), 'label': 'cos'},
    ... ], title='Trig Functions')

    Tuple shorthand:

    >>> pv.plot1d_multi([
    ...     (x, np.sin(x), 'sin'),
    ...     (x, np.cos(x), 'cos'),
    ... ])
    """
    colors = get_color_cycle(len(datasets))
    markers = get_marker_cycle(len(datasets))

    if interactive:
        import plotly.graph_objects as go

        fig = go.Figure()
        for i, ds in enumerate(datasets):
            ds = _normalize_dataset(ds, i, colors, markers)
            trace_kw = dict(
                x=ds["x"],
                y=ds["y"],
                name=ds.get("label", f"curve {i}"),
                mode="lines+markers" if ds.get("marker") else "lines",
            )
            if ds.get("color"):
                trace_kw["line"] = dict(color=ds["color"])
            if ds.get("yerr") is not None:
                trace_kw["error_y"] = dict(
                    type="data",
                    array=ds["yerr"],
                    visible=True,
                )
            fig.add_trace(go.Scatter(**trace_kw))

        layout_kw = {}
        if kwargs.get("logx") or kwargs.get("logxy"):
            layout_kw["xaxis_type"] = "log"
        if kwargs.get("logy") or kwargs.get("logxy"):
            layout_kw["yaxis_type"] = "log"
        if "title" in kwargs:
            layout_kw["title"] = kwargs["title"]
        if "xlabel" in kwargs:
            layout_kw["xaxis_title"] = kwargs["xlabel"]
        if "ylabel" in kwargs:
            layout_kw["yaxis_title"] = kwargs["ylabel"]
        fig.update_layout(**layout_kw)
        return fig

    # Matplotlib
    fig, ax = _get_ax(ax, kwargs.get("figsize"))

    for i, ds in enumerate(datasets):
        ds = _normalize_dataset(ds, i, colors, markers)

        plot_kw = dict(
            marker=ds.get("marker"),
            color=ds.get("color", colors[i % len(colors)]),
            ls=ds.get("ls", "-"),
            lw=ds.get("lw"),
            markersize=ds.get("markersize"),
            alpha=ds.get("alpha", 1.0),
            label=ds.get("label", f"curve {i}"),
        )

        if ds.get("yerr") is not None:
            ax.errorbar(ds["x"], ds["y"], ds["yerr"], **plot_kw)
        else:
            ax.plot(ds["x"], ds["y"], **plot_kw)

    _apply_common(ax, **kwargs)
    ax.legend(loc="best")

    save = kwargs.get("save")
    if save:
        from pyscattviz.plotting.io import save_fig as _save

        _save(fig, save)

    return ax


def _normalize_dataset(ds, idx, colors, markers):
    """Normalize a dataset entry to a dict with 'x', 'y', etc."""
    if isinstance(ds, dict):
        d = dict(ds)
        d["x"], _ = to_array(d.get("x"))
        d["y"], y_label = to_array(d.get("y"))
        if d["x"] is None:
            d["x"] = np.arange(len(d["y"]))
        if "label" not in d and y_label:
            d["label"] = y_label
        if "yerr" in d and d["yerr"] is not None:
            d["yerr"], _ = to_array(d["yerr"])
        d.setdefault("color", colors[idx % len(colors)])
        return d

    # Tuple form
    t = tuple(ds)
    d = {"color": colors[idx % len(colors)]}
    if len(t) == 2:
        d["x"], _ = to_array(t[0])
        d["y"], y_label = to_array(t[1])
        if y_label:
            d["label"] = y_label
    elif len(t) == 3:
        d["x"], _ = to_array(t[0])
        d["y"], _ = to_array(t[1])
        if isinstance(t[2], str):
            d["label"] = t[2]
        else:
            d["yerr"], _ = to_array(t[2])
    else:
        raise ValueError(f"Dataset tuple must have 2 or 3 elements, got {len(t)}")

    return d
