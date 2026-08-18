"""Publication-figure helpers for selected scattering curves."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from pyscattviz.plotting import plot1d_multi, theme_context


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
        scale = float(abs(np.trapz(intensity, q)))
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
) -> Figure:
    """Build a static, export-ready overlay from selected scattering curves."""

    prepared = [
        prepare_curve(
            curve,
            q_min=q_min,
            q_max=q_max,
            normalization=normalization,
        )
        for curve in curves
    ]
    if not prepared:
        raise ValueError("at least one curve is required")

    datasets = []
    for index, curve in enumerate(prepared):
        intensity = curve.intensity + index * float(offset)
        if logx:
            keep = curve.q > 0
        else:
            keep = np.ones(curve.q.shape, dtype=bool)
        if logy:
            keep &= intensity > 0
        if not keep.any():
            raise ValueError(f"{curve.name!r} has no positive points for the selected log axes")
        datasets.append(
            {
                "x": curve.q[keep],
                "y": intensity[keep],
                "label": compact_label(curve.name, max_label_length),
                "marker": None,
                "lw": 1.6,
            }
        )

    with theme_context(theme):
        fig, ax = plt.subplots(figsize=figsize)
        plot1d_multi(
            datasets,
            ax=ax,
            logx=logx,
            logy=logy,
            xlabel=xlabel,
            ylabel=ylabel,
            title=title,
            grid=False,
        )
        if not legend and ax.legend_ is not None:
            ax.legend_.remove()
        fig.tight_layout()
    return fig
