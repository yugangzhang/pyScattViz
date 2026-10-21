"""Compare samples of the open org: I(q) of many samples at one angle,
overlaid and as a map — and the peak in a q window of each."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pyscattviz.app.auth import require_password
from pyscattviz.app.state import action_key, keep_widget_state

keep_widget_state(st.session_state)
require_password()

from pyscattviz.app.components.org import controls, figures, state  # noqa: E402
from pyscattviz.org import analysis, cms  # noqa: E402

state.on_page()
state.require_source()

NO_ANGLE = -999.0

st.title("📈 Compare samples")
frames = state.frames()
frames = frames[frames["cir"].map(lambda p: isinstance(p, str))]
if frames.empty:
    st.info("No I(q) yet.")
    st.stop()

a, b, c = st.columns([1, 1, 2])
folder = controls.pick_folder(frames, "svorg_cmp", container=a)
in_folder = frames[frames["folder"] == folder]
det = controls.pick_detector(in_folder, "svorg_cmp", container=b)
in_folder = in_folder[in_folder["det_folder"] == det]
angle = pd.to_numeric(in_folder["th"], errors="coerce").fillna(NO_ANGLE)
counts = in_folder.groupby(angle)["sample"].nunique()
values = list(counts.index)
labels = [("no angle" if v == NO_ANGLE else f"{v:g}") + f" ({counts[v]})" for v in values]
if len(values) > 1:
    th = values[
        labels.index(
            c.select_slider(
                "Incident angle (°) — and how many samples were measured there",
                labels,
                value=labels[values.index(counts.idxmax())],
                key="svorg_cmp_th",
            )
        )
    ]
else:
    th = values[0]
    c.caption(f"Incident angle: {labels[0]}")
at = in_folder[np.isclose(angle, th)]
th_text = "" if th == NO_ANGLE else f"θ {th:g}°"
names = list(dict.fromkeys(at["sample"]))

# ---------------------------------------------------------------------------
# Which samples, which frames
# ---------------------------------------------------------------------------

org = state.org()
basket = [s for s in (org.basket if org is not None else []) if s in names]
text = (
    st.text_input(
        "Select every sample whose name contains", key="svorg_cmp_filter", placeholder="e.g. film_A"
    )
    .strip()
    .lower()
)
matching = [n for n in names if text and text in n.lower()]
default = matching or basket or names[:12]
chosen = st.multiselect(
    f"Samples ({len(names)}{' at ' + th_text if th_text else ''})",
    names,
    default=default,
    key=f"svorg_cmp_samples_{folder}_{det}_{th:g}_{text}",
)
if basket and not text:
    st.caption(f"Starting from the {len(basket)} samples selected in the org.")
if not chosen:
    st.stop()

kind = at[at["sample"].isin(chosen)]["kind"].iloc[0]
how = st.radio(
    "Frames of each sample",
    ["newest", "mean of all"] if kind == "static" else ["last", "first", "mean of all"],
    horizontal=True,
    key="svorg_cmp_how",
    help="A static sample may have several spots and repeats at one "
    "angle; an in-situ sample is a run of frames.",
)
show = controls.display_options("svorg_cmp", qimage=False, logx=str(det).lower().startswith("saxs"))
lines_shown = controls.curve_controls("svorg_cmp_lines")
with st.expander("Normalise"):
    norm = st.toggle(
        "Divide each curve by its mean I in a q window", value=False, key="svorg_cmp_norm"
    )
    n1, n2 = st.columns(2)
    q_lo = n1.number_input("from q", value=1.0, format="%g", key="svorg_cmp_nlo")
    q_hi = n2.number_input("to q", value=1.2, format="%g", key="svorg_cmp_nhi")

rows, lines = [], []
for name in chosen:
    own = at[at["sample"] == name]
    if kind != "static":
        own = own.iloc[np.argsort(cms.run_time(own)[0], kind="stable")]
    if how == "newest":
        own = own.sort_values("scan").tail(1)
    elif how == "last":
        own = own.tail(1)
    elif how == "first":
        own = own.head(1)
    q, stack = state.stack(tuple(own["cir"]))
    iq = np.nanmean(stack, axis=0) if len(stack) > 1 else stack[0]
    if norm:
        window = (q >= q_lo) & (q <= q_hi) & np.isfinite(iq)
        scale = np.nanmean(iq[window]) if window.any() else np.nan
        iq = iq / scale if scale and np.isfinite(scale) else iq
    lines.append((name, q, iq))
    scans = own["scan"].dropna()
    rows.append(
        dict(
            sample=name,
            frames=len(own),
            scans=", ".join(str(int(s)) for s in scans[:6]) + (" …" if len(scans) > 6 else ""),
        )
    )

# ---------------------------------------------------------------------------
# Overlay and map
# ---------------------------------------------------------------------------

q0, stacked = cms.stack_iq([(q, iq) for _, q, iq in lines])
limits = controls.ranges(
    "svorg_cmp",
    {"Overlay": [("q", "q"), ("I", "I")], "Map (q as the overlay)": [("map_I", "I")]},
    fit={
        "q": figures.span(q0[np.isfinite(stacked).any(axis=0)], positive=show["logx"]),
        "I": figures.span(stacked, positive=show["logy"]),
    },
    fit_label="Fit to these curves",
)
title = " · ".join(t for t in (folder, det, th_text) if t)
overlay, mapped = st.tabs(["Overlay", "Map"])
with overlay:
    st.plotly_chart(
        figures.curves_figure(
            lines,
            logx=show["logx"],
            logy=show["logy"],
            offset=lines_shown["offset"],
            cmap=lines_shown["cmap"],
            x_range=limits["q"],
            y_range=limits["I"],
            width=lines_shown["width"],
            markers=lines_shown["markers"],
            legend=lines_shown["legend"],
            title=title,
            ylabel="I(q) / ⟨I⟩" if norm else "I(q)",
            height=show["height"] + 100,
        ),
        width="stretch",
        key="svorg_cmp_overlay_chart",
    )
with mapped:
    keep = controls.q_window(q0, limits["q"])
    st.plotly_chart(
        figures.image_figure(
            stacked[:, keep],
            q0[keep],
            np.arange(len(lines)),
            "q (Å⁻¹)",
            "sample",
            title="I(q), a row per sample",
            cmap=show["cmap"],
            log=show["log"],
            vmin=limits["map_I"][0],
            vmax=limits["map_I"][1],
            xlog=show["logx"],
            height=max(show["height"] - 100, 22 * len(lines) + 120),
        ).update_yaxes(
            tickmode="array", tickvals=list(range(len(lines))), ticktext=[n for n, _, _ in lines]
        ),
        width="stretch",
        key="svorg_cmp_map_chart",
    )

st.dataframe(pd.DataFrame(rows), hide_index=True)
table = pd.DataFrame(stacked.T, columns=[n for n, _, _ in lines])
table.insert(0, "q", q0)
suffix = "" if th == NO_ANGLE else f"_th{th:g}"
st.download_button(
    "These curves (CSV)",
    table.to_csv(index=False),
    file_name=f"{folder}_{det}{suffix}_iq.csv",
    key=action_key(st.session_state, "svorg_cmp_csv"),
)

# ---------------------------------------------------------------------------
# A peak in each
# ---------------------------------------------------------------------------

st.subheader("A peak in each curve")
st.caption(
    "Above a straight line between the window's ends: the peak's area, height, "
    "position and width — quick numbers to rank samples by, not a fit."
)
finite = q0[np.isfinite(q0)]
if not finite.size:
    st.stop()
a, b, c = st.columns(3)
p_lo = a.number_input(
    "from q", value=float(np.round(np.quantile(finite, 0.4), 3)), format="%g", key="svorg_cmp_plo"
)
p_hi = b.number_input(
    "to q", value=float(np.round(np.quantile(finite, 0.6), 3)), format="%g", key="svorg_cmp_phi"
)
shown = c.selectbox(
    "Bar chart of", ["area", "height", "q_max", "q_centroid", "fwhm"], key="svorg_cmp_pshow"
)
found = analysis.peaks(q0, stacked, p_lo, p_hi)
found.insert(0, "sample", [n for n, _, _ in lines])
st.plotly_chart(
    go.Figure(go.Bar(x=found["sample"], y=found[shown], marker_color="#1f2a44")).update_layout(
        height=320, template="plotly_white", yaxis_title=shown, margin=dict(l=55, r=10, t=20, b=80)
    ),
    width="stretch",
    key="svorg_cmp_peak_chart",
)
st.dataframe(found, hide_index=True, width="stretch")
st.download_button(
    "The peak table (CSV)",
    found.to_csv(index=False),
    file_name=f"{folder}_{det}{suffix}_peak_{p_lo:g}-{p_hi:g}.csv",
    key=action_key(st.session_state, "svorg_cmp_peak_csv"),
)
