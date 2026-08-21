"""Shared implementation for independent transmission SAXS and WAXS pages.

Transmission-geometry counterpart to the GIWAXS explorer. Point it at a
``saxs/`` or ``waxs/`` folder's ``analysis/`` directory (CMS auto-reduction).
The layout differs from grazing incidence in two ways handled by the shared
engine:

* the 2D raw ``.tiff`` lives in the sibling ``raw/`` folder (not
  ``analysis/stitched/``), and
* there is usually **no** ``q_image/`` remesh for transmission data, so the
  q-image panel shows a placeholder until such files exist.

Per reduced frame it uses:

* ``../raw/<name>.tiff``               → the 2D raw detector image (A).
* ``q_image/qimg_<name>.tiff.npz``     → remeshed q-space image (B, optional).
* ``qphi/qphi_<name>.tiff.npz``        → keys ``q``, ``phi``, ``qphi`` — the
  q–φ caking map (C).
* ``cir_avg/Cir_Avg_<name>.tiff.csv``  → columns ``q_ca, iq_ca`` — I(q) (D).

Line-cuts are taken on the q–φ map (q-cut → I vs φ, or φ-cut → I vs q).

Runs as a page of the pyScattViz local application.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pyscattviz.app.components.batchprocess import render_batch_process
from pyscattviz.app.components.cleaning import render_cleaning_controls
from pyscattviz.app.components.codeview import render_code_export
from pyscattviz.app.components.datasource import (
    apply_term_filters,
    render_folder_picker,
    render_term_filters,
)
from pyscattviz.app.components.saving import render_output_settings, render_save_panel

# Shared scattering engine (aliased to the underscore names used below).
from pyscattviz.app.components.scattering import (
    CMAPS,
    SCATTERING_PRODUCTS,
    frame_axis_ranges,
    frame_curve,
    heatmap_fig,
    index_frames,
    intensity_limits_in_window,
    load_cir,
    load_qimg,
    load_qphi,
    load_raw,
    resolve_qimage,
    scattering_product_selector,
)
from pyscattviz.app.components.scattering import (
    apply_curve_style as _apply_curve_style,
)
from pyscattviz.app.components.scattering import (
    apply_mask as _apply_mask,
)
from pyscattviz.app.components.scattering import (
    axrange as _axrange,
)
from pyscattviz.app.components.scattering import (
    band_profile as _band_profile,
)
from pyscattviz.app.components.scattering import (
    curve_style_controls as _curve_style_controls,
)
from pyscattviz.app.components.scattering import (
    downsample as _downsample,
)
from pyscattviz.app.components.scattering import (
    parse_centers as _parse_centers,
)
from pyscattviz.app.components.scattering import (
    style_1d_axes as _style_1d_axes,
)
from pyscattviz.app.state import action_key, keep_widget_state
from pyscattviz.codegen import frame_panel_code
from pyscattviz.dataio import DataReadError
from pyscattviz.filters import FilterSyntaxError

EXPLORER_MODE = globals().get("EXPLORER_MODE", "tsaxs")
_PROFILES = {
    "tsaxs": {
        "name": "Transmission SAXS",
        "short": "TSAXS",
        "icon": "🔬",
        "folder": "tsaxs",
        "state": "tsaxs",
        "description": (
            "Small-angle transmission review with SAXS detector paths, low-q limits, "
            "log-q I(q), q–φ anisotropy cuts, and selected-frame loading."
        ),
        "logq": True,
        "q_range": (0.001, 0.5),
        "phi_range": (0.0, 180.0),
        "q_cut_center": "0.1",
        "q_cut_width": 0.005,
        "raw_choices": [
            "../../user_data/2M",
            "../raw",
            "../../user_data/900KW",
            "stitched",
        ],
    },
    "twaxs": {
        "name": "Transmission WAXS",
        "short": "TWAXS",
        "icon": "🔭",
        "folder": "twaxs",
        "state": "twaxs",
        "description": (
            "Wide-angle transmission review with WAXS detector paths, high-q limits, "
            "linear-q I(q), q–φ orientation cuts, and selected-frame loading."
        ),
        "logq": False,
        "q_range": (0.0, 3.5),
        "phi_range": (0.0, 180.0),
        "q_cut_center": "1.0",
        "q_cut_width": 0.05,
        "raw_choices": [
            "../../user_data/900KW",
            "../raw",
            "../../user_data/2M",
            "stitched",
        ],
    },
}
PROFILE = _PROFILES[EXPLORER_MODE]
STATE_PREFIX = f"pyscattviz_{PROFILE['state']}"
AUTO_Q_KEY = f"{STATE_PREFIX}_auto_q"
AUTO_I_KEY = f"{STATE_PREFIX}_auto_i"
RAW_SUBDIR_CHOICES = PROFILE["raw_choices"]
RAW_SUBDIR = RAW_SUBDIR_CHOICES[0]


# ===========================================================================
st.set_page_config(
    page_title=f"{PROFILE['short']} Explorer",
    page_icon=PROFILE["icon"],
    layout="wide",
)

# Streamlit forgets a page's widgets as soon as another page is opened.
keep_widget_state(st.session_state)

st.title(f"{PROFILE['icon']} {PROFILE['name']} Explorer")
st.caption(PROFILE["description"])

with st.sidebar:
    st.header(f"📁 {PROFILE['short']} analysis folder")

    # One mounted drive usually holds many proposals, beamlines, and projects,
    # so the picker offers every folder the session knows and keeps whatever is
    # typed even when it is not available yet.
    analysis = render_folder_picker(
        STATE_PREFIX,
        f"Data path ({PROFILE['folder']}/analysis or one product folder)",
        help_text=(
            "A result folder, or one product folder inside it. An original "
            "/nsls2/... path works once its mount is registered."
        ),
    )
    if not analysis:
        st.info("Choose or paste a data folder to start.")
        st.stop()

    analysis_root, products, selected_products = scattering_product_selector(
        f"{PROFILE['state']}_products", analysis
    )
    raw_subdir = st.selectbox(
        "Raw image folder (relative to analysis/)",
        RAW_SUBDIR_CHOICES,
        index=0,
        accept_new_options=True,
        help="CMS: ../raw · SMI: ../../user_data/<detector>. Type any other "
        "relative path if your layout differs.",
        key=f"{STATE_PREFIX}_raw_subdir",
    )

    saved_stems = st.session_state.get("pyscattviz_selected_stems", ())
    saved_root = st.session_state.get("pyscattviz_selected_root")
    saved_available = bool(saved_stems and saved_root == analysis_root)
    use_saved = st.checkbox(
        f"Use saved File Selection ({len(saved_stems):,} frames)",
        value=saved_available,
        disabled=not saved_available,
        key=f"{STATE_PREFIX}_use_saved",
    )
    query = st.text_input(
        "Boolean filename filter",
        value="",
        placeholder="sample AND (10s OR 30s) NOT AgBH",
        disabled=use_saved,
        key=f"{STATE_PREFIX}_query",
    )
    max_frames = st.number_input(
        "Maximum frames",
        1,
        50_000,
        5_000,
        500,
        disabled=use_saved,
        key=f"{STATE_PREFIX}_max_frames",
    )

    if st.button("🔄 Rescan"):
        index_frames.clear()
    if not analysis or not selected_products:
        if analysis and products:
            st.warning("Select at least one product panel to continue.")
        st.stop()

    try:
        df = index_frames(
            analysis_root,
            raw_subdir=raw_subdir or RAW_SUBDIR,
            product_keys=tuple(selected_products),
            query="" if use_saved else query,
            filename_list=tuple(saved_stems) if use_saved else (),
            max_frames=len(saved_stems) if use_saved else int(max_frames),
        )
    except FilterSyntaxError as exc:
        st.error(f"Filter error: {exc}")
        st.stop()
    if df.empty:
        st.warning("No frame files found in the selected scattering products.")
        st.stop()
    if df.attrs.get("truncated"):
        st.warning("The frame cap was reached; narrow the filename filter.")
    st.success(
        f"{len(df)} frames (scanned {df.attrs.get('scanned_entries', 0):,} names) — "
        f"{int(df['has_raw'].sum())} raw · {int(df['has_qc'].sum())} QC · "
        f"{int(df['has_qimg'].sum())} q-img · "
        f"{int(df['has_qphi'].sum())} q–φ · {int(df['has_cir'].sum())} 1D."
    )

    hide_cal = st.checkbox("Hide calibration", value=True, key=f"{STATE_PREFIX}_hide_cal")
    st.caption("Narrow the frame list")
    kw_and, kw_or, kw_not = render_term_filters(STATE_PREFIX)

    st.divider()
    st.subheader("💾 Saving")
    render_output_settings(st)

work = df.copy()
if hide_cal:
    work = work[~work["is_calibration"]]
work = apply_term_filters(work, kw_and, kw_or, kw_not)
work = work.reset_index(drop=True)
if work.empty:
    # Say which filter emptied the list. A calibration-only folder is common —
    # a beamtime's AgBH scans live in their own directory — and "Nothing matches
    # the filter" on its own sends people looking for a fault that is not there.
    hidden_calibration = int(df["is_calibration"].sum()) if hide_cal else 0
    if hidden_calibration and hidden_calibration == len(df):
        st.warning(
            f"All {hidden_calibration} frame(s) here are calibration scans "
            "(AgBH, direct beam, glassy carbon). Clear **Hide calibration** in "
            "the sidebar to look at them."
        )
    elif hidden_calibration:
        st.warning(
            f"Nothing matches the keyword filter. {hidden_calibration} "
            "calibration frame(s) are also hidden."
        )
    else:
        st.warning("Nothing matches the filter.")
    st.stop()

# --- Frame picker -----------------------------------------------------------
active_products = set(selected_products)
c1, c2 = st.columns([4, 1])
labels = work["stem"].tolist()
chosen = (
    c1.selectbox("Frame", options=labels, index=0, key=f"{STATE_PREFIX}_frame")
    if len(labels) > 1
    else labels[0]
)
idx = labels.index(chosen)
sel = work.iloc[int(idx)]
c2.metric("Frame", f"{int(idx) + 1}/{len(labels)}")

ts = sel["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if pd.notna(sel["timestamp"]) else "—"
st.markdown(f"**{sel['stem']}**  ·  well `{sel['well']}`  ·  t = {ts}")

# --- Display controls -------------------------------------------------------
dc1, dc2, dc3, dc4 = st.columns(4)
logI = dc1.checkbox("log I (2D panels)", value=True, key=f"{STATE_PREFIX}_logI")
logq = dc2.checkbox("log q (1D)", value=PROFILE["logq"], key=f"{STATE_PREFIX}_logq")
logiq = dc3.checkbox("log I (1D)", value=True, key=f"{STATE_PREFIX}_logiq")
cmap = dc4.selectbox("2D colormap", CMAPS, index=0, key=f"{STATE_PREFIX}_cmap")  # default Turbo


# One or two pixels on every CMS/SMI detector read absurdly high whatever the
# sample. The azimuthal average is a mean, so a single 500,000-count pixel moves
# a whole q bin and the 1-D curve grows a peak that is not there.
def _preview_frame():
    """The 2D product the hot-pixel thresholds are judged against.

    Every loader is cached, so reading a product here costs nothing the page was
    not about to spend a few lines further down anyway.
    """

    try:
        if sel.get("has_qphi"):
            return load_qphi(sel["qphi"])[2]
        if sel.get("has_qimg"):
            return resolve_qimage(load_qimg(sel["qimg"]), "qx")[0]
    except (DataReadError, KeyError, TypeError, ValueError):
        return None
    return None


# Every threshold is on screen: what counts as "hot" depends on the detector and
# on how oriented the sample is, and that is the user's call, not a constant.
# Hot pixels, the across-frames vote, and the exclusion mask, in one place —
# the same object the batch below uses, so a batch cannot drift from what the
# panels are showing.
cleaning = render_cleaning_controls(STATE_PREFIX, work, preview_image=_preview_frame())
hot = cleaning.hot
user_mask = cleaning.mask
despike = hot.enabled
_drawing = cleaning.drawing

dc5, _ = st.columns(2)
aspect_mode = dc5.selectbox(
    "Aspect ratio (A & B)",
    ["Auto", "Equal (1:1)", "Custom"],
    index=1,
    help="Equal locks y/x to 1:1 in data units; Custom sets the y:x ratio.",
    key=f"{STATE_PREFIX}_aspect_mode",
)
aspect_ratio = 1.0
if aspect_mode == "Custom":
    aspect_ratio = dc5.number_input(
        "y:x ratio",
        value=1.0,
        min_value=0.05,
        max_value=20.0,
        step=0.1,
        format="%.2f",
        key=f"{STATE_PREFIX}_aspect_ratio",
    )

_PANEL_H = 380


def _rng(col, label, key, lo_val=None, hi_val=None, fmt="%.4g"):
    """Two side-by-side optional number inputs → (min, max); None means auto."""
    a, b = col.columns(2)
    lo = a.number_input(f"{label} min", value=lo_val, key=f"{STATE_PREFIX}_{key}_lo", format=fmt)
    hi = b.number_input(f"{label} max", value=hi_val, key=f"{STATE_PREFIX}_{key}_hi", format=fmt)
    return lo, hi


def _heatmap_fig(title, z, x, y, xlab, ylab, **kw):
    """Thin wrapper injecting this page's colormap / log toggle / height."""
    return heatmap_fig(title, z, x, y, xlab, ylab, cmap=cmap, logI=logI, height=_PANEL_H, **kw)


