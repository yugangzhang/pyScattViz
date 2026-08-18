"""
Colors, colormaps, markers, and plotting themes for pyscattviz.plotting.

All custom colormaps are auto-registered with matplotlib on import so that
``cmap='pv_vge_hdr'`` works anywhere.  Original colormap code adapted from
Y.G.@CFN (ColMars.py) and the pyCHX package.

Examples
--------
>>> import pyscattviz.plotting as pv
>>> pv.set_theme('science')          # publication-ready defaults
>>> pv.show_cmaps()                  # visual swatch of all custom cmaps
>>> colors = pv.get_color_cycle(5)   # 5 distinct colors
"""

from __future__ import annotations

import matplotlib as mpl
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

__all__ = [
    # Colormaps
    "CMAP_VGE",
    "CMAP_VGE_HDR",
    "CMAP_ALBULA",
    "CMAP_HDR_ALBULA",
    "CMAP_HDR_GOLDISH",
    "CMAP_CYCLIC",
    "CMAP_JET_EXT",
    # Palettes & markers
    "COLORS",
    "COLORS_10",
    "MARKERS",
    "MARKERS_MATH",
    # Functions
    "list_cmaps",
    "show_cmaps",
    "set_theme",
    "theme_context",
    "get_color_cycle",
    "get_marker_cycle",
]

# ---------------------------------------------------------------------------
# Custom colormaps
# Adapted from Y.G.@CFN ColMars.py — original colors for X-ray scattering
# ---------------------------------------------------------------------------

_CMAP_DEFS: dict[str, list[list[float]]] = {
    "pv_vge": [
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 254 / 255],
        [188 / 255, 2 / 255, 107 / 255],
        [254 / 255, 55 / 255, 0.0],
        [254 / 255, 254 / 255, 0.0],
        [254 / 255, 254 / 255, 254 / 255],
    ],
    "pv_vge_hdr": [
        [1.0, 1.0, 1.0],
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0],
        [188 / 255, 0.0, 107 / 255],
        [254 / 255, 55 / 255, 0.0],
        [254 / 255, 254 / 255, 0.0],
        [254 / 255, 254 / 255, 254 / 255],
    ],
    "pv_albula": [
        [1.0, 1.0, 1.0],
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [1.0, 1.0, 0.0],
    ],
    "pv_hdr_goldish": [
        [1.0, 1.0, 1.0],
        [0.0, 0.0, 0.0],
        [100 / 255, 127 / 255, 1.0],
        [0.0, 0.0, 127 / 255],
        [127 / 255, 60 / 255, 0.0],
        [1.0, 1.0, 0.0],
        [200 / 255, 0.0, 0.0],
        [1.0, 1.0, 1.0],
    ],
    "pv_cyclic": [
        [1.0, 0.0, 0.0],
        [1.0, 165 / 255, 0.0],
        [1.0, 1.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.2, 1.0],
        [148 / 255, 0.0, 211 / 255],
        [1.0, 0.0, 0.0],
    ],
    "pv_jet_ext": [
        [0, 0, 0],
        [0.18, 0, 0.18],
        [0, 0, 0.5],
        [0, 0, 1],
        [0.0, 0.389, 1.0],
        [0.0, 0.833, 1.0],
        [0.305, 1.0, 0.663],
        [0.663, 1.0, 0.305],
        [1.0, 0.901, 0.0],
        [1.0, 0.490, 0.0],
        [1.0, 0.078, 0.0],
        [1, 0, 0],
        [0.5, 0.0, 0.0],
    ],
}

# Build and register colormaps, including reversed variants
_REGISTERED_CMAPS: dict[str, mcolors.LinearSegmentedColormap] = {}

for _name, _colors in _CMAP_DEFS.items():
    _cmap = mcolors.LinearSegmentedColormap.from_list(_name, _colors)
    _cmap_r = mcolors.LinearSegmentedColormap.from_list(f"{_name}_r", _colors[::-1])
    try:
        mpl.colormaps.register(_cmap, name=_name)
        mpl.colormaps.register(_cmap_r, name=f"{_name}_r")
    except ValueError:
        pass  # Already registered (e.g. reimport)
    _REGISTERED_CMAPS[_name] = _cmap
    _REGISTERED_CMAPS[f"{_name}_r"] = _cmap_r

