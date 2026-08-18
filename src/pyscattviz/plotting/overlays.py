"""
Annotations and overlays for matplotlib axes.

ROI mask overlays, guide lines, colored region patches, and text boxes.
These functions *add to* existing axes — they don't create new figures.

Adapted from ``show_label_array`` / ``add_lines_patches`` in pyScatt
by Y.G.@CFN.

Examples
--------
>>> import pyscattviz.plotting as pv
>>> import numpy as np
>>> fig, axes = pv.create_axes()
>>> axes[0].plot(np.sin(np.linspace(0, 10, 100)))
>>> pv.add_vlines(axes[0], [2.0, 5.0, 8.0], color='red', ls='--')
"""

from __future__ import annotations

import copy

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes

__all__ = [
    "overlay_mask",
    "overlay_mask_on_image",
    "add_vlines",
    "add_hlines",
    "add_patches",
    "add_region_patches",
    "add_text_box",
]


def overlay_mask(
    ax: Axes,
    label_array: np.ndarray,
    alpha: float = 0.5,
    cmap: str = "viridis",
    interpolation: str = "nearest",
    **kwargs,
):
    """Display labeled ROI regions on an axes.

    Background (label == 0) is shown as transparent white.

    Parameters
    ----------
    ax : Axes
        The axes to add the overlay to.
    label_array : np.ndarray
        Integer array where 0 = background, positive integers = ROI labels.
    alpha : float
        Overlay transparency.
    cmap : str
        Colormap for the labels.
    interpolation : str
        Interpolation method.
    **kwargs
        Extra keyword arguments passed to ``ax.imshow()``.

    Returns
    -------
    im : AxesImage

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> import numpy as np
    >>> mask = np.zeros((100, 100), dtype=int)
    >>> mask[20:40, 20:40] = 1
    >>> mask[60:80, 60:80] = 2
    >>> fig, axes = pv.create_axes()
    >>> pv.overlay_mask(axes[0], mask)
    """
    _cmap = copy.copy(plt.colormaps.get_cmap(cmap))
    _cmap.set_under("w", 0)
    vmin = max(0.5, kwargs.pop("vmin", 0.5))
    im = ax.imshow(
        label_array,
        cmap=_cmap,
        interpolation=interpolation,
        vmin=vmin,
        alpha=alpha,
        **kwargs,
    )
    return im


def overlay_mask_on_image(
    ax: Axes,
    image: np.ndarray,
    label_array: np.ndarray,
    alpha: float = 0.3,
    log_img: bool = True,
    vmin: float | None = None,
    vmax: float | None = None,
    image_cmap: str = "gray",
    mask_cmap: str = "viridis",
    **kwargs,
):
    """Overlay a labeled mask on top of an image with transparency.

    Parameters
    ----------
    ax : Axes
        The axes to add the overlay to.
    image : np.ndarray
        Background image.
    label_array : np.ndarray
        ROI mask (0 = background).
    alpha : float
        Mask transparency.
    log_img : bool
        If *True*, display the image with ``LogNorm``.
    vmin, vmax : float, optional
        Image intensity limits.
    image_cmap : str
        Colormap for the background image.
    mask_cmap : str
        Colormap for the mask overlay.

    Returns
    -------
    im : AxesImage
        The image artist.
    im_label : AxesImage
        The mask overlay artist.

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> import numpy as np
    >>> img = np.random.exponential(10, (100, 100))
    >>> mask = np.zeros((100, 100), dtype=int)
    >>> mask[30:70, 30:70] = 1
    >>> fig, axes = pv.create_axes()
    >>> pv.overlay_mask_on_image(axes[0], img, mask)
    """
    from matplotlib.colors import LogNorm

    ax.set_aspect("equal")

    if vmin is None:
        vmin = 0.1
    if vmax is None:
        vmax = float(np.percentile(image[image > 0], 99)) if np.any(image > 0) else 5.0

    if log_img:
        im = ax.imshow(
            image,
            cmap=image_cmap,
            interpolation="none",
            norm=LogNorm(vmin=vmin, vmax=vmax),
            **kwargs,
        )
    else:
        im = ax.imshow(
            image,
            cmap=image_cmap,
            interpolation="none",
            vmin=vmin,
            vmax=vmax,
            **kwargs,
        )

    im_label = overlay_mask(ax, label_array, alpha=alpha, cmap=mask_cmap)
    return im, im_label


def add_vlines(
    ax: Axes,
    positions: list[float] | np.ndarray,
    ymin: float | None = None,
    ymax: float | None = None,
    color: str = "red",
    ls: str = "--",
    lw: float = 1.0,
    alpha: float = 0.8,
    **kwargs,
):
    """Add vertical reference lines to an axes.

    Parameters
    ----------
    ax : Axes
        Target axes.
    positions : list of float
        X-coordinates for the vertical lines.
    ymin, ymax : float, optional
        Y-range for the lines.  Defaults to current axis limits.
    color : str
        Line color.
    ls : str
        Line style.
    lw : float
        Line width.
    alpha : float
        Transparency.

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> fig, axes = pv.create_axes()
    >>> axes[0].plot([0, 10], [0, 10])
    >>> pv.add_vlines(axes[0], [3, 7], color='blue')
    """
    for pos in positions:
        ax.axvline(x=pos, color=color, ls=ls, lw=lw, alpha=alpha, **kwargs)


