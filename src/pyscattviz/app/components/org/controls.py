"""Page pieces the Org pages share: pickers, display options, live refresh.

Widget keys start ``svorg_``; the caller gives the rest.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd
import streamlit as st

from pyscattviz.app.components.org import figures


def folders(frames: pd.DataFrame, kind: Optional[str] = None) -> List[str]:
    """Experiment folders with frames (of one *kind*: ``static``/``insitu``)."""
    part = frames if kind is None else frames[frames["kind"] == kind]
    return sorted(part["folder"].unique())


def pick_folder(
    frames: pd.DataFrame, key: str, *, kind: Optional[str] = None, container=st
) -> Optional[str]:
    names = folders(frames, kind)
    if not names:
        return None
    part = frames if kind is None else frames[frames["kind"] == kind]
    last = part.sort_values("scan")["folder"]
    newest = names.index(last.iloc[-1]) if len(last) else 0
    return container.selectbox(
        "Folder",
        names,
        index=newest,
        key=f"{key}_folder",
        help="Opens on the folder measured last.",
    )


def pick_sample(
    frames: pd.DataFrame,
    folder: str,
    key: str,
    *,
    kind: Optional[str] = None,
    label: str = "Sample",
    container=st,
) -> Optional[str]:
    """A sample of *folder*, narrowed by a name filter; it opens on the one
    measured last — during a beamtime, the one on the beam."""
    part = frames[frames["folder"] == folder]
    if kind is not None:
        part = part[part["kind"] == kind]
    names = list(dict.fromkeys(part["sample"]))
    text = (
        container.text_input(
            f"{label} name contains", key=f"{key}_filter", placeholder="e.g. film_A"
        )
        .strip()
        .lower()
    )
    if text:
        names = [n for n in names if text in n.lower()] or names
    if not names:
        return None
    last = part[part["sample"].isin(names)].sort_values("scan")["sample"]
    newest = names.index(last.iloc[-1]) if len(last) else 0
    return container.selectbox(
        label, names, index=newest, key=f"{key}_sample", help="Opens on the sample measured last."
    )


def pick_detector(part: pd.DataFrame, key: str, container=st) -> Optional[str]:
    names = sorted(part["det_folder"].unique())
    if not names:
        return None
    if len(names) == 1:
        return names[0]
    return container.radio("Detector", names, horizontal=True, key=f"{key}_det")


def angles(part: pd.DataFrame) -> List[float]:
    return sorted(pd.to_numeric(part["th"], errors="coerce").dropna().unique())


def pick_angle(
    part: pd.DataFrame, key: str, *, label: str = "Incident angle (°)", container=st
) -> Optional[float]:
    values = angles(part)
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    labels = [f"{a:g}" for a in values]
    chosen = container.select_slider(label, labels, value=labels[0], key=f"{key}_th")
    return values[labels.index(chosen)]


def pick_frame(n: int, key: str, run: str, *, label: str = "Frame", container=st) -> int:
    """A frame of a run of *n* frames: the last when the run is first shown
    (or another run is), and where it was left while the run grows."""
    if n < 2:
        return 0
    shown_run = f"{key}_run"
    current = st.session_state.get(key)
    if (
        st.session_state.get(shown_run) != run
        or not isinstance(current, int)
        or not 0 <= current < n
    ):
        st.session_state[key] = n - 1
    st.session_state[shown_run] = run
    return int(container.slider(label, 0, n - 1, key=key))


def image_options(key: str, *, expanded: bool = False) -> dict:
    """Colour map, log intensity, intensity limits — for the 2-D panels."""
    with st.expander("Image options", expanded=expanded):
        a, b, c, d = st.columns(4)
        cmap = a.selectbox("Colour map", figures.CMAPS, key=f"{key}_cmap")
        log = b.toggle("log intensity", value=True, key=f"{key}_log")
        auto = c.toggle("auto limits (1–99.5 %)", value=True, key=f"{key}_auto")
        equal = d.toggle("equal q aspect", value=True, key=f"{key}_equal")
        vmin = vmax = None
        if not auto:
            e, f = st.columns(2)
            vmin = e.number_input("I min", value=1.0, min_value=0.0, key=f"{key}_vmin", format="%g")
            vmax = f.number_input("I max", value=1e4, min_value=0.0, key=f"{key}_vmax", format="%g")
    return dict(cmap=cmap, log=log, vmin=vmin, vmax=vmax, aspect="equal" if equal else None)


def curve_options(
    key: str, *, offset: bool = True, colormap: bool = True, expanded: bool = False
) -> dict:
    """Log axes, q range, stacking offset, colour map — for I(q) plots."""
    with st.expander("Curve options", expanded=expanded):
        a, b, c, d = st.columns(4)
        logx = a.toggle("log q", value=False, key=f"{key}_logx")
        logy = b.toggle("log I", value=True, key=f"{key}_logy")
        q_lo = c.number_input(
            "q min (0: auto)", value=0.0, min_value=0.0, step=0.05, key=f"{key}_qlo", format="%g"
        )
        q_hi = d.number_input(
            "q max (0: auto)", value=0.0, min_value=0.0, step=0.1, key=f"{key}_qhi", format="%g"
        )
        e, f = st.columns(2)
        shift = 1.0
        if offset:
            shift = e.number_input(
                "Offset (× per curve on log I, + on linear; 1/0 = none)",
                value=1.0 if logy else 0.0,
                min_value=0.0,
                key=f"{key}_offset",
                format="%g",
            )
        cmap = (
            f.selectbox("Colour map", figures.LINE_CMAPS, key=f"{key}_lcmap") if colormap else None
        )
    q_range = (q_lo or None, q_hi or None)
    return dict(
        logx=logx, logy=logy, offset=shift, cmap=cmap, q_range=q_range if any(q_range) else None
    )


def live(key: str, *, default: bool = False) -> Optional[int]:
    """A *Live* toggle: the seconds between refreshes, or None when off."""
    a, b = st.columns([1, 2])
    on = a.toggle(
        "Live",
        value=default,
        key=f"{key}_live",
        help="Re-read the folders and redraw on a timer, for a run that is still going.",
    )
    if not on:
        return None
    return int(b.select_slider("every (s)", [10, 15, 30, 60, 120], value=30, key=f"{key}_every"))


def q_window(q, q_range):
    """The part of *q* inside *q_range* (``(lo, hi)``, either None)."""
    q = np.asarray(q, float)
    if not q_range:
        return np.ones(q.shape, bool)
    lo, hi = q_range
    keep = np.isfinite(q)
    if lo:
        keep &= q >= lo
    if hi:
        keep &= q <= hi
    return keep


__all__ = [
    "folders",
    "pick_folder",
    "pick_sample",
    "pick_detector",
    "angles",
    "pick_angle",
    "image_options",
    "curve_options",
    "live",
    "q_window",
]
