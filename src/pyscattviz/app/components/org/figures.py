"""Figures of the Org pages: arrays in, a Plotly figure out.

Nothing here reads a file or computes a result a reader would keep; the
2-D panels are pyScattViz's (:func:`heatmap_fig`, its masking and
log-axis handling), the curves are drawn the way its 1-D panels are.

Limits are ``(lo, hi)`` pairs, either side None for auto: an axis then
frames the data — not the blank around a remeshed image — and a colour or
intensity scale spans what lies inside the window shown, so narrowing q
rescales I to match.
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple, Union

import numpy as np
import plotly.graph_objects as go
from plotly.colors import sample_colorscale
from plotly.subplots import make_subplots

from pyscattviz.app.components import scattering as sv

CMAPS = sv.CMAPS
LINE_CMAPS = ["Viridis", "Plasma", "Turbo", "Cividis", "Inferno", "Jet", "Rainbow"]

Limits = Optional[Tuple[Optional[float], Optional[float]]]


def colors(n: int, cmap: str = "Viridis") -> list:
    """*n* colours spread over a Plotly colour scale."""
    if n <= 0:
        return []
    return sample_colorscale(cmap, [0.5] if n == 1 else list(np.linspace(0, 0.95, n)))


def _light(figure: go.Figure) -> go.Figure:
    """Heat maps sent as float32: half the bytes, no visible difference."""
    for trace in figure.data:
        if trace.type == "heatmap" and trace.z is not None:
            trace.z = np.asarray(trace.z, dtype=np.float32)
    return figure


# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------


def span(values, *, positive: bool = False) -> Optional[Tuple[float, float]]:
    """``(min, max)`` of the finite (and, with *positive*, > 0) *values*."""
    values = np.asarray(values, float).ravel()
    values = values[np.isfinite(values) & ((values > 0) if positive else True)]
    if not values.size:
        return None
    return float(values.min()), float(values.max())


def filled(given: Limits, auto: Limits) -> Optional[Tuple[float, float]]:
    """*given*, its blank sides taken from *auto*; None unless both are known."""
    lo, hi = given or (None, None)
    a_lo, a_hi = auto or (None, None)
    lo, hi = (a_lo if lo is None else lo), (a_hi if hi is None else hi)
    if lo is None or hi is None or not lo < hi:
        return None
    return float(lo), float(hi)


def _inside(axis, limits: Limits, n: int) -> np.ndarray:
    axis = np.asarray(axis, float) if axis is not None else np.arange(n, dtype=float)
    if axis.shape != (n,):
        return np.ones(n, bool)
    keep = np.ones(n, bool)
    lo, hi = limits or (None, None)
    if lo is not None:
        keep &= axis >= lo
    if hi is not None:
        keep &= axis <= hi
    return keep


def _padded(lo: float, hi: float, log: bool, pad: float = 0.04) -> Tuple[float, float]:
    if log:
        lo, hi = np.log10(lo), np.log10(hi)
    width = (hi - lo) * pad or (abs(hi) * pad or 1.0)
    lo, hi = lo - width, hi + width
    return (10**lo, 10**hi) if log else (lo, hi)


def image_limits(
    z, x, y, x_range: Limits = None, y_range: Limits = None, vmin=None, vmax=None, *, log=True
):
    """The window and colour scale a map is drawn on: blank sides of the
    axes frame the data (:func:`~scattering.data_extent`), blank colour
    limits span 1–99.5 % of the intensities inside that window.
    Returns ``(x_range, y_range, vmin, vmax)``."""
    z = np.asarray(z, float)
    box = sv.data_extent(z, x, y) if z.ndim == 2 else None
    x_range = filled(x_range, box[:2] if box else None)
    y_range = filled(y_range, box[2:] if box else None)
    if (vmin is None or vmax is None) and z.ndim == 2:
        part = z[np.ix_(_inside(y, y_range, z.shape[0]), _inside(x, x_range, z.shape[1]))]
        part = part[np.isfinite(part) & ((part > 0) if log else True)]
        if part.size:
            lo, hi = np.percentile(part, [1.0, 99.5])
            vmin = float(lo) if vmin is None else vmin
            vmax = float(hi) if vmax is None else vmax
    return x_range, y_range, vmin, vmax


def curve_limits(
    curves: Sequence[Tuple[np.ndarray, np.ndarray]],
    x_range: Limits = None,
    y_range: Limits = None,
    *,
    logx: bool = False,
    logy: bool = True,
):
    """The window curves ``(x, y)`` are drawn on: blank x sides frame the
    points that can be drawn, blank y sides span the points inside the x
    window, a little padded. Returns ``(x_range, y_range)``."""
    xs, ys = [], []
    for x, y in curves:
        x, y = np.asarray(x, float), np.asarray(y, float)
        usable = np.isfinite(x) & np.isfinite(y)
        if logx:
            usable &= x > 0
        if logy:
            usable &= y > 0
        xs.append(x[usable])
        ys.append(y[usable])
    x_all = np.concatenate(xs) if xs else np.array([])
    y_all = np.concatenate(ys) if ys else np.array([])
    x_range = filled(x_range, span(x_all))
    keep = _inside(x_all, x_range, x_all.size)
    auto = None
    if keep.any():
        inside = y_all[keep]
        lo = float(np.percentile(inside, 0.5)) if logy else float(inside.min())
        hi = float(inside.max())
        if hi > lo:
            auto = _padded(lo, hi, logy)
    return x_range, filled(y_range, auto)


def value_colors(values, cmap: str, lo: float, hi: float) -> list:
    """The colour of each value on a colour scale running *lo* → *hi*."""
    values = np.asarray(values, float)
    span = (hi - lo) or 1.0
    where = np.clip(np.nan_to_num((values - lo) / span, nan=0.0), 0, 1) * 0.95
    return sample_colorscale(cmap, list(where))


def image_figure(
    z,
    x,
    y,
    xlabel: str,
    ylabel: str,
    *,
    mask=None,
    title: str = "",
    cmap: str = "Turbo",
    log: bool = True,
    vmin=None,
    vmax=None,
    x_range: Limits = None,
    y_range: Limits = None,
    aspect: Union[None, str, float] = None,
    xlog: bool = False,
    height: int = 420,
) -> go.Figure:
    """A 2-D map on its axes: no-data blanked, framed and scaled as
    :func:`image_limits` says, decimated, log intensity. *aspect*:
    ``"equal"``, a y:x ratio, or None (free)."""
    z = sv.apply_mask(z, mask)
    x_range, y_range, vmin, vmax = image_limits(z, x, y, x_range, y_range, vmin, vmax, log=log)
    z, x, y = sv.downsample(z, x, y)
    return _light(
        sv.heatmap_fig(
            title,
            z,
            x,
            y,
            xlabel,
            ylabel,
            cmap=cmap,
            logI=log,
            vmin_I=vmin,
            vmax_I=vmax,
            x_range=x_range,
            y_range=y_range,
            aspect=aspect,
            xlog=xlog,
            height=height,
        )
    )


def curves_figure(
    curves: Sequence[Tuple[str, np.ndarray, np.ndarray]],
    *,
    logx: bool = True,
    logy: bool = True,
    offset: float = 1.0,
    cmap: Optional[str] = None,
    line_colors: Optional[Sequence] = None,
    x_range: Limits = None,
    y_range: Limits = None,
    title: str = "",
    xlabel: str = "q (Å⁻¹)",
    ylabel: str = "I(q)",
    height: int = 420,
    legend: bool = True,
    colorbar: Optional[Tuple[str, float, float]] = None,
    width: float = 1.4,
    markers: bool = False,
    style: Optional[dict] = None,
) -> go.Figure:
    """I(q) curves, one trace each, ``(label, q, I)``.

    *offset* stacks them: each curve is multiplied by ``offset**i`` on a log
    axis, shifted by ``i * offset`` on a linear one (1 / 0: no offset).
    *colorbar* ``(title, lo, hi)`` adds a colour bar for *cmap* — the curves
    are then coloured by that quantity. The window is :func:`curve_limits`'.
    *style* (:func:`~scattering.curve_style_controls`) styles every curve
    instead of *width* and *markers*.
    """
    figure = go.Figure()
    shades = (
        list(line_colors)
        if line_colors is not None
        else (colors(len(curves), cmap) if cmap else [None] * len(curves))
    )
    drawn = []
    for i, (label, q, iq) in enumerate(curves):
        iq = np.asarray(iq, float)
        if logy:
            iq = iq * (offset**i) if offset and offset > 0 else iq
        elif offset:
            iq = iq + i * offset
        drawn.append((q, iq))
        trace = dict(x=q, y=iq, name=str(label))
        if style is not None:
            sv.apply_curve_style(trace, style, base_color=shades[i])
        else:
            trace["mode"] = "lines+markers" if markers else "lines"
            trace["line"] = dict(width=width)
            trace["marker"] = dict(size=max(3.0, 2.5 * width))
            if shades[i] is not None:
                trace["line"]["color"] = shades[i]
        figure.add_trace(go.Scatter(**trace))
    x_range, y_range = curve_limits(drawn, x_range, y_range, logx=logx, logy=logy)
    if colorbar is not None and cmap:
        name, lo, hi = colorbar
        figure.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                showlegend=False,
                hoverinfo="skip",
                marker=dict(
                    colorscale=cmap,
                    cmin=lo,
                    cmax=hi,
                    color=[lo],
                    size=0.1,
                    showscale=True,
                    colorbar=dict(title=name),
                ),
            )
        )
    sv.style_1d_axes(figure, logx, logy)
    figure.update_xaxes(title_text=xlabel, range=sv.axrange(*(x_range or (None, None)), logx))
    figure.update_yaxes(title_text=ylabel, range=sv.axrange(*(y_range or (None, None)), logy))
    figure.update_layout(
        title=title,
        height=height,
        template="plotly_white",
        showlegend=legend,
        margin=dict(l=55, r=10, t=40, b=45),
        legend=dict(font=dict(size=10)),
    )
    return figure


def waterfall_figure(
    q,
    values,
    iq,
    ylabel: str,
    *,
    title: str = "",
    cmap: str = "Turbo",
    log: bool = True,
    logq: bool = False,
    vmin=None,
    vmax=None,
    q_range: Limits = None,
    y_range: Limits = None,
    height: int = 460,
    marker: Optional[float] = None,
) -> go.Figure:
    """I(q) of a run as a map: q across, the run's axis (time, RH …) up.

    Rows are drawn in order of *values*; *marker* draws a line at one value
    (the frame shown beside it). Framed and scaled as :func:`image_limits`
    says."""
    values = np.asarray(values, float)
    order = np.argsort(values, kind="stable")
    z = sv.apply_mask(np.asarray(iq, float)[order], None)
    q_range, y_range, vmin, vmax = image_limits(
        z, np.asarray(q, float), values[order], q_range, y_range, vmin, vmax, log=log
    )
    # A 600-frame spin is 600 × 1400 values: decimated for the browser.
    z, qs, ys = sv.downsample(z, np.asarray(q, float), values[order], max_pixels=250_000)
    figure = _light(
        sv.heatmap_fig(
            title,
            z,
            qs,
            ys,
            "q (Å⁻¹)",
            ylabel,
            cmap=cmap,
            logI=log,
            vmin_I=vmin,
            vmax_I=vmax,
            x_range=q_range,
            y_range=y_range,
            xlog=logq,
            height=height,
        )
    )
    if marker is not None and np.isfinite(marker):
        figure.add_hline(y=float(marker), line=dict(color="white", width=1, dash="dot"))
    return figure


def conditions_figure(
    t,
    series: Dict[str, np.ndarray],
    xlabel: str,
    *,
    marker: Optional[float] = None,
    height: int = 260,
) -> go.Figure:
    """What the cell read during a run (RH, T …), against its time axis;
    the second quantity on its own axis."""
    names = [k for k, v in series.items() if np.isfinite(np.asarray(v, float)).any()]
    figure = make_subplots(specs=[[{"secondary_y": len(names) > 1}]])
    palette = ["#1f77b4", "#d62728", "#2ca02c"]
    for i, name in enumerate(names):
        values = np.asarray(series[name], float)
        figure.add_trace(
            go.Scatter(
                x=t,
                y=values,
                name=name,
                mode="lines+markers",
                marker=dict(size=4),
                line=dict(color=palette[i % 3]),
            ),
            secondary_y=(i == 1),
        )
        # A controller holding 70.00 ± 0.02 °C is steady, not noisy: show at
        # least 1 unit (or 5 % of the reading) of axis.
        lo, hi = np.nanmin(values), np.nanmax(values)
        half = max(hi - lo, 1.0, 0.05 * abs((lo + hi) / 2)) * 0.55
        middle = (lo + hi) / 2
        figure.update_yaxes(
            title_text=name, secondary_y=(i == 1), range=[middle - half, middle + half]
        )
    if marker is not None and np.isfinite(marker):
        figure.add_vline(x=float(marker), line=dict(color="grey", width=1, dash="dot"))
    figure.update_xaxes(title_text=xlabel)
    figure.update_layout(
        height=height,
        template="plotly_white",
        margin=dict(l=55, r=10, t=30, b=45),
        legend=dict(orientation="h", y=1.12),
    )
    return figure


def trend_figure(
    x,
    series: Dict[str, np.ndarray],
    xlabel: str,
    *,
    marker: Optional[float] = None,
    height: int = 420,
) -> go.Figure:
    """Several quantities against one axis, a panel each, x shared — a
    peak's area, position and width along a run."""
    names = list(series)
    figure = make_subplots(rows=len(names), cols=1, shared_xaxes=True, vertical_spacing=0.06)
    order = np.argsort(np.asarray(x, float), kind="stable")
    for i, name in enumerate(names, start=1):
        figure.add_trace(
            go.Scatter(
                x=np.asarray(x, float)[order],
                y=np.asarray(series[name], float)[order],
                name=name,
                mode="lines+markers",
                marker=dict(size=4),
                line=dict(color="#1f2a44"),
            ),
            row=i,
            col=1,
        )
        figure.update_yaxes(title_text=name, row=i, col=1)
    if marker is not None and np.isfinite(marker):
        figure.add_vline(x=float(marker), line=dict(color="grey", width=1, dash="dot"))
    figure.update_xaxes(title_text=xlabel, row=len(names), col=1)
    figure.update_layout(
        height=height,
        template="plotly_white",
        showlegend=False,
        margin=dict(l=55, r=10, t=20, b=45),
    )
    return figure


__all__ = [
    "CMAPS",
    "LINE_CMAPS",
    "span",
    "filled",
    "image_limits",
    "curve_limits",
    "colors",
    "value_colors",
    "image_figure",
    "curves_figure",
    "waterfall_figure",
    "conditions_figure",
    "trend_figure",
]