def _aspect_arg():
    if aspect_mode == "Equal (1:1)":
        return "equal"
    if aspect_mode == "Custom":
        return aspect_ratio
    return None


# Axis limits start blank so each panel scales to the frame it is showing. Fixed
# defaults were wrong more often than right: an SMI transmission WAXS q–φ map
# reaches 9 Å⁻¹ and was being cut off at 3.5, and φ runs -179 … +179 rather than
# 0 … 180. The buttons below fill the boxes explicitly.
_RANGE_KEYS = ("c_q", "c_phi", "d_q")


def _fill_ranges(values: dict) -> None:
    """Write measured or preset limits into the range boxes."""

    for key, span in values.items():
        # Assign rather than delete: the boxes declare a geometry default, so a
        # deleted key would simply come back as that default on the next render
        # and "Clear back to auto" would do nothing.
        low = None if span is None else float(span[0])
        high = None if span is None else float(span[1])
        st.session_state[f"{STATE_PREFIX}_{key}_lo"] = low
        st.session_state[f"{STATE_PREFIX}_{key}_hi"] = high


with st.expander("🎛️ Ranges & colour scaling (blank = auto)", expanded=False):
    _auto_columns = st.columns(2)
    auto_q = _auto_columns[0].checkbox(
        "Auto q limits",
        value=bool(st.session_state.get(AUTO_Q_KEY, True)),
        key=AUTO_Q_KEY,
        help=(
            "Frame the q–φ q axis and the I(q) panel on their own data. A fixed "
            "window wastes the panel on decades that hold no signal — a CMS SAXS "
            "file runs to q = 0.31 but the intensity has fallen to nothing by "
            "0.25, and it starts at 0.0056, not 0.001. φ is left alone. Turn "
            "this off to pin your own q range."
        ),
    )
    auto_i = _auto_columns[1].checkbox(
        "Auto intensity limits",
        value=bool(st.session_state.get(AUTO_I_KEY, True)),
        key=AUTO_I_KEY,
        help=(
            "Set the I(q) limits from the points inside the q window that is "
            "actually shown. Choose a q range by hand and the intensity "
            "rescales to match, instead of leaving the part you asked for as a "
            "flat line at the top of a panel scaled to the full four decades."
        ),
    )
    fill_left, fill_middle, fill_right = st.columns([1.2, 1.4, 2.4])
    if fill_left.button(
        "Fit to this frame", key=action_key(st.session_state, f"{STATE_PREFIX}_fit_ranges")
    ):
        measured = frame_axis_ranges(sel)
        _fill_ranges(
            {
                "c_q": measured.get("qphi_q"),
                "c_phi": measured.get("phi"),
                "d_q": measured.get("cir_q"),
            }
        )
        st.rerun()
    if fill_middle.button(
        f"{PROFILE['short']} preset",
        key=action_key(st.session_state, f"{STATE_PREFIX}_preset_ranges"),
    ):
        _fill_ranges(
            {
                "c_q": PROFILE["q_range"],
                "c_phi": PROFILE["phi_range"],
                "d_q": PROFILE["q_range"],
            }
        )
        st.rerun()
    if fill_right.button(
        "Clear back to auto", key=action_key(st.session_state, f"{STATE_PREFIX}_clear_ranges")
    ):
        _fill_ranges({key: None for key in _RANGE_KEYS})
        st.rerun()

    st.caption(
        "Colour limits are in **intensity** units (pre-log). "
        "Auto colour uses robust percentiles of each panel."
    )
    ap, cp, dp = st.columns(3)
    ap.markdown("**A · raw**")
    a_vmin, a_vmax = _rng(ap, "I", "a_v")
    a_xr = _rng(ap, "x (px)", "a_x")
    a_yr = _rng(ap, "y (px)", "a_y")
    cp.markdown("**C · q–φ**")
    c_vmin, c_vmax = _rng(cp, "I", "c_v")
    c_qr = _rng(cp, "q", "c_q", *PROFILE["q_range"])
    # The reduction writes φ over -179 … +179; the halves mirror each other, so
    # the review default is the upper half.
    c_phir = _rng(cp, "φ", "c_phi", *PROFILE["phi_range"])
    dp.markdown("**D · I(q)**")
    d_qr = _rng(dp, "q", "d_q", *PROFILE["q_range"])
    d_ir = _rng(dp, "I", "d_i")
    st.caption("D curve style")
    d_style = _curve_style_controls(
        f"{STATE_PREFIX}_d_style", defaults={"color": "Crimson", "width": 2.2}
    )


