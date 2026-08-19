"""Publication-figure helpers for selected scattering curves."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from pyscattviz.dataio import integrate_curve
from pyscattviz.plotting import theme_context

# What matplotlib understands, phrased the way a person would say it. The GUI
# offers these; the values are passed straight through.
MARKERS = {
    "none": None,
    "circle": "o",
    "square": "s",
    "triangle": "^",
    "triangle down": "v",
    "diamond": "D",
    "plus": "+",
    "cross": "x",
    "star": "*",
    "point": ".",
}
LINE_STYLES = {"solid": "-", "dashed": "--", "dash-dot": "-.", "dotted": ":", "none": "None"}
LEGEND_LOCATIONS = (
    "best",
    "upper right",
    "upper left",
    "lower left",
    "lower right",
    "center left",
    "center right",
    "upper center",
    "lower center",
)
TICK_DIRECTIONS = ("in", "out", "inout")


@dataclass
class CurveStyle:
    """How one curve is drawn. Every field maps to a matplotlib argument."""

    color: str | None = None  # None follows the theme's colour cycle
    linestyle: str = "-"
    linewidth: float = 1.6
    marker: str | None = None
    markersize: float = 5.0
    markevery: int = 1
    alpha: float = 1.0
    label: str | None = None  # None keeps the curve's own name


@dataclass(frozen=True)
class Curve:
    """One named scattering curve used in a publication plot."""

    name: str
    q: np.ndarray
    intensity: np.ndarray


def compact_label(value: str, max_length: int = 64) -> str:
    """Shorten a long detector filename while preserving both ends."""

    if max_length < 12:
        raise ValueError("max_length must be at least 12")
    if len(value) <= max_length:
        return value
    left = max_length // 2
    right = max_length - left - 1
    return f"{value[:left]}…{value[-right:]}"


def prepare_curve(
    curve: Curve,
    *,
    q_min: float | None = None,
    q_max: float | None = None,
    normalization: str = "none",
) -> Curve:
    """Remove invalid points, apply a q range, and optionally normalize."""

    q = np.asarray(curve.q, dtype=float)
    intensity = np.asarray(curve.intensity, dtype=float)
    if q.ndim != 1 or intensity.ndim != 1 or q.shape != intensity.shape:
        raise ValueError("q and intensity must be one-dimensional arrays of equal length")

    keep = np.isfinite(q) & np.isfinite(intensity)
    if q_min is not None:
        keep &= q >= q_min
    if q_max is not None:
        keep &= q <= q_max
    q = q[keep]
    intensity = intensity[keep]
    if not q.size:
        raise ValueError(f"{curve.name!r} has no finite points in the selected q range")

    mode = normalization.lower()
    if mode == "maximum":
        scale = float(np.nanmax(np.abs(intensity)))
        if scale <= 0:
            raise ValueError(f"{curve.name!r} cannot be normalized by a zero maximum")
        intensity = intensity / scale
    elif mode == "integral":
        scale = abs(integrate_curve(intensity, q))
        if scale <= 0:
            raise ValueError(f"{curve.name!r} cannot be normalized by a zero integral")
        intensity = intensity / scale
    elif mode != "none":
        raise ValueError("normalization must be none, maximum, or integral")

    return Curve(curve.name, q, intensity)


def build_curve_figure(
    curves: Iterable[Curve],
    *,
    theme: str = "science",
    normalization: str = "none",
    q_min: float | None = None,
    q_max: float | None = None,
    offset: float = 0.0,
    logx: bool = True,
    logy: bool = True,
    title: str = "",
    xlabel: str = r"q ($\AA^{-1}$)",
    ylabel: str = "I(q)",
    figsize: tuple[float, float] = (7.0, 5.0),
    legend: bool = True,
    max_label_length: int = 64,
    styles: Iterable[CurveStyle] | None = None,
    multiplier: float = 1.0,
    xlim: tuple[float | None, float | None] | None = None,
    ylim: tuple[float | None, float | None] | None = None,
    grid: bool = False,
    minor_grid: bool = False,
    grid_alpha: float = 0.3,
    minor_ticks: bool = True,
    tick_direction: str = "in",
    tick_top: bool = True,
    tick_right: bool = True,
    tick_length: float = 4.0,
    tick_width: float = 1.0,
    spine_width: float = 1.0,
    font_size: float | None = None,
    dpi: int = 150,
    legend_location: str = "best",
    legend_columns: int = 1,
    legend_font_size: float = 9.0,
    legend_frame: bool = True,
) -> Figure:
    """Build a static, export-ready overlay from selected scattering curves.

    Everything matplotlib exposes for a line plot is reachable here: per-curve
    colour, line style, width, marker, marker size and spacing, and opacity
    through ``styles``; axis limits, tick direction and length, grids, spine
    width, font sizes and the legend through the keyword arguments.
    """

    prepared = [
        prepare_curve(curve, q_min=q_min, q_max=q_max, normalization=normalization)
        for curve in curves
    ]
    if not prepared:
        raise ValueError("at least one curve is required")

    style_list = list(styles or [])
    with theme_context(theme):
        if font_size:
            plt.rcParams.update(
                {
                    "font.size": font_size,
                    "axes.labelsize": font_size + 1,
                    "axes.titlesize": font_size + 2,
                    "xtick.labelsize": font_size - 1,
                    "ytick.labelsize": font_size - 1,
                }
            )
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

        for index, curve in enumerate(prepared):
            intensity = curve.intensity * (float(multiplier) ** index) + index * float(offset)
            keep = curve.q > 0 if logx else np.ones(curve.q.shape, dtype=bool)
            if logy:
                keep = keep & (intensity > 0)
            if not keep.any():
                raise ValueError(f"{curve.name!r} has no positive points for the selected log axes")
            style = style_list[index] if index < len(style_list) else CurveStyle()
            ax.plot(
                curve.q[keep],
                intensity[keep],
                color=style.color,
                linestyle=style.linestyle,
                linewidth=style.linewidth,
                marker=style.marker,
                markersize=style.markersize,
                markevery=max(1, int(style.markevery)),
                alpha=style.alpha,
                label=style.label or compact_label(curve.name, max_label_length),
            )

        if logx:
            ax.set_xscale("log")
        if logy:
            ax.set_yscale("log")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if title:
            ax.set_title(title)
        if xlim and None not in xlim:
            ax.set_xlim(*xlim)
        if ylim and None not in ylim:
            ax.set_ylim(*ylim)

        # Passing alpha with grid(False) makes matplotlib turn the grid back on.
        if grid:
            ax.grid(True, which="major", alpha=grid_alpha)
        else:
            ax.grid(False, which="major")
        if minor_grid:
            ax.grid(True, which="minor", alpha=grid_alpha * 0.5)
        if minor_ticks:
            ax.minorticks_on()
        ax.tick_params(
            which="both",
            direction=tick_direction,
            top=tick_top,
            right=tick_right,
            length=tick_length,
            width=tick_width,
        )
        for spine in ax.spines.values():
            spine.set_linewidth(spine_width)

        if legend:
            ax.legend(
                loc=legend_location,
                ncol=max(1, int(legend_columns)),
                fontsize=legend_font_size,
                frameon=legend_frame,
            )
        elif ax.legend_ is not None:
            ax.legend_.remove()
        fig.tight_layout()
    return fig
