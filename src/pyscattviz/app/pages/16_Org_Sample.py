"""One sample of the open org: every product of one frame, and every angle
of a spot — or the frame's place in its in-situ run."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from pyscattviz.app.auth import require_password
from pyscattviz.app.state import action_key, keep_widget_state

keep_widget_state(st.session_state)
require_password()

from pyscattviz.app.components import scattering as sv  # noqa: E402
from pyscattviz.app.components.org import controls, figures, state  # noqa: E402
from pyscattviz.dataio import DataReadError  # noqa: E402
from pyscattviz.org import cms  # noqa: E402

state.on_page()
state.require_source()

st.title("🖼️ One sample")
frames = state.frames()
if frames.empty:
    st.info("Nothing is reduced yet.")
    st.stop()

a, b, c = st.columns([1, 2, 1])
folder = controls.pick_folder(frames, "svorg_one", container=a)
sample = controls.pick_sample(frames, folder, "svorg_one", container=b)
if sample is None:
    st.stop()
part = cms.frames_of(frames, folder, sample)
det = controls.pick_detector(part, "svorg_one", container=c)
part = part[part["det_folder"] == det]
kind = part["kind"].iloc[0]

# ---------------------------------------------------------------------------
# Which frame
# ---------------------------------------------------------------------------

if kind == "static":
    spots = part.drop_duplicates(["pos", "x"])[["pos", "x"]]
    spot_labels = [
        cms.frame_label({"pos": p, "x": x}) or f"spot {i + 1}"
        for i, (p, x) in enumerate(spots.itertuples(index=False))
    ]
    a, b, c = st.columns([1, 2, 1])
    spot = (
        a.selectbox(
            "Spot", range(len(spots)), format_func=lambda i: spot_labels[i], key="svorg_one_spot"
        )
        if len(spots) > 1
        else 0
    )
    pos, x = spots.iloc[min(spot, len(spots) - 1)]
    at_spot = part[
        (part["pos"].fillna(-1) == (pos if pd.notna(pos) else -1))
        & np.isclose(part["x"].fillna(0), 0 if pd.isna(x) else x)
    ]
    th = controls.pick_angle(at_spot, "svorg_one", container=b)
    at_angle = at_spot if th is None else at_spot[np.isclose(at_spot["th"], th)]
    repeats = at_angle["scan"].tolist()
    pick = (
        c.selectbox(
            "Repeat",
            range(len(repeats)),
            format_func=lambda i: (
                f"scan {int(repeats[i])}" if pd.notna(repeats[i]) else f"#{i + 1}"
            ),
            key="svorg_one_repeat",
        )
        if len(repeats) > 1
        else 0
    )
    row = at_angle.iloc[min(pick, len(at_angle) - 1)]
else:
    a, b = st.columns([1, 3])
    th = controls.pick_angle(part, "svorg_one", container=a)
    run = part if th is None else part[np.isclose(part["th"], th)]
    t, t_label = cms.run_time(run)
    order = np.argsort(t, kind="stable")
    run, t = run.iloc[order], t[order]
    i = controls.pick_frame(
        len(run),
        "svorg_one_frame",
        f"{folder}|{sample}|{det}|{th}",
        label=f"Frame in the run ({len(run)} frames)",
        container=b,
    )
    row = run.iloc[i]
    b.caption(f"{t_label} {t[i]:g} · {cms.frame_label(row.to_dict())}")

st.caption(f"`{row['stem']}`")

# ---------------------------------------------------------------------------
# How it is shown
# ---------------------------------------------------------------------------

qimage = None
if isinstance(row["qimg"], str):
    try:
        qimage = state.load_qimage_data(row["qimg"])
    except DataReadError as exc:  # caught half-written by the reduction
        st.warning(str(exc))
has_qr = sv.qimage_has_qr(qimage)
show = controls.display_options("svorg_one", qr=has_qr, logx=str(det).lower().startswith("saxs"))
mode = show["qmode"] if has_qr else "qx"
measured = sv.frame_axis_ranges(row, mode)
covers = [
    f"{name} {pair[0]:+.3g} … {pair[1]:+.3g}"
    for name, pair in (
        (mode, measured.get(mode)),
        ("qz", measured.get("qz")),
        ("q–φ q", measured.get("qphi_q")),
        ("φ", measured.get("phi")),
        ("I(q) q", measured.get("cir_q")),
    )
    if pair
]
below = "Every angle" if kind == "static" else "Its run"
limits = controls.ranges(
    "svorg_one",
    {
        "q-image": [("qimg_I", "I"), ("qimg_x", mode), ("qimg_z", "qz")],
        "q–φ": [("qphi_I", "I"), ("qphi_q", "q"), ("qphi_phi", "φ")],
        "I(q)": [("iq_q", "q"), ("iq_I", "I")],
        f"{below} (below; q as I(q))": [("below_I", "I")],
    },
    fit={
        "qimg_x": measured.get(mode),
        "qimg_z": measured.get("qz"),
        "qphi_q": measured.get("qphi_q"),
        "qphi_phi": measured.get("phi"),
        "iq_q": measured.get("cir_q"),
        "iq_I": measured.get("cir_I"),
    },
    note="This frame covers " + " · ".join(covers) if covers else "",
)
with st.expander("I(q) curve style"):
    style = controls.curve_style("svorg_one_iq_style", width=1.6)

# ---------------------------------------------------------------------------
# The frame
# ---------------------------------------------------------------------------

left, right = st.columns(2)
with left:
    if qimage is not None:
        z, qx, qz, mask, xlabel = sv.resolve_qimage(qimage, mode)
        st.plotly_chart(
            figures.image_figure(
                z,
                qx,
                qz,
                xlabel,
                "qz (Å⁻¹)",
                mask=mask,
                title="q-image",
                cmap=show["cmap"],
                log=show["log"],
                vmin=limits["qimg_I"][0],
                vmax=limits["qimg_I"][1],
                x_range=limits["qimg_x"],
                y_range=limits["qimg_z"],
                aspect=show["aspect"],
                height=show["height"],
            ),
            width="stretch",
            key="svorg_one_qimg_chart",
        )
    else:
        st.caption("no q-image for this frame")
with right:
    if isinstance(row["qphi"], str):
        q, phi, qphi = state.load_qphi(row["qphi"])
        st.plotly_chart(
            figures.image_figure(
                qphi,
                q,
                phi,
                "q (Å⁻¹)",
                "φ (°)",
                title="q–φ",
                cmap=show["cmap"],
                log=show["log"],
                vmin=limits["qphi_I"][0],
                vmax=limits["qphi_I"][1],
                x_range=limits["qphi_q"],
                y_range=limits["qphi_phi"],
                xlog=show["logx"],
                height=show["height"],
            ),
            width="stretch",
            key="svorg_one_qphi_chart",
        )
    else:
        st.caption("no q–φ map for this frame")

left, right = st.columns(2)
with left:
    if isinstance(row["cir"], str):
        q, iq = state.load_iq(row["cir"])
        st.plotly_chart(
            figures.curves_figure(
                [("I(q)", q, iq)],
                logx=show["logx"],
                logy=show["logy"],
                x_range=limits["iq_q"],
                y_range=limits["iq_I"],
                title="circular average",
                legend=False,
                line_colors=["#1f2a44"],
                style=style,
                height=show["height"],
            ),
            width="stretch",
            key="svorg_one_iq_chart",
        )
        st.download_button(
            "I(q) (CSV)",
            Path(row["cir"]).read_bytes(),
            file_name=Path(row["cir"]).name,
            key=action_key(st.session_state, "svorg_one_iq_csv"),
        )
    else:
        st.caption("no I(q) for this frame")
with right:
    if isinstance(row["qc"], str) and Path(row["qc"]).is_file():
        st.image(row["qc"], caption="the reduction's QC panel", width="stretch")
    else:
        st.caption("no QC panel for this frame (in-situ runs keep one in every few frames)")

# ---------------------------------------------------------------------------
# Around it
# ---------------------------------------------------------------------------

if kind == "static":
    st.subheader("Every angle at this spot")
    latest = (
        at_spot.dropna(subset=["cir", "th"])
        .sort_values("scan")
        .groupby("th")
        .tail(1)
        .sort_values("th")
    )
    if len(latest) > 1:
        lines_shown = controls.curve_controls("svorg_one_angles")
        q, stack = state.stack(tuple(latest["cir"]))
        lines = [(f"θ {r.th:g}°", q, stack[k]) for k, r in enumerate(latest.itertuples())]
        st.plotly_chart(
            figures.curves_figure(
                lines,
                logx=show["logx"],
                logy=show["logy"],
                offset=lines_shown["offset"],
                cmap=lines_shown["cmap"],
                x_range=limits["iq_q"],
                y_range=limits["below_I"],
                width=lines_shown["width"],
                markers=lines_shown["markers"],
                legend=lines_shown["legend"],
                height=show["height"],
                title=f"{sample} · {cms.frame_label({'pos': pos, 'x': x})}",
            ),
            width="stretch",
            key="svorg_one_angles_chart",
        )
        st.caption(
            "The newest frame at each angle. Below the critical angle the "
            "beam sees the surface only; above it, the whole film."
        )
    else:
        st.caption("One angle at this spot.")
else:
    st.subheader("This frame in its run")
    chosen = [("first", run.iloc[0]), ("this", row), ("last", run.iloc[-1])]
    chosen = [(n, r) for n, r in chosen if isinstance(r["cir"], str)]
    if chosen:
        lines_shown = controls.curve_controls("svorg_one_run", colormap=False)
        q, stack = state.stack(tuple(r["cir"] for _, r in chosen))
        lines = [
            (f"{n} · {cms.frame_label(r.to_dict())}", q, stack[k])
            for k, (n, r) in enumerate(chosen)
        ]
        st.plotly_chart(
            figures.curves_figure(
                lines,
                logx=show["logx"],
                logy=show["logy"],
                offset=lines_shown["offset"],
                x_range=limits["iq_q"],
                y_range=limits["below_I"],
                line_colors=["#9aa5b1", "#d62728", "#1f2a44"][: len(lines)],
                width=lines_shown["width"],
                markers=lines_shown["markers"],
                legend=lines_shown["legend"],
                height=show["height"],
            ),
            width="stretch",
            key="svorg_one_run_chart",
        )
    state.page_link("pages/18_Org_In_situ.py", "The whole run on In-situ", "⏱️")

org = state.org()
if org is not None and sample in org.project.samples:
    kept = org.project.samples[sample]
    if kept.notes or kept.tags:
        st.subheader("Kept in the org")
        if kept.tags:
            st.caption("tags: " + ", ".join(sorted(kept.tags)))
        if kept.notes:
            st.markdown(kept.notes if isinstance(kept.notes, str) else str(kept.notes))