# Module-level constants for direct access
CMAP_VGE = _REGISTERED_CMAPS["pv_vge"]
CMAP_VGE_HDR = _REGISTERED_CMAPS["pv_vge_hdr"]
CMAP_ALBULA = _REGISTERED_CMAPS["pv_albula"]
CMAP_HDR_ALBULA = _REGISTERED_CMAPS["pv_albula"]  # alias
CMAP_HDR_GOLDISH = _REGISTERED_CMAPS["pv_hdr_goldish"]
CMAP_CYCLIC = _REGISTERED_CMAPS["pv_cyclic"]
CMAP_JET_EXT = _REGISTERED_CMAPS["pv_jet_ext"]

# ---------------------------------------------------------------------------
# Color palettes
# ---------------------------------------------------------------------------

#: Top-10 distinct colors (matplotlib tab10 cycle)
COLORS_10: list[str] = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]

#: Large color pool for many-curve plots (adapted from ColMars.py)
COLORS: list[str] = [
    "blue",
    "red",
    "green",
    "black",
    "cyan",
    "magenta",
    "brown",
    "orange",
    "purple",
    "navy",
    "darkcyan",
    "darkred",
    "darkolivegreen",
    "hotpink",
    "gray",
    "dodgerblue",
    "teal",
    "steelblue",
    "crimson",
    "forestgreen",
    "tomato",
    "coral",
    "gold",
    "indigo",
    "orchid",
    "salmon",
    "turquoise",
    "sienna",
    "limegreen",
    "slateblue",
    "peru",
    "chocolate",
    "darkviolet",
    "cadetblue",
    "goldenrod",
    "mediumseagreen",
    "royalblue",
    "firebrick",
    "darkorange",
    "mediumturquoise",
    "darkblue",
    "yellowgreen",
    "springgreen",
    "deepskyblue",
    "saddlebrown",
    "khaki",
    "blueviolet",
    "orangered",
    "mediumvioletred",
    "lightcoral",
    "cornflowerblue",
    "darkmagenta",
    "olive",
    "plum",
    "seagreen",
    "mediumpurple",
    "darkgoldenrod",
    "rosybrown",
    "darkturquoise",
    "tan",
    "skyblue",
    "greenyellow",
    "lightsalmon",
    "indianred",
    "darksalmon",
    "palevioletred",
    "lawngreen",
    "mediumorchid",
    "mediumblue",
    "deeppink",
    "mediumslateblue",
    "sandybrown",
    "darkseagreen",
    "lightseagreen",
]

# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------

#: Standard marker set (24 variants)
MARKERS: list[str] = [
    "o",
    "D",
    "v",
    "^",
    "<",
    ">",
    "p",
    "s",
    "H",
    "h",
    "*",
    "d",
    "8",
    "1",
    "3",
    "2",
    "4",
    "+",
    "x",
    "_",
    "|",
    ",",
    "P",
    "X",
]

#: Mathematical symbol markers for labeling distinct datasets
MARKERS_MATH: list[str] = [
    "$I$",
    "$L$",
    "$O$",
    "$V$",
    "$E$",
    "$c$",
    "$h$",
    "$x$",
    "$b$",
    "$e$",
    "$a$",
    "$m$",
    "$l$",
    "$i$",
    "$n$",
]

# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------

_THEME_PARAMS: dict[str, dict] = {
    "science": {
        "font.family": "serif",
        "font.size": 10,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 9,
        "figure.figsize": (6, 4),
        "axes.linewidth": 0.8,
        "lines.linewidth": 1.5,
        "lines.markersize": 5,
        "axes.grid": False,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    },
    "present": {
        "font.family": "sans-serif",
        "font.size": 14,
        "axes.labelsize": 18,
        "axes.titlesize": 20,
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "legend.fontsize": 14,
        "figure.figsize": (10, 7),
        "axes.linewidth": 1.5,
        "lines.linewidth": 2.5,
        "lines.markersize": 8,
        "axes.grid": True,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
    },
    "notebook": {
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.labelsize": 13,
        "axes.titlesize": 14,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "legend.fontsize": 10,
        "figure.figsize": (8, 5),
        "axes.linewidth": 1.0,
        "lines.linewidth": 2.0,
        "lines.markersize": 6,
        "axes.grid": True,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
    },
    "poster": {
        "font.family": "sans-serif",
        "font.size": 18,
        "axes.labelsize": 24,
        "axes.titlesize": 26,
        "xtick.labelsize": 18,
        "ytick.labelsize": 18,
        "legend.fontsize": 18,
        "figure.figsize": (14, 10),
        "axes.linewidth": 2.0,
        "lines.linewidth": 3.0,
        "lines.markersize": 10,
        "axes.grid": True,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    },
}


