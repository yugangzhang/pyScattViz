"""
N-dimensional visualization: pairplots, multi-hue scatter, parallel
coordinates, and correlation matrices.

For exploring relationships in high-dimensional datasets — materials
properties, synthesis parameters, scattering features, etc.

Adapted from ``multi_hue_pairplot`` in pyScatt by Y.G.@CFN.

Examples
--------
>>> import pyscattviz.plotting as pv
>>> import pandas as pd, numpy as np
>>> df = pd.DataFrame(np.random.randn(100, 4), columns=list('ABCD'))
>>> pv.pairplot(df, hue=None)
"""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from matplotlib.figure import Figure

__all__ = [
    "pairplot",
    "multi_hue_pairplot",
    "parallel_coords",
    "correlation_matrix",
]


# ---------------------------------------------------------------------------
# pairplot
# ---------------------------------------------------------------------------


def pairplot(
    data,
    vars: list[str] | None = None,
    hue: str | None = None,
    interactive: bool = False,
    **kwargs,
) -> Figure | Any:
    """Enhanced seaborn pairplot for multi-dimensional data.

    Parameters
    ----------
    data : DataFrame
        Tabular data with numeric columns.
    vars : list of str, optional
        Subset of columns to include.
    hue : str, optional
        Column name used for color grouping.
    interactive : bool
        If *True*, return a plotly Figure (scatter matrix).
    **kwargs
        Passed to ``seaborn.pairplot()`` or plotly.  Common:

        - **palette** : str — color palette.
        - **diag_kind** : str — ``'auto'``, ``'hist'``, ``'kde'``.
        - **markers** : str or list.
        - **height** : float — height of each facet.
        - **corner** : bool — only lower triangle.

    Returns
    -------
    fig : Figure (seaborn PairGrid.figure) or plotly Figure

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> import pandas as pd, numpy as np
    >>> df = pd.DataFrame(np.random.randn(200, 4), columns=list('ABCD'))
    >>> df['group'] = np.random.choice(['x', 'y'], 200)
    >>> pv.pairplot(df, hue='group', palette='Set1')

    Interactive:

    >>> fig = pv.pairplot(df, hue='group', interactive=True)
    """
    if interactive:
        return _pairplot_plotly(data, vars=vars, hue=hue, **kwargs)

    palette = kwargs.pop("palette", None)
    diag_kind = kwargs.pop("diag_kind", "auto")
    height = kwargs.pop("height", 2.5)
    corner = kwargs.pop("corner", False)
    markers = kwargs.pop("markers", None)

    g = sns.pairplot(
        data,
        vars=vars,
        hue=hue,
        palette=palette,
        diag_kind=diag_kind,
        height=height,
        corner=corner,
        markers=markers,
        **kwargs,
    )
    return g.figure


# ---------------------------------------------------------------------------
# multi_hue_pairplot
# ---------------------------------------------------------------------------


def multi_hue_pairplot(
    data,
    x_vars: list[str],
    y_vars: list[str],
    hues: list[str],
    palettes: str | list[str] = "Spectral",
    interactive: bool = False,
    **kwargs,
) -> Figure | Any:
    """Scatter grid with multiple hue dimensions.

    Creates a grid where each row uses a different hue column, and each
    cell is an (x, y) scatter colored by that hue.

    Parameters
    ----------
    data : DataFrame
        Tabular data.
    x_vars : list of str
        Columns for the x-axis.
    y_vars : list of str
        Columns for the y-axis.
    hues : list of str
        Column names used as hue for each row.
    palettes : str or list of str
        Palette(s) for each hue row.
    interactive : bool
        If *True*, return a plotly Figure.
    **kwargs
        - **figsize** : tuple — figure size.
        - **s** : int — marker size (default 60).
        - **edgecolor** : str — marker edge color.
        - **grid** : bool — show grid.
        - **legend_loc** : str — legend location.

    Returns
    -------
    fig : Figure or plotly Figure

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> import pandas as pd, numpy as np
    >>> df = pd.DataFrame({
    ...     'x1': np.random.rand(50), 'x2': np.random.rand(50),
    ...     'y1': np.random.rand(50),
    ...     'hue_a': np.random.choice(['A','B'], 50),
    ...     'hue_b': np.random.rand(50),
    ... })
    >>> pv.multi_hue_pairplot(df, x_vars=['x1','x2'], y_vars=['y1'],
    ...                       hues=['hue_a','hue_b'])
    """
    if isinstance(palettes, str):
        palettes = [palettes] * len(hues)

    figsize = kwargs.get("figsize", (4 * len(x_vars) * len(y_vars), 4 * len(hues)))
    s = kwargs.get("s", 60)
    edgecolor = kwargs.get("edgecolor", "k")
    grid = kwargs.get("grid", True)
    legend_loc = kwargs.get("legend_loc", "best")

    ncols = len(y_vars) * len(x_vars)
    nrows = len(hues)

    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=figsize, squeeze=False)

    for hue_idx, hue in enumerate(hues):
        palette = palettes[min(hue_idx, len(palettes) - 1)]
        for y_idx, yvar in enumerate(y_vars):
            for x_idx, xvar in enumerate(x_vars):
                col = y_idx * len(x_vars) + x_idx
                ax = axes[hue_idx, col]
                sns.scatterplot(
                    data=data,
                    x=xvar,
                    y=yvar,
                    hue=hue,
                    palette=palette,
                    s=s,
                    edgecolor=edgecolor,
                    ax=ax,
                )
                ax.set_title(f"{xvar} vs {yvar} (hue={hue})", fontsize=10)
                if grid:
                    ax.grid(True, alpha=0.3)
                ax.legend(title=hue, loc=legend_loc, fontsize=8, title_fontsize=9)

    if not fig.get_constrained_layout():
        fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# parallel_coords