def add_hlines(
    ax: Axes,
    positions: list[float] | np.ndarray,
    color: str = "red",
    ls: str = "--",
    lw: float = 1.0,
    alpha: float = 0.8,
    **kwargs,
):
    """Add horizontal reference lines to an axes.

    Parameters
    ----------
    ax : Axes
        Target axes.
    positions : list of float
        Y-coordinates for the horizontal lines.
    color, ls, lw, alpha
        Line styling (same as :func:`add_vlines`).

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> fig, axes = pv.create_axes()
    >>> axes[0].plot([0, 10], [0, 10])
    >>> pv.add_hlines(axes[0], [3, 7], color='green', ls=':')
    """
    for pos in positions:
        ax.axhline(y=pos, color=color, ls=ls, lw=lw, alpha=alpha, **kwargs)


def add_patches(
    ax: Axes,
    regions: list[tuple[float, float, float, float]],
    colors: list[str] | None = None,
    alpha: float = 0.2,
    **kwargs,
):
    """Add colored rectangular patches to an axes.

    Parameters
    ----------
    ax : Axes
        Target axes.
    regions : list of tuple
        Each region is ``(x, y, width, height)`` in data coordinates.
    colors : list of str, optional
        Colors for each patch.  Defaults to
        ``['red', 'green', 'blue', 'grey', ...]``.
    alpha : float
        Patch transparency.

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> fig, axes = pv.create_axes()
    >>> axes[0].plot([0, 10], [0, 10])
    >>> pv.add_patches(axes[0], [(0, 0, 3, 10), (3, 0, 4, 10)])
    """
    default_colors = ["red", "green", "blue", "grey", "orange", "purple"]
    if colors is None:
        colors = default_colors

    for i, (x, y, w, h) in enumerate(regions):
        c = colors[i % len(colors)]
        rect = mpatches.Rectangle(
            (x, y),
            w,
            h,
            linewidth=1,
            edgecolor="none",
            facecolor=c,
            alpha=alpha,
            **kwargs,
        )
        ax.add_patch(rect)


def add_region_patches(
    ax: Axes,
    boundaries: list[float],
    y_range: tuple[float, float],
    colors: list[str] | None = None,
    alpha: float = 0.2,
    show_lines: bool = True,
    line_ls: str = "--",
):
    """Add colored region patches between vertical boundaries.

    A convenience wrapper that divides the x-axis into regions at the
    given boundaries and fills each region with a color.

    Parameters
    ----------
    ax : Axes
        Target axes.
    boundaries : list of float
        X-coordinates that separate regions.  N boundaries create N+1
        regions (or fewer if axis limits are used).
    y_range : tuple of float
        ``(ymin, ymax)`` for the patches.
    colors : list of str, optional
        Colors for each region.
    alpha : float
        Patch transparency.
    show_lines : bool
        If *True*, also draw dashed vertical lines at boundaries.
    line_ls : str
        Line style for boundary lines.

    Examples
    --------
    Adapted from pyScatt ``add_lines_patches``:

    >>> import pyscattviz.plotting as pv
    >>> fig, axes = pv.create_axes()
    >>> axes[0].plot(range(30), range(30))
    >>> pv.add_region_patches(axes[0], [10, 20], (0, 30))
    """
    default_colors = ["red", "green", "grey", "blue", "orange"]
    if colors is None:
        colors = default_colors

    ymin, ymax = y_range
    h = ymax - ymin

    if show_lines:
        for b in boundaries:
            ax.axvline(x=b, ymin=0, ymax=1, ls=line_ls, color=colors[0], alpha=0.6)

    # Build region edges
    xlim = ax.get_xlim()
    edges = [xlim[0]] + sorted(boundaries) + [xlim[1]]

    for i in range(len(edges) - 1):
        c = colors[i % len(colors)]
        w = edges[i + 1] - edges[i]
        rect = mpatches.Rectangle(
            (edges[i], ymin),
            w,
            h,
            linewidth=0,
            facecolor=c,
            alpha=alpha,
        )
        ax.add_patch(rect)


def add_text_box(
    ax: Axes,
    text: str,
    loc: str = "upper right",
    fontsize: float = 10,
    alpha: float = 0.7,
    **kwargs,
):
    """Add a text box annotation to an axes.

    Parameters
    ----------
    ax : Axes
        Target axes.
    text : str
        Text content (supports newlines).
    loc : str
        Position: ``'upper right'``, ``'upper left'``, ``'lower right'``,
        ``'lower left'``, ``'center'``.
    fontsize : float
        Font size.
    alpha : float
        Background transparency.

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> fig, axes = pv.create_axes()
    >>> axes[0].plot([1, 2, 3])
    >>> pv.add_text_box(axes[0], 'peak = 2.5\\nFWHM = 0.3')
    """
    loc_map = {
        "upper right": (0.97, 0.97, "right", "top"),
        "upper left": (0.03, 0.97, "left", "top"),
        "lower right": (0.97, 0.03, "right", "bottom"),
        "lower left": (0.03, 0.03, "left", "bottom"),
        "center": (0.5, 0.5, "center", "center"),
    }

    x, y, ha, va = loc_map.get(loc, loc_map["upper right"])

    bbox = kwargs.pop("bbox", dict(boxstyle="round", facecolor="wheat", alpha=alpha))
    ax.text(
        x,
        y,
        text,
        transform=ax.transAxes,
        fontsize=fontsize,
        verticalalignment=va,
        horizontalalignment=ha,
        bbox=bbox,
        **kwargs,
    )
