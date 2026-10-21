"""Page pieces the Org pages share: pickers, display options, live refresh.

The display options and the *Ranges & colour scaling* panel are the
explorers' (GISAXS, GIWAXS …): log axes, colour map, aspect, the q-image's
in-plane axis, and a min and a max box for every axis and intensity of
every panel — blank is auto (:mod:`.figures`).

Widget keys start ``svorg_``; the caller gives the rest.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from pyscattviz.app.components import scattering as sv
from pyscattviz.app.components.org import figures
from pyscattviz.app.state import action_key

ASPECTS = ("Equal (1:1)", "Auto", "Custom")
QIMAGE_AXES = {"qx": "qx–qz", "qr": "qr–qz"}


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


def display_options(key: str, *, qimage: bool = True, qr: bool = False, logx: bool = False) -> dict:
    """The row above the panels: log I of the maps, log q and log I of the
    curves, the maps' colour map; with *qimage*, the q-image's aspect and —
    where its npz has a qr remesh (*qr*) — its in-plane axis; the panels'
    height. *logx* is log q's first value."""
    a, b, c, d = st.columns(4)
    found = dict(
        log=a.checkbox("log I (2D panels)", value=True, key=f"{key}_log"),
        logx=b.checkbox("log q (1D)", value=logx, key=f"{key}_logx"),
        logy=c.checkbox("log I (1D)", value=True, key=f"{key}_logy"),
        cmap=d.selectbox("2D colour map", figures.CMAPS, key=f"{key}_cmap"),
        aspect=None,
        qmode="qx",
    )
    a, b, c, d = st.columns(4)
    if qimage:
        mode = a.selectbox(
            "Aspect ratio (q-image)",
            ASPECTS,
            key=f"{key}_aspect",
            help="Equal locks qz to q∥ at 1:1; Custom sets the qz:q∥ ratio.",
        )
        if mode == "Custom":
            found["aspect"] = b.number_input(
                "qz : q∥ ratio", 0.05, 20.0, 1.0, 0.1, format="%.2f", key=f"{key}_ratio"
            )
        elif mode == ASPECTS[0]:
            found["aspect"] = "equal"
        found["qmode"] = c.selectbox(
            "q-image x-axis",
            list(QIMAGE_AXES),
            format_func=QIMAGE_AXES.get,
            key=f"{key}_qmode",
            help="qr–qz needs a qr remesh in the q_image npz"
            + ("" if qr else " — this frame has none, so qx–qz is shown")
            + ".",
        )
    found["height"] = d.select_slider(
        "Panel height (px)", [320, 380, 420, 480, 560, 640, 760], value=420, key=f"{key}_height"
    )
    return found


def limits(container, label: str, key: str) -> Tuple[Optional[float], Optional[float]]:
    """A *label* min and max box side by side → ``(lo, hi)``; blank is None."""
    a, b = container.columns(2)
    lo = a.number_input(f"{label} min", value=None, key=f"{key}_lo", format="%.4g")
    hi = b.number_input(f"{label} max", value=None, key=f"{key}_hi", format="%.4g")
    return lo, hi


def fill_limits(values: Mapping[str, Optional[Tuple[float, float]]]) -> None:
    """Write ``{key: (lo, hi)}`` into the boxes of :func:`limits`; None
    empties them."""
    for key, pair in values.items():
        st.session_state[f"{key}_lo"] = None if pair is None else float(pair[0])
        st.session_state[f"{key}_hi"] = None if pair is None else float(pair[1])


def ranges(
    key: str,
    panels: Mapping[str, Sequence[Tuple[str, str]]],
    *,
    fit: Optional[Mapping[str, Optional[Tuple[float, float]]]] = None,
    fit_label: str = "Fit to this frame",
    note: str = "",
    expanded: bool = False,
) -> Dict[str, Tuple[Optional[float], Optional[float]]]:
    """*Ranges & colour scaling*, as on the explorers: for each panel
    (``{title: [(name, label), …]}``) a min and a max box per axis, three
    panels to a row. **Fit** writes *fit* ``{name: (lo, hi)}`` into the
    boxes, to be edited; **Clear back to auto** empties them. Returns
    ``{name: (lo, hi)}``, None where blank."""
    names = [name for axes in panels.values() for name, _ in axes]
    found = {}
    with st.expander("🎛️ Ranges & colour scaling (blank = auto)", expanded=expanded):
        st.caption(
            "Blank is auto: an axis frames the data it shows, and a colour or "
            "intensity scale spans what lies inside that window — narrow q and I "
            "follows. Colour limits are intensities (before the log)."
        )
        a, b, _ = st.columns([1.2, 1.4, 2.4])
        if fit and a.button(fit_label, key=action_key(st.session_state, f"{key}_fit")):
            fill_limits({f"{key}_{n}": fit[n] for n in names if fit.get(n)})
            st.rerun()
        if b.button("Clear back to auto", key=action_key(st.session_state, f"{key}_clear")):
            fill_limits({f"{key}_{n}": None for n in names})
            st.rerun()
        items = list(panels.items())
        for row in range(0, len(items), 3):
            for column, (title, axes) in zip(st.columns(3), items[row : row + 3]):
                column.markdown(f"**{title}**")
                for name, label in axes:
                    found[name] = limits(column, label, f"{key}_{name}")
        if note:
            st.caption(note)
    return found


def curve_controls(key: str, *, offset: bool = True, colormap: bool = True) -> dict:
    """Stacking offset, colour map, line width, markers and legend of a plot
    of several I(q)."""
    a, b, c, d, e = st.columns([1.3, 1.2, 1, 0.8, 0.8])
    shift = (
        a.number_input(
            "Offset (× per curve on log I, + on linear; 1/0 = none)",
            value=1.0,
            min_value=0.0,
            key=f"{key}_offset",
            format="%g",
        )
        if offset
        else 1.0
    )
    cmap = (
        b.selectbox("Line colour map", figures.LINE_CMAPS, key=f"{key}_lcmap") if colormap else None
    )
    width = c.slider("Line width", 0.5, 5.0, 1.4, 0.1, key=f"{key}_width")
    markers = d.checkbox("Markers", value=False, key=f"{key}_markers")
    legend = e.checkbox("Legend", value=True, key=f"{key}_legend")
    return dict(offset=shift, cmap=cmap, width=width, markers=markers, legend=legend)


def curve_style(key: str, **defaults) -> dict:
    """The explorers' style of one curve: colour, marker, line, width …"""
    return sv.curve_style_controls(key, defaults=defaults or None)


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
    "pick_frame",
    "display_options",
    "limits",
    "fill_limits",
    "ranges",
    "curve_controls",
    "curve_style",
    "live",
    "q_window",
]
