"""In-situ runs of the open org: a run as a waterfall against time, RH or
T; the cell's readings; any frame of it; a peak followed along it."""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from pyscattviz.app.auth import require_password
from pyscattviz.app.state import action_key, keep_widget_state

keep_widget_state(st.session_state)
require_password()

from pyscattviz.app.components.org import controls, figures, state  # noqa: E402
from pyscattviz.org import analysis, cms  # noqa: E402

state.on_page()
state.require_source()

st.title("⏱️ In-situ")
frames = state.frames()
runs = frames[(frames["kind"] == "insitu") & frames["cir"].map(lambda p: isinstance(p, str))]
if runs.empty:
    st.info(
        "No in-situ run has an I(q) yet. A run's frames carry an elapsed "
        "time in their names (`<series>_<idx>_<t>s_x…` or `<series>_<t>s_x…`)."
    )
    st.stop()

a, b, c = st.columns([1, 2, 1])
folder = controls.pick_folder(runs, "svorg_run", container=a)
series = controls.pick_sample(runs, folder, "svorg_run", label="Run", container=b)
if series is None:
    st.stop()
part = cms.frames_of(runs, folder, series)
det = controls.pick_detector(part, "svorg_run", container=c)
part = part[part["det_folder"] == det]

a, b = st.columns([2, 1])
th = controls.pick_angle(
    part,
    "svorg_run",
    container=a,
    label="Incident angle (°) — a run alternating angles is a run per angle",
)
th_text = "" if th is None else f"θ {th:g}°"
th_file = "" if th is None else f"_th{th:g}"
axes = [
    k
    for k in cms.RUN_AXES
    if k == "time" or np.isfinite(pd.to_numeric(part[k], errors="coerce")).any()
]
axis = b.selectbox("Against", axes, format_func=lambda k: cms.RUN_AXES[k], key="svorg_run_axis")
images = controls.image_options("svorg_run_img")
curves = controls.curve_options("svorg_run_iq", offset=True)
every = controls.live("svorg_run")