# ---------------------------------------------------------------------------


def parallel_coords(
    data,
    class_column: str | None = None,
    cols: list[str] | None = None,
    interactive: bool = False,
    **kwargs,
) -> Any:
    """Parallel coordinates plot for high-dimensional data.

    Parameters
    ----------
    data : DataFrame
        Tabular data.
    class_column : str, optional
        Column used for coloring lines.
    cols : list of str, optional
        Subset of numeric columns to include.  If *None*, uses all numeric
        columns.
    interactive : bool
        If *True*, return a plotly Figure.
    **kwargs
        - **cmap** or **palette** : str — colormap/palette.
        - **alpha** : float — line transparency.
        - **figsize** : tuple.
        - **title** : str.

    Returns
    -------
    ax : Axes or plotly Figure

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> import pandas as pd, numpy as np
    >>> df = pd.DataFrame(np.random.randn(50, 4), columns=list('ABCD'))
    >>> df['cls'] = np.random.choice(['x', 'y'], 50)
    >>> pv.parallel_coords(df, class_column='cls', palette='Set2')
    """
    import pandas as pd

    if interactive:
        return _parallel_plotly(data, class_column=class_column, cols=cols, **kwargs)

    if cols is not None:
        plot_cols = cols + ([class_column] if class_column else [])
        plot_data = data[plot_cols]
    else:
        plot_data = data

    figsize = kwargs.get("figsize", (10, 5))
    fig, ax = plt.subplots(figsize=figsize)
    palette = kwargs.get("palette") or kwargs.get("cmap", "Set2")
    alpha = kwargs.get("alpha", 0.5)

    pd.plotting.parallel_coordinates(
        plot_data,
        class_column=class_column or plot_data.columns[-1],
        ax=ax,
        colormap=palette if isinstance(palette, str) else None,
        alpha=alpha,
    )
    ax.grid(True, alpha=0.3)

    title = kwargs.get("title")
    if title:
        ax.set_title(title, fontsize=14)

    ax.legend(loc="best", fontsize=9)
    if not fig.get_constrained_layout():
        fig.tight_layout()

    save = kwargs.get("save")
    if save:
        from pyscattviz.plotting.io import save_fig as _save

        _save(fig, save)

    return ax


# ---------------------------------------------------------------------------
# correlation_matrix
# ---------------------------------------------------------------------------