def list_cmaps() -> list[str]:
    """Return names of all pyScattViz-registered colormaps.

    Returns
    -------
    names : list of str
        Sorted colormap names (e.g. ``['pv_albula', 'pv_albula_r', ...]``).

    Examples
    --------
    >>> from pyscattviz.plotting.style import list_cmaps
    >>> list_cmaps()
    ['pv_albula', 'pv_albula_r', 'pv_cyclic', ...]
    """
    return sorted(_REGISTERED_CMAPS.keys())


def show_cmaps(figsize: tuple[float, float] = (12, 6)):
    """Display a visual swatch of all pyScattViz-registered colormaps.

    Parameters
    ----------
    figsize : tuple of float, optional
        Figure size ``(width, height)`` in inches.

    Examples
    --------
    >>> from pyscattviz.plotting.style import show_cmaps
    >>> show_cmaps()
    """
    names = [n for n in sorted(_REGISTERED_CMAPS) if not n.endswith("_r")]
    gradient = np.linspace(0, 1, 256).reshape(1, -1)

    fig, axes = plt.subplots(
        nrows=len(names),
        figsize=figsize,
        constrained_layout=True,
    )
    if len(names) == 1:
        axes = [axes]

    for ax, name in zip(axes, names):
        ax.imshow(gradient, aspect="auto", cmap=_REGISTERED_CMAPS[name])
        ax.set_ylabel(name, rotation=0, ha="right", va="center", fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])

    fig.suptitle("pyScattViz Colormaps", fontsize=14)
    return fig


def set_theme(
    style: str = "science",
    context: str | None = None,
    palette: str | list[str] | None = None,
):
    """Set the global plotting theme.

    Combines seaborn theming with custom matplotlib rcParams.

    Parameters
    ----------
    style : str
        One of ``'science'``, ``'present'``, ``'notebook'``, ``'poster'``.
    context : str, optional
        Seaborn context override (``'paper'``, ``'notebook'``, ``'talk'``,
        ``'poster'``).  If *None*, a sensible default is chosen per style.
    palette : str or list of str, optional
        Seaborn color palette name or list of colors.

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> pv.set_theme('science')                # publication-ready
    >>> pv.set_theme('present', palette='deep') # for talks
    """
    params = _THEME_PARAMS.get(style)
    if params is None:
        raise ValueError(f"Unknown style {style!r}. Choose from: {list(_THEME_PARAMS)}")

    _context_map = {
        "science": "paper",
        "present": "talk",
        "notebook": "notebook",
        "poster": "poster",
    }
    ctx = context or _context_map.get(style, "notebook")
    pal = palette or COLORS_10

    sns.set_theme(context=ctx, style="ticks", palette=pal)
    mpl.rcParams.update(params)


class theme_context:
    """Context manager for temporary theme changes.

    Parameters
    ----------
    style : str
        Theme style name (see :func:`set_theme`).
    **kwargs
        Extra keyword arguments passed to :func:`set_theme`.

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> with pv.theme_context('poster'):
    ...     pv.plot1d(data)  # uses poster theme
    >>> # Back to previous theme
    """

    def __init__(self, style: str = "science", **kwargs):
        self._style = style
        self._kwargs = kwargs
        self._old_params: dict = {}

    def __enter__(self):
        self._old_params = mpl.rcParams.copy()
        set_theme(self._style, **self._kwargs)
        return self

    def __exit__(self, *exc):
        mpl.rcParams.update(self._old_params)
        return False


def get_color_cycle(n: int = 10, palette: str | list[str] = "default") -> list[str]:
    """Get *n* distinct colors from a palette.

    Parameters
    ----------
    n : int
        Number of colors.
    palette : str or list of str
        ``'default'`` uses :data:`COLORS_10` (cycling if *n* > 10).
        Any seaborn palette name is also accepted.

    Returns
    -------
    colors : list of str
        Hex color strings.

    Examples
    --------
    >>> from pyscattviz.plotting.style import get_color_cycle
    >>> get_color_cycle(3)
    ['#1f77b4', '#ff7f0e', '#2ca02c']
    """
    if palette == "default":
        return [COLORS_10[i % len(COLORS_10)] for i in range(n)]
    return [mcolors.to_hex(c) for c in sns.color_palette(palette, n)]


def get_marker_cycle(n: int = 10) -> list[str]:
    """Get *n* distinct markers, cycling through :data:`MARKERS`.

    Parameters
    ----------
    n : int
        Number of markers.

    Returns
    -------
    markers : list of str
        Marker style strings.

    Examples
    --------
    >>> from pyscattviz.plotting.style import get_marker_cycle
    >>> get_marker_cycle(3)
    ['o', 'D', 'v']
    """
    return [MARKERS[i % len(MARKERS)] for i in range(n)]