if auto_q:
    _measured = frame_axis_ranges(sel)
    if _measured.get("qphi_q"):
        c_qr = _measured["qphi_q"]
    if _measured.get("cir_q"):
        d_qr = _measured["cir_q"]

if auto_i:
    # After the q block on purpose: `d_qr` is by now the window actually on
    # screen — auto-fitted or typed into the boxes — and the intensity limits
    # are measured from the points inside it.
    _curve_q, _curve_i = frame_curve(sel)
    if _curve_q is not None:
        _limits = intensity_limits_in_window(_curve_q, _curve_i, d_qr)
        if _limits:
            d_ir = _limits


# ===========================================================================
# Line-cut controls (q–φ only for transmission)
# ===========================================================================
st.divider()
_is_qcut = False
centers = []
if "qphi" in active_products:
    st.subheader("✂️ Line-cuts (q–φ)")
    lc2, lc3, lc4 = st.columns([1.6, 1.3, 1])
    cut_dir = lc2.selectbox(
        "Direction",
        ["q-cut  (I vs φ, fixed q band)", "φ-cut  (I vs q, fixed φ band)"],
        index=0,
        key=f"{STATE_PREFIX}_cut_dir",
    )
    _is_qcut = cut_dir.startswith("q-cut")
    centers_lab = "q center(s)" if _is_qcut else "φ center(s)"
    width_lab = "q width" if _is_qcut else "φ width"
    def_centers, def_width = (
        (PROFILE["q_cut_center"], PROFILE["q_cut_width"]) if _is_qcut else ("0", 10.0)
    )

    centers_txt = lc3.text_input(
        centers_lab,
        value=def_centers,
        help="Comma / space separated; one profile per center.",
        key=f"{STATE_PREFIX}_cut_centers",
    )
    width = lc4.number_input(
        width_lab,
        value=float(def_width),
        min_value=0.0,
        step=0.01,
        format="%.3f",
        key=f"{STATE_PREFIX}_cut_width",
    )
    centers = _parse_centers(centers_txt)
