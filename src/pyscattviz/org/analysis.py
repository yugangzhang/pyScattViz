"""A first look at a peak: what one q window of each curve holds.

::

    q, stack = …                         # I(q) of a run, a row per frame
    peaks(q, stack, 1.30, 1.50)          # a row per frame: area, q, width …

Above a straight line drawn between the window's ends (the background,
taken from the curve itself), each curve gives the peak's area, its
height, the q of its maximum, its centroid and its full width at half
maximum. Quick numbers for following a run or ranking samples — not a fit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PEAK_COLUMNS = ("area", "height", "q_max", "q_centroid", "fwhm", "points")


def _crossing(x, s, start: int, step: int, half: float) -> float:
    """Where *s* first falls below *half*, walking from *start* by *step*,
    interpolated between the two points either side; NaN if it never does."""
    i = start
    while 0 <= i + step < len(s):
        if s[i + step] < half:
            a, b = s[i], s[i + step]
            return float(x[i] + (x[i + step] - x[i]) * (a - half) / (a - b))
        i += step
    return float("nan")


def peak(q, iq, lo: float, hi: float) -> dict:
    """The peak in ``lo ≤ q ≤ hi`` of one curve, above the straight line
    between the window's ends (:data:`PEAK_COLUMNS`; NaN where there are
    fewer than three points)."""
    q, iq = np.asarray(q, float), np.asarray(iq, float)
    keep = np.isfinite(q) & np.isfinite(iq) & (q >= min(lo, hi)) & (q <= max(lo, hi))
    x, y = q[keep], iq[keep]
    order = np.argsort(x, kind="stable")
    x, y = x[order], y[order]
    out = dict.fromkeys(PEAK_COLUMNS, float("nan"))
    out["points"] = int(x.size)
    if x.size < 3 or x[-1] == x[0]:
        return out
    background = y[0] + (y[-1] - y[0]) * (x - x[0]) / (x[-1] - x[0])
    s = y - background
    k = int(np.argmax(s))
    above = np.clip(s, 0, None)
    out["area"] = float(np.sum(0.5 * (s[1:] + s[:-1]) * np.diff(x)))
    out["height"] = float(s[k])
    out["q_max"] = float(x[k])
    out["q_centroid"] = (
        float(np.sum(x * above) / np.sum(above)) if above.sum() > 0 else float("nan")
    )
    if s[k] > 0:
        half = s[k] / 2
        out["fwhm"] = _crossing(x, s, k, 1, half) - _crossing(x, s, k, -1, half)
    return out


def peaks(q, stack, lo: float, hi: float) -> pd.DataFrame:
    """:func:`peak` of each row of *stack* (curves on the axis *q*)."""
    stack = np.atleast_2d(np.asarray(stack, float))
    return pd.DataFrame([peak(q, row, lo, hi) for row in stack], columns=list(PEAK_COLUMNS))


__all__ = ["PEAK_COLUMNS", "peak", "peaks"]
