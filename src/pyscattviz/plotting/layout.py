"""
Figure and axes creation utilities for multi-panel layouts.

Provides convenient wrappers around matplotlib's subplot machinery so that
creating common layouts (grids, main+residual panels, mosaics, insets) is
a one-liner.

Adapted from ``create_fig_ax`` / ``create_2ax_main_minor`` in pyScatt and
the multi-axes layout engine in NanoOrganizer.

Examples
--------
>>> import pyscattviz.plotting as pv
>>> fig, axes = pv.create_axes(2, 3, figsize=(12, 6))
>>> len(axes)
6
"""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

__all__ = [
    "create_axes",
    "create_axes_ratio",
    "create_axes_mosaic",
    "create_axes_inset",
]


def create_axes(
    rows: int = 1,
    cols: int = 1,
    figsize: tuple[float, float] | None = None,
    title: str | None = None,
    sharex: bool = False,
    sharey: bool = False,
    **kwargs,
) -> tuple[Figure, list[Axes]]:
    """Create a figure with a grid of subplots.

    Always returns a **flat list** of axes, regardless of the grid shape,
    so indexing is simple: ``axes[0]``, ``axes[1]``, etc.

    Parameters
    ----------
    rows, cols : int
        Number of rows and columns.
    figsize : tuple of float, optional
        Figure size ``(width, height)`` in inches.  Defaults to a reasonable
        size based on the grid.
    title : str, optional
        Super-title for the whole figure.
    sharex, sharey : bool
        Whether subplots share x/y axes.
    **kwargs
        Extra keyword arguments passed to ``plt.subplots()``.

    Returns
    -------
    fig : Figure
    axes : list of Axes
        Flat list of length ``rows * cols``.

    Examples
    --------
    >>> from pyscattviz.plotting.layout import create_axes
    >>> fig, axes = create_axes(2, 2, figsize=(8, 6))
    >>> len(axes)
    4
    >>> axes[0].plot([1, 2, 3])  # top-left

    Single panel:

    >>> fig, axes = create_axes()
    >>> len(axes)
    1
    """
    if figsize is None:
        figsize = (4 * cols, 3 * rows)

    fig, ax_array = plt.subplots(
        rows,
        cols,
        figsize=figsize,
        sharex=sharex,
        sharey=sharey,
        squeeze=False,
        **kwargs,
    )
    axes = list(ax_array.flat)

    if title is not None:
        fig.suptitle(title, fontsize=14, y=1.02)

    if not fig.get_constrained_layout():
        fig.tight_layout()
    return fig, axes


def create_axes_ratio(
    ratio: int = 4,
    orientation: str = "vertical",
    figsize: tuple[float, float] = (8, 6),
    sharex: bool = True,
    **kwargs,
) -> tuple[Figure, Axes, Axes]:
    """Create two axes with a size ratio (e.g. main plot + residual panel).

    Parameters
    ----------
    ratio : int
        Size ratio of the main axis to the minor axis.  ``ratio=4`` means
        the main panel is 4x the height (or width) of the minor panel.
    orientation : str
        ``'vertical'`` (default) stacks the panels vertically (main on top,
        minor below).  ``'horizontal'`` arranges them side by side.
    figsize : tuple of float
        Figure size in inches.
    sharex : bool
        If *True* (default), the two axes share the same x-axis (vertical)
        or y-axis (horizontal).
    **kwargs
        Extra keyword arguments passed to ``plt.figure()``.

    Returns
    -------
    fig : Figure
    ax_main : Axes
        The larger panel.
    ax_minor : Axes
        The smaller panel.

    Examples
    --------
    Main plot with residual panel below:

    >>> from pyscattviz.plotting.layout import create_axes_ratio
    >>> fig, ax_main, ax_resid = create_axes_ratio(ratio=4)
    >>> ax_main.plot(x, y)
    >>> ax_resid.plot(x, residuals)
    """
    fig = plt.figure(figsize=figsize, constrained_layout=True, **kwargs)

    if orientation == "vertical":
        gs = fig.add_gridspec(ratio + 1, 1, wspace=0.0, hspace=0.0)
        ax_main = fig.add_subplot(gs[0:ratio])
        if sharex:
            plt.setp(ax_main.get_xticklabels(), visible=False)
            ax_minor = fig.add_subplot(gs[ratio], sharex=ax_main)
        else:
            ax_minor = fig.add_subplot(gs[ratio])
    else:  # horizontal
        gs = fig.add_gridspec(1, ratio + 1, wspace=0.0, hspace=0.0)
        ax_main = fig.add_subplot(gs[0:ratio])
        if sharex:
            plt.setp(ax_main.get_yticklabels(), visible=False)
            ax_minor = fig.add_subplot(gs[ratio], sharey=ax_main)
        else:
            ax_minor = fig.add_subplot(gs[ratio])

    return fig, ax_main, ax_minor


def create_axes_mosaic(
    layout: list[list[str]] | str,
    figsize: tuple[float, float] | None = None,
    **kwargs,
) -> tuple[Figure, dict[str, Axes]]:
    """Create a named subplot layout using matplotlib's mosaic API.

    Parameters
    ----------
    layout : list of list of str, or str
        Mosaic layout specification.  Each unique string names a subplot.
        Use ``'.'`` for empty cells.

        Example: ``[['A', 'A', 'B'], ['C', 'D', 'B']]`` creates a 2x3
        grid where 'A' spans the top-left two cells, 'B' spans the right
        column, and 'C'/'D' are in the bottom-left.

        Also accepts a multi-line string::

            \"\"\"
            AAB
            CDB
            \"\"\"

    figsize : tuple of float, optional
        Figure size.
    **kwargs
        Extra keyword arguments passed to ``plt.subplot_mosaic()``.

    Returns
    -------
    fig : Figure
    axes : dict of str -> Axes
        Dictionary mapping layout names to their Axes objects.

    Examples
    --------
    >>> from pyscattviz.plotting.layout import create_axes_mosaic
    >>> layout = [['main', 'main', 'side'], ['bot_l', 'bot_r', 'side']]
    >>> fig, axes = create_axes_mosaic(layout, figsize=(10, 6))
    >>> axes['main'].plot(x, y)
    >>> axes['side'].imshow(image)

    Using string layout:

    >>> fig, axes = create_axes_mosaic('AB\\nCC', figsize=(8, 6))
    >>> axes['A'].plot([1, 2, 3])
    """
    if figsize is None:
        figsize = (10, 6)

    fig, axes = plt.subplot_mosaic(
        layout,
        figsize=figsize,
        constrained_layout=True,
        **kwargs,
    )
    return fig, axes


def create_axes_inset(
    ax: Axes,
    bounds: tuple[float, float, float, float] = (0.6, 0.6, 0.35, 0.35),
    **kwargs,
) -> Axes:
    """Add an inset axes to an existing plot.

    Parameters
    ----------
    ax : Axes
        The parent axes.
    bounds : tuple of float
        ``(x, y, width, height)`` in axes-fraction coordinates.
        Default places a small inset in the upper-right corner.
    **kwargs
        Extra keyword arguments passed to ``ax.inset_axes()``.

    Returns
    -------
    ax_inset : Axes
        The inset axes, ready for plotting.

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> fig, axes = pv.create_axes()
    >>> axes[0].plot(x, y)
    >>> ax_in = pv.create_axes_inset(axes[0])
    >>> ax_in.plot(x_zoom, y_zoom)
    """
    ax_inset = ax.inset_axes(bounds, **kwargs)
    return ax_inset