else:
    st.info("Select the q–φ product above to enable line-cuts.")

cut_curves = []  # list of (name, xarr, yarr)
qphi_shapes = []
_band_color = "rgba(255,0,0,0.15)"
_line_color = "crimson"

if centers and "qphi" in active_products and sel["has_qphi"]:
    try:
        q, phi, qphi, pmask = load_qphi(sel["qphi"])
    except DataReadError as exc:
        st.error(str(exc))
        q = phi = qphi = pmask = None
    pmask = pmask if getattr(pmask, "shape", None) == getattr(qphi, "shape", None) else None
    if qphi is not None:
        for c in centers:
            if _is_qcut:  # band in q → profile along phi
                res = _band_profile(qphi, phi, q, c, width, pmask)
                if res:
                    cut_curves.append((f"q={c:g}", res[0], res[1]))
                qphi_shapes.append(
                    dict(
                        type="rect",
                        xref="x",
                        yref="y",
                        y0=float(phi.min()),
                        y1=float(phi.max()),
                        x0=c - width / 2,
                        x1=c + width / 2,
                        fillcolor=_band_color,
                        line=dict(color=_line_color, width=1),
                    )
                )
            else:  # band in phi → profile along q
                res = _band_profile(qphi, q, phi, c, width, pmask)
                if res:
                    cut_curves.append((f"φ={c:g}", res[0], res[1]))
                qphi_shapes.append(
                    dict(
                        type="rect",
                        xref="x",
                        yref="y",
                        x0=float(q.min()),
                        x1=float(q.max()),
                        y0=c - width / 2,
                        y1=c + width / 2,
                        fillcolor=_band_color,
                        line=dict(color=_line_color, width=1),
                    )
                )