def correlation_matrix(
    data,
    method: str = "pearson",
    interactive: bool = False,
    **kwargs,
) -> Any:
    """Correlation heatmap with optional clustering.

    Parameters
    ----------
    data : DataFrame
        Tabular data (numeric columns).
    method : str
        Correlation method: ``'pearson'``, ``'spearman'``, ``'kendall'``.
    interactive : bool
        If *True*, return a plotly Figure.
    **kwargs
        - **cmap** : str — colormap (default ``'RdBu_r'``).
        - **annot** : bool — annotate cells (default *True*).
        - **fmt** : str — annotation format.
        - **figsize** : tuple.
        - **title** : str.
        - **mask_upper** : bool — mask upper triangle (default *False*).
          Kept for backwards compatibility; prefer **mask_half**.
        - **mask_half** : str or None — ``'upper'`` or ``'lower'`` to mask
          that half of the original (pre-flip) matrix.  *None* shows all.
        - **flip** : bool — flip rows so the diagonal runs from bottom-left
          to top-right (default *True*).
        - **diag_labels** : bool — show column names on the diagonal
          (default *False*).
        - **vmin**, **vmax** : float — color limits (default -1 to 1).

    Returns
    -------
    ax : Axes or plotly Figure

    Examples
    --------
    >>> import pyscattviz.plotting as pv
    >>> import pandas as pd, numpy as np
    >>> df = pd.DataFrame(np.random.randn(100, 5), columns=list('ABCDE'))
    >>> pv.correlation_matrix(df, title='Correlation')
    """
    corr = data.select_dtypes(include=[np.number]).corr(method=method)

    if interactive:
        return _corr_plotly(corr, **kwargs)

    figsize = kwargs.get("figsize", (8, 6))
    fig, ax = plt.subplots(figsize=figsize)

    cmap = kwargs.get("cmap", "RdBu_r")
    annot = kwargs.get("annot", True)
    fmt = kwargs.get("fmt", ".2f")
    vmin = kwargs.get("vmin", -1)
    vmax = kwargs.get("vmax", 1)
    mask_upper = kwargs.get("mask_upper", False)
    mask_half = kwargs.get("mask_half", None)
    flip = kwargs.get("flip", True)
    diag_labels = kwargs.get("diag_labels", False)

    mask = None
    if mask_half == "upper" or (mask_upper and mask_half is None):
        mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    elif mask_half == "lower":
        mask = np.tril(np.ones_like(corr, dtype=bool), k=-1)

    # Flip rows so diagonal runs bottom-left → top-right
    if flip:
        corr = corr.iloc[::-1]
        if mask is not None:
            mask = mask[::-1]

    sns.heatmap(
        corr,
        ax=ax,
        cmap=cmap,
        annot=annot,
        fmt=fmt,
        vmin=vmin,
        vmax=vmax,
        mask=mask,
        square=True,
        linewidths=0.5,
    )

    if diag_labels:
        n = len(corr)
        for i, col_name in enumerate(corr.columns):
            row = (n - 1 - i) if flip else i
            ax.text(
                i + 0.5,
                row + 0.5,
                col_name,
                ha="center",
                va="center",
                fontsize=kwargs.get("diag_fontsize", 11),
                fontweight="bold",
            )

    title = kwargs.get("title")
    if title:
        ax.set_title(title, fontsize=14)

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


def _pairplot_plotly(data, vars=None, hue=None, **kwargs):
    import plotly.express as px

    dimensions = vars or [c for c in data.columns if data[c].dtype.kind in "iuf"]
    fig = px.scatter_matrix(
        data,
        dimensions=dimensions,
        color=hue,
        color_continuous_scale=kwargs.get("palette", kwargs.get("cmap")),
    )
    fig.update_traces(diagonal_visible=False, marker=dict(size=3))
    title = kwargs.get("title")
    if title:
        fig.update_layout(title=title)
    return fig


def _parallel_plotly(data, class_column=None, cols=None, **kwargs):
    import pandas as pd
    import plotly.express as px

    if cols is None:
        cols = [c for c in data.columns if data[c].dtype.kind in "iuf"]

    # plotly parallel_coordinates needs numeric color column
    color_col = class_column
    plot_data = data.copy()
    if class_column is not None and plot_data[class_column].dtype.kind not in "iuf":
        # Encode categorical to numeric
        codes, _uniques = pd.factorize(plot_data[class_column])
        plot_data[f"__{class_column}_code"] = codes
        color_col = f"__{class_column}_code"

    fig = px.parallel_coordinates(
        plot_data,
        dimensions=cols,
        color=color_col,
        color_continuous_scale=kwargs.get("cmap", "viridis"),
    )
    title = kwargs.get("title")
    if title:
        fig.update_layout(title=title)
    return fig


def _corr_plotly(corr, **kwargs):
    import plotly.express as px

    fig = px.imshow(
        corr,
        color_continuous_scale=kwargs.get("cmap", "RdBu_r"),
        zmin=kwargs.get("vmin", -1),
        zmax=kwargs.get("vmax", 1),
        text_auto=".2f" if kwargs.get("annot", True) else False,
    )
    title = kwargs.get("title")
    if title:
        fig.update_layout(title=title)
    return fig