@st.fragment(run_every=f"{every}s" if every else None)
def body() -> None:
    if every:
        state.rescan()
        state.sync_org()
    now = state.frames()
    run = cms.frames_of(now, folder, series, det_folder=det, th=th)
    run = run[run["cir"].map(lambda p: isinstance(p, str))]
    if run.empty:
        st.info("No reduced frames in this run yet.")
        return
    t, t_label = cms.run_time(run)
    order = np.argsort(t, kind="stable")
    run, t = run.iloc[order], t[order]
    values, v_label = (t, t_label) if axis == "time" else cms.run_axis(run, axis)

    with st.spinner(f"Reading {len(run)} I(q) …"):
        q, stack = state.stack(tuple(run["cir"]))
    st.caption(
        f"{len(run)} reduced frames · {t_label} {t[0]:g}–{t[-1]:g} · "
        f"exposure {cms.span(run['exposure_s'])} s"
    )

    i = controls.pick_frame(len(run), "svorg_run_frame", f"{folder}|{series}|{det}|{th}")
    row = run.iloc[i]
    st.caption(f"{t_label} {t[i]:g} · {cms.frame_label(row.to_dict())} · `{row['stem']}`")

    left, right = st.columns([3, 2])
    with left:
        keep = controls.q_window(q, curves["q_range"])
        st.plotly_chart(
            figures.waterfall_figure(
                q[keep],
                values,
                stack[:, keep],
                v_label,
                title=" · ".join(x for x in (series, th_text) if x),
                cmap=images["cmap"],
                log=images["log"],
                logq=curves["logx"],
                vmin=images["vmin"],
                vmax=images["vmax"],
                marker=values[i],
            ),
            width="stretch",
            key="svorg_run_waterfall_chart",
        )
    with right:
        lines = [
            (f"first ({t[0]:g})", q, stack[0]),
            (f"this ({t[i]:g})", q, stack[i]),
            (f"last ({t[-1]:g})", q, stack[-1]),
        ]
        st.plotly_chart(
            figures.curves_figure(
                lines,
                logx=curves["logx"],
                logy=curves["logy"],
                x_range=curves["q_range"],
                line_colors=["#9aa5b1", "#d62728", "#1f2a44"],
                title="I(q)",
                height=460,
            ),
            width="stretch",
            key="svorg_run_frame_iq_chart",
        )

    readings = {
        "RH (%)": pd.to_numeric(run["RH"], errors="coerce").to_numpy(float),
        "T (°C)": pd.to_numeric(run["T_C"], errors="coerce").to_numpy(float),
    }
    if any(np.isfinite(v).any() for v in readings.values()):
        st.plotly_chart(
            figures.conditions_figure(t, readings, t_label, marker=t[i]),
            width="stretch",
            key="svorg_run_conditions_chart",
        )

    if isinstance(row["qimg"], str) and st.toggle(
        "Show the q-image of this frame", value=False, key="svorg_run_show_qimg"
    ):
        z, qx, qz, mask, xlabel = state.load_qimage(row["qimg"])
        st.plotly_chart(
            figures.image_figure(
                z,
                qx,
                qz,
                xlabel,
                "qz (Å⁻¹)",
                mask=mask,
                title="q-image",
                cmap=images["cmap"],
                log=images["log"],
                vmin=images["vmin"],
                vmax=images["vmax"],
                aspect=images["aspect"],
                height=520,
            ),
            width="stretch",
            key="svorg_run_qimg_chart",
        )

    table = pd.DataFrame(stack.T, columns=[f"{v:g}" for v in values])
    table.insert(0, "q", q)
    st.download_button(
        f"The waterfall (CSV: q, then a column per {v_label})",
        table.to_csv(index=False),
        file_name=f"{series}{th_file}_waterfall.csv",
        key=action_key(st.session_state, "svorg_run_csv"),
    )

    if len(run) < 2:
        return
    st.subheader("Frames along the run")
    a, _ = st.columns([1, 3])
    count = a.number_input("How many", 2, len(run), min(12, len(run)), key="svorg_run_count")
    pick = cms.evenly_spaced(len(run), int(count))
    finite = values[np.isfinite(values)]
    lo, hi = (float(finite.min()), float(finite.max())) if finite.size else (0.0, 1.0)
    cmap = curves["cmap"] or "Viridis"
    st.plotly_chart(
        figures.curves_figure(
            [(f"{values[k]:g}", q, stack[k]) for k in pick],
            logx=curves["logx"],
            logy=curves["logy"],
            offset=curves["offset"],
            cmap=cmap,
            line_colors=figures.value_colors(values[pick], cmap, lo, hi),
            x_range=curves["q_range"],
            legend=False,
            colorbar=(v_label, lo, hi),
            title=f"coloured by {v_label}",
            height=480,
        ),
        width="stretch",
        key="svorg_run_along_chart",
    )

    st.subheader("A peak along the run")
    st.caption(
        "In a q window, above a straight line between its ends: the peak's area, "
        "position and width in every frame — quick numbers to follow a "
        "transition by, not a fit."
    )
    qs = q[np.isfinite(q)]
    if not qs.size:
        return
    a, b = st.columns(2)
    p_lo = a.number_input(
        "from q", value=float(np.round(np.quantile(qs, 0.4), 3)), format="%g", key="svorg_run_plo"
    )
    p_hi = b.number_input(
        "to q", value=float(np.round(np.quantile(qs, 0.6), 3)), format="%g", key="svorg_run_phi"
    )
    found = analysis.peaks(q, stack, p_lo, p_hi)
    st.plotly_chart(
        figures.trend_figure(
            values,
            {"area": found["area"], "q of max (Å⁻¹)": found["q_max"], "FWHM (Å⁻¹)": found["fwhm"]},
            v_label,
            marker=values[i],
            height=520,
        ),
        width="stretch",
        key="svorg_run_peak_chart",
    )
    found.insert(0, v_label, values)
    found.insert(1, "stem", run["stem"].to_numpy())
    st.download_button(
        "The peak along the run (CSV)",
        found.to_csv(index=False),
        file_name=f"{series}{th_file}_peak_{p_lo:g}-{p_hi:g}.csv",
        key=action_key(st.session_state, "svorg_run_peak_csv"),
    )


body()
st.caption(
    "Several runs side by side: **Compare samples**, with the run's last (or first, or mean) frame."
)
state.page_link("pages/17_Org_Compare.py", "Compare samples", "📈")