# ===========================================================================
# Four panels: A raw · B q-image (reserved) · C q–φ · D I(q)
# ===========================================================================
st.divider()
st.markdown(f"### 🖼️ {sel['stem']}")

# Figures kept as they are drawn, so the save panel below can offer any of them.
rendered_figures: dict[str, object] = {}
rendered_tables: dict[str, pd.DataFrame] = {}
rendered_arrays: dict[str, dict] = {}

PANEL_TITLES = {
    "stitched": "A · raw",
    "q_image": "B · q-image",
    "qphi": "C · q–φ map",
    "cir_avg": "D · I(q)",
}


def _render_panel(panel: str) -> None:
    """Draw one product panel. Only called when the frame actually has it."""

    if panel == "stitched":
        try:
            raw = load_raw(sel["raw"])
        except DataReadError as exc:
            st.error(str(exc))
            return
        z = raw.astype(float).copy()
        z[~np.isfinite(z)] = np.nan
        z[z <= 0] = np.nan
        z = np.flipud(z)  # right-side-up, lower-left origin
        z, px_x, px_y = _downsample(z, np.arange(z.shape[1]), np.arange(z.shape[0]))
        fig = _heatmap_fig(
            PANEL_TITLES[panel],
            z,
            px_x,
            px_y,
            "x (px)",
            "y (px)",
            y_reverse=False,
            vmin_I=a_vmin,
            vmax_I=a_vmax,
            x_range=a_xr,
            y_range=a_yr,
            aspect=_aspect_arg(),
        )
        st.plotly_chart(fig, use_container_width=True)
        rendered_figures[PANEL_TITLES[panel]] = fig
        rendered_arrays[PANEL_TITLES[panel]] = {"image": z}

    elif panel == "q_image":
        from pyscattviz.app.components.scattering import load_qimg, resolve_qimage

        try:
            data = load_qimg(sel["qimg"])
        except DataReadError as exc:
            st.error(str(exc))
            return
        qimg, qx, qz, qmask, b_xlab = resolve_qimage(data, "qx")
        z = _apply_mask(qimg, qmask)
        z = cleaning.clean(z, qx, qz, "qimage", "qimg")
        z, xx, yy = _downsample(z, qx, qz)
        fig = _heatmap_fig(
            PANEL_TITLES[panel],
            z,
            xx,
            yy,
            b_xlab,
            "qz (Å⁻¹)",
            vmin_I=None,
            vmax_I=None,
            aspect=_aspect_arg(),
        )
        st.plotly_chart(fig, use_container_width=True)
        rendered_figures[PANEL_TITLES[panel]] = fig
        rendered_arrays[PANEL_TITLES[panel]] = {
            "qimg": z,
            "qx": np.asarray(xx),
            "qz": np.asarray(yy),
        }

    elif panel == "qphi":
        try:
            q, phi, caked, pmask = load_qphi(sel["qphi"])
        except DataReadError as exc:
            st.error(str(exc))
            return
        pmask = pmask if getattr(pmask, "shape", None) == getattr(caked, "shape", None) else None
        z = _apply_mask(caked, pmask)
        z = cleaning.clean(z, q, phi, "qphi", "qphi")
        fig = _heatmap_fig(
            PANEL_TITLES[panel],
            z,
            q,
            phi,
            "q (Å⁻¹)",
            "φ (deg)",
            xlog=logq,
            shapes=qphi_shapes,
            vmin_I=c_vmin,
            vmax_I=c_vmax,
            x_range=c_qr,
            y_range=c_phir,
        )
        st.plotly_chart(fig, use_container_width=True)
        rendered_figures[PANEL_TITLES[panel]] = fig
        rendered_arrays[PANEL_TITLES[panel]] = {
            "qphi": z,
            "q": np.asarray(q),
            "phi": np.asarray(phi),
        }

    elif panel == "cir_avg":
        try:
            qq, ii = load_cir(sel["cir"])
        except DataReadError as exc:
            st.error(str(exc))
            return
        tk = _apply_curve_style(
            dict(x=qq, y=ii, name="I(q)", hovertemplate="q=%{x:.4f}<br>I=%{y:.3g}<extra></extra>"),
            d_style,
            base_color="crimson",
        )
        fig = go.Figure(go.Scatter(**tk))
        fig.update_xaxes(title_text="q (Å⁻¹)", range=_axrange(d_qr[0], d_qr[1], logq))
        fig.update_yaxes(title_text="I(q)", range=_axrange(d_ir[0], d_ir[1], logiq))
        _style_1d_axes(fig, logq, logiq)
        fig.update_layout(
            title=PANEL_TITLES[panel],
            height=_PANEL_H,
            template="plotly_white",
            margin=dict(l=60, r=15, t=40, b=45),
        )
        st.plotly_chart(fig, use_container_width=True)
        rendered_figures[PANEL_TITLES[panel]] = fig
        rendered_tables[PANEL_TITLES[panel]] = pd.DataFrame({"q": qq, "I": ii})


_HAS_PRODUCT = {
    "stitched": bool(sel["has_raw"]),
    "q_image": bool(sel["has_qimg"]),
    "qphi": bool(sel["has_qphi"]),
    "cir_avg": bool(sel["has_cir"]),
}
_selected = [p for p in ("stitched", "q_image", "qphi", "cir_avg") if p in active_products]
_shown = [p for p in _selected if _HAS_PRODUCT[p]]
_absent = [p for p in _selected if not _HAS_PRODUCT[p]]

# Pack the panels that will actually draw. The old fixed A/B/C/D grid always
# reserved four slots, so transmission data — which has no stitched raw image —
# opened with an empty first cell and the rest pushed out of place.
for _start in range(0, len(_shown), 2):
    _batch = _shown[_start : _start + 2]
    for _col, _panel in zip(st.columns(len(_batch)), _batch):
        with _col:
            _render_panel(_panel)

if _absent:
    _names = ", ".join(SCATTERING_PRODUCTS[p]["label"] for p in _absent)
    st.caption(f"Not present for this frame: {_names}.")
    if "q_image" in _absent:
        st.caption(
            "A qx–qz remesh is optional for transmission data; this panel appears "
            "as soon as `q_image/qimg_*.npz` files exist."
        )

if rendered_figures:
    st.divider()
    st.markdown("#### 💾 Save a panel to disk")
    chosen_panel = st.selectbox("Panel", list(rendered_figures), key=f"{STATE_PREFIX}_save_panel")
    render_save_panel(
        f"{PROFILE['name']} Explorer",
        f"{sel['stem']}_{chosen_panel.split('·')[-1].strip()}",
        key=f"{STATE_PREFIX}_panel_save",
        figure=rendered_figures[chosen_panel],
        figure_kind="plotly",
        table=rendered_tables.get(chosen_panel),
        arrays=rendered_arrays.get(chosen_panel),
        expanded=True,
        caption=(
            f"Written under the {PROFILE['name']}_Explorer subfolder of the output "
            "root. HTML stays interactive; PNG/SVG/PDF need the free kaleido package."
        ),
    )
    render_code_export(
        frame_panel_code(
            analysis_root,
            str(sel["stem"]),
            {
                "A · raw": "stitched",
                "QC image": "qc",
                "B · q-image": "q_image",
                "C · q–φ map": "qphi",
                "D · circular average": "cir_avg",
                "D · I(q)": "cir_avg",
                "A · stitched raw": "stitched",
            }.get(chosen_panel, "cir_avg"),
            cmap=cmap,
            log_intensity=logI,
            b_mode="qx",  # transmission has no qr–qz remesh
            log_q=logq,
        ),
        key=f"{STATE_PREFIX}_panel_code",
        tab_name=f"{PROFILE['name']} Explorer",
        filename=f"{sel['stem']}_panel",
    )
    render_batch_process(
        work,
        [
            item
            for item in ("stitched", "qc", "q_image", "qphi", "cir_avg")
            if item in active_products
        ],
        f"{PROFILE['name']} Explorer",
        key=STATE_PREFIX,
        panel_options=dict(
            cmap=cmap,
            logI=logI,
            height=_PANEL_H,
            b_mode="qx",
            aspect=_aspect_arg(),
            logq=logq,
            logiq=logiq,
        ),
        cleaning=cleaning,
        defaults={"iq": True, "iphi": True, "manifest": True},
    )

if "qc" in active_products:
    st.subheader("QC image")
    qc_cols = st.columns(2)
    with qc_cols[0]:
        if sel["has_qc"]:
            # st.image decodes the file itself, so a truncated or zero-byte PNG
            # raises straight out of PIL. Report it like any other bad product.
            try:
                st.image(sel["qc"], caption="QC image", width="stretch")
            except Exception as exc:  # noqa: BLE001 - PIL raises several types
                st.error(f"{Path(sel['qc']).name} could not be read: {exc}")
        else:
            st.info("No QC image for this frame.")

# ===========================================================================
# Line-cut result plot + export
# ===========================================================================
if centers:
    st.divider()
    st.markdown("#### Line-cut profiles")
    if not cut_curves:
        st.warning("No data in the chosen band(s) — check centers / width.")
    else:
        xlab = "φ (deg)" if _is_qcut else "q (Å⁻¹)"
        xlog = logq and not _is_qcut

        with st.expander("🎛️ Line-cut plot: limits & style", expanded=True):
            lp1, lp2 = st.columns(2)
            lc_xr = (
                _rng(lp1, xlab, "lc_x_phi", *PROFILE["phi_range"])
                if xlab.startswith("φ")
                else _rng(lp1, xlab, "tsaxs_lc_x")
            )
            lc_yr = _rng(lp2, "I", "tsaxs_lc_i")
            st.caption("Profile curve style (applied to all cuts)")
            lc_style = _curve_style_controls(f"{STATE_PREFIX}_lc_style", defaults={"width": 2.0})

        import plotly.express as px

        base_colors = px.colors.sample_colorscale(
            "Turbo", np.linspace(0, 1, max(1, len(cut_curves)))
        )
        fig = go.Figure()
        for (name, xa, ya), col in zip(cut_curves, base_colors):
            tk = _apply_curve_style(dict(x=xa, y=ya, name=name), lc_style, base_color=col)
            fig.add_trace(go.Scatter(**tk))
        fig.update_xaxes(title_text=xlab, range=_axrange(lc_xr[0], lc_xr[1], xlog))
        fig.update_yaxes(title_text="I (band mean)", range=_axrange(lc_yr[0], lc_yr[1], logiq))
        _style_1d_axes(fig, xlog, logiq)
        fig.update_layout(
            height=420,
            template="plotly_white",
            margin=dict(l=60, r=15, t=25, b=50),
            legend=dict(orientation="h", y=1.05),
        )
        st.plotly_chart(fig, use_container_width=True)

        # CSV export: outer-join all profiles on their common x-axis.
        buf = io.StringIO()
        frames = [pd.DataFrame({xlab: xa, f"I[{name}]": ya}) for name, xa, ya in cut_curves]
        out = frames[0]
        for f in frames[1:]:
            out = out.merge(f, on=xlab, how="outer")
        out = out.sort_values(xlab)
        out.to_csv(buf, index=False)
        st.download_button(
            "⬇️ Download line-cuts (CSV)",
            buf.getvalue(),
            file_name=f"linecuts_{sel['stem']}.csv",
            mime="text/csv",
        )
        render_save_panel(
            f"{PROFILE['name']} Explorer",
            f"linecuts_{sel['stem']}",
            key=f"{STATE_PREFIX}_linecut_save",
            figure=fig,
            figure_kind="plotly",
            table=out,
            subfolder="line_cuts",
            caption="The cuts land in a line_cuts subfolder so they stay together.",
        )

# --- Frame table ------------------------------------------------------------
with st.expander("📋 Frame table", expanded=False):
    st.dataframe(
        work[["stem", "well", "timestamp", "has_raw", "has_qc", "has_qimg", "has_qphi", "has_cir"]],
        width="stretch",
        hide_index=True,
    )
