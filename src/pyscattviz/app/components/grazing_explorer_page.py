"""Shared implementation for the independent GISAXS and GIWAXS pages.

Point it at an SMI ``Results/gisaxs`` or ``Results/giwaxs`` folder, or at a
CMS MAXS/GIWAXS ``analysis/`` folder, containing per reduced frame:

* ``stitched/<name>.tiff``            → the stitched raw detector image (A).
* ``q_image/qimg_<name>.tiff.npz``    → keys ``qimg (nz, nx)``, ``qx (nx,)``,
  ``qz (nz,)``, ``qimg_mask (nz, nx)`` — the remeshed q-space image (B).
* ``qphi/qphi_<name>.tiff.npz``       → keys ``q (nq,)``, ``phi (nphi,)``,
  ``qphi (nphi, nq)``, ``qphi_mask`` — the q–φ caking map (C).
* ``cir_avg/Cir_Avg_<name>.tiff.csv`` → columns ``q_ca, iq_ca`` — the circular
  average (D).
* ``qc/qc_<name>.png``                 → an optional quality-control image.

Paste either the product root or one product folder. The sidebar discovers the
available products, reports their file counts, and lets the user choose which
panels to render. You can also take **line-cuts**:

* on the **q_image** — a *qr-cut* (I vs qr at a fixed qz band) or a *qz-cut*
  (I vs qz at a fixed qr band),
* on the **q–φ** map — a *q-cut* (I vs φ at a fixed q band) or a *φ-cut*
  (I vs q at a fixed φ band).

Each cut is defined by one or more **centers** (comma-separated) and a single
band **width**; the integration band is overlaid on the map and the extracted
1-D profiles are plotted together (and exportable as CSV).

Runs as a page of the pyScattViz local application.
"""

from __future__ import annotations

import io

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
from pyscattviz.app.components.maskeditor import (
    add_selection_grid,
    render_selection_capture,
)
from pyscattviz.app.components.saving import render_output_settings, render_save_panel

# Shared scattering engine — indexing, loaders, array/plot helpers, styling.
# Some are aliased to the underscore names this page's body already uses.
from pyscattviz.app.components.scattering import (
    CMAPS,
    detect_beamline,
    frame_axis_ranges,
    frame_curve,
    heatmap_fig,
    index_frames,
    intensity_limits_in_window,
    load_cir,
    load_qimg,
    load_qphi,
    load_raw,
    qimage_has_qr,
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

EXPLORER_MODE = globals().get("EXPLORER_MODE", "giwaxs")
_PROFILES = {
    "gisaxs": {
        "name": "GISAXS",
        "icon": "🧭",
        "folder": "gisaxs",
        "state": "gisaxs",
        "description": (
            "Small-angle grazing-incidence review with GISAXS-specific q limits, "
            "qx/qz band cuts, q–φ cuts, and log-q I(q) defaults."
        ),
        "logq": True,
        "qx_range": (-0.5, 0.5),
        "qz_range": (0.0, 0.5),
        "q_range": (0.001, 0.5),
        "qphi_q_range": (0.001, 0.5),
        "phi_range": (0.0, 180.0),
        "q_cut_center": "0.1",
        "q_cut_width": 0.01,
        "qz_cut_center": "0.05",
        "qz_cut_width": 0.01,
    },
    "giwaxs": {
        "name": "GIWAXS",
        "icon": "🧭",
        "folder": "giwaxs",
        "state": "giwaxs",
        "description": (
            "Wide-angle grazing-incidence review with GIWAXS-specific q limits, "
            "q-space orientation maps, q–φ cuts, and linear-q defaults."
        ),
        "logq": False,
        # The first quadrant out to 5 A^-1 is the GIWAXS view Yugang reviews;
        # "Fit to this frame" opens it up to whatever the frame really covers.
        "qx_range": (0.0, 5.0),
        "qz_range": (0.0, 5.0),
        "q_range": (0.0, 5.0),
        "qphi_q_range": (0.0, 5.0),
        "phi_range": (0.0, 180.0),
        "q_cut_center": "1.0",
        "q_cut_width": 0.05,
        "qz_cut_center": "0.0",
        "qz_cut_width": 0.05,
    },
}
# CMS and SMI put different detectors at different distances, so the window
# worth opening on differs. These are the values Yugang reviews CMS GIWAXS in;
# anything without an entry here starts on auto-fit instead (see AUTO_Q_KEY).
_BEAMLINE_PROFILES = {
    ("giwaxs", "cms"): {
        "qx_range": (0.0, 3.0),
        "qz_range": (0.0, 3.0),
        "qphi_q_range": (0.5, 3.5),
        "phi_range": (0.0, 180.0),
    },
}

PROFILE = dict(_PROFILES[EXPLORER_MODE])
STATE_PREFIX = f"pyscattviz_{PROFILE['state']}"
AUTO_Q_KEY = f"{STATE_PREFIX}_auto_q"
AUTO_I_KEY = f"{STATE_PREFIX}_auto_i"
BEAMLINE_KEY = f"{STATE_PREFIX}_last_beamline"

# ===========================================================================
st.set_page_config(
    page_title=f"{PROFILE['name']} Explorer",
    page_icon=PROFILE["icon"],
    layout="wide",
)

# Streamlit forgets a page's widgets as soon as another page is opened.
keep_widget_state(st.session_state)

st.title(f"{PROFILE['icon']} {PROFILE['name']} Explorer")
st.caption(PROFILE["description"])

with st.sidebar:
    st.header(f"📁 {PROFILE['name']} data")

    # One mounted drive usually holds many proposals, beamlines, and projects,
    # so the picker offers every folder the session knows and keeps whatever is
    # typed even when it is not available yet.
    analysis = render_folder_picker(
        STATE_PREFIX,
        f"Data path ({PROFILE['folder']}/ or one product folder)",
        help_text=(
            "A result folder, or one product folder inside it. An original "
            "/nsls2/... path works once its mount is registered."
        ),
    )
    if not analysis:
        st.info("Choose or paste a data folder to start.")
        st.stop()

    # "Once the folder contains cms" — the window worth opening on follows the
    # beamline, so apply its preset the moment the data comes from a different
    # one rather than leaving the previous beamline's limits in place.
    BEAMLINE = detect_beamline(analysis)
    _override = _BEAMLINE_PROFILES.get((EXPLORER_MODE, BEAMLINE))
    if _override:
        PROFILE.update(_override)
    if st.session_state.get(BEAMLINE_KEY) != (EXPLORER_MODE, BEAMLINE):
        st.session_state[BEAMLINE_KEY] = (EXPLORER_MODE, BEAMLINE)
        # Auto q wins even where a beamline preset exists, because how far a
        # frame reaches in q is a property of the detector rather than a
        # preference. CMS GIWAXS opened on qx 0–3 by preset, but a Pilatus800
        # whose active area starts 300 px left of the beam covers -2.18 … +1.23
        # — so that window showed a band of blank on one side and hid most of
        # the data on the other. The preset still fills the boxes below, so
        # unticking "Auto q limits" gives it back in one click.
        st.session_state[AUTO_Q_KEY] = True
        st.session_state[AUTO_I_KEY] = True
        for _key, _span in (
            ("b_qx", PROFILE["qx_range"]),
            ("b_qz", PROFILE["qz_range"]),
            ("c_q", PROFILE["qphi_q_range"]),
            ("c_phi", PROFILE["phi_range"]),
            ("d_q", PROFILE["q_range"]),
        ):
            st.session_state[f"{STATE_PREFIX}_{_key}_lo"] = float(_span[0])
            st.session_state[f"{STATE_PREFIX}_{_key}_hi"] = float(_span[1])

    analysis_root, products, selected_products = scattering_product_selector(
        f"{PROFILE['state']}_products", analysis
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
        placeholder="sampleA AND 0.1000deg NOT AgBH",
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
th = f"{sel['th']:.3f}°" if pd.notna(sel["th"]) else "—"
st.markdown(f"**{sel['stem']}**  ·  θ = {th}  ·  well `{sel['well']}`  ·  t = {ts}")

# --- Display controls -------------------------------------------------------
dc1, dc2, dc3, dc4 = st.columns(4)
logI = dc1.checkbox("log I (2D panels)", value=True, key=f"{STATE_PREFIX}_logI")
logq = dc2.checkbox("log q (1D)", value=PROFILE["logq"], key=f"{STATE_PREFIX}_logq")
logiq = dc3.checkbox("log I (1D)", value=True, key=f"{STATE_PREFIX}_logiq")
cmap = dc4.selectbox(
    "2D colormap", CMAPS, index=0, key=f"{STATE_PREFIX}_cmap"
)  # default Turbo (item 4)

# Second row: aspect ratio (shared by A & B, item 2) + B-panel axis mode (item 3)


# One or two pixels on every CMS/SMI detector read absurdly high whatever the
# sample. The azimuthal average is a mean, so a single 500,000-count pixel moves
# a whole q bin and the 1-D curve grows a peak that is not there.
def _preview_frame():
    """The 2D product the hot-pixel thresholds are judged against.

    Every loader is cached, so reading a product here costs nothing the page was
    not about to spend a few lines further down anyway.
    """

    try:
        if sel.get("has_qimg"):
            return resolve_qimage(load_qimg(sel["qimg"]), "qx")[0]
        if sel.get("has_qphi"):
            return load_qphi(sel["qphi"])[2]
    except (DataReadError, KeyError, TypeError, ValueError):
        return None
    return None


# Hot pixels, the across-frames vote, and the exclusion mask, in one place —
# the same object the batch below uses, so a batch cannot drift from what the
# panels are showing.
cleaning = render_cleaning_controls(STATE_PREFIX, work, preview_image=_preview_frame())
hot = cleaning.hot
user_mask = cleaning.mask
despike = hot.enabled
_drawing = cleaning.drawing


def _defect_mask_for(product: str):
    return cleaning.defect_mask(product)


def _apply_user_mask(z, x_axis, y_axis, space: str):
    """Kept for the call sites that clean an array they already hold."""

    return cleaning.clean(z, x_axis, y_axis, space, product=None)


dc5, dc6 = st.columns(2)
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
# Does the current frame's q_image expose a qr–qz representation? A frame whose
# npz is unreadable must not take the page down with it.
_qimg_data = None
_qimg_error = ""
if "q_image" in active_products and sel["has_qimg"]:
    try:
        _qimg_data = load_qimg(sel["qimg"])
    except DataReadError as exc:
        _qimg_error = str(exc)
_has_qr = qimage_has_qr(_qimg_data)
b_axis_mode = dc6.selectbox(
    "B x-axis",
    ["qx–qz", "qr–qz"],
    index=0,
    help=(
        "qr–qz needs a 'qr' (and optional 'qrimg') key in the q_image npz."
        if not _has_qr
        else "Plot against qx or in-plane qr."
    ),
    key=f"{STATE_PREFIX}_b_axis",
)
b_mode = "qr" if b_axis_mode.startswith("qr") else "qx"
if b_mode == "qr" and not _has_qr:
    dc6.caption("⚠️ No qr key in this npz yet — showing qx–qz.")
elif _has_qr:
    # A reduction run with `qimg_x_axis = ['Qx', 'Qr']` puts both remeshes in
    # one npz. Nothing on screen said so, so the second one went unnoticed.
    dc6.caption("✅ This npz carries both remeshes — switch them here.")

_PANEL_H = 380


def _rng(col, label, key, lo_val=None, hi_val=None, fmt="%.4g"):
    """Two side-by-side optional number inputs → (min, max); None means auto."""
    a, b = col.columns(2)
    lo = a.number_input(f"{label} min", value=lo_val, key=f"{STATE_PREFIX}_{key}_lo", format=fmt)
    hi = b.number_input(f"{label} max", value=hi_val, key=f"{STATE_PREFIX}_{key}_hi", format=fmt)
    return lo, hi


# Axis limits start blank, which lets each panel autoscale to the frame it is
# actually showing. Fixed defaults were wrong more often than right: the q a
# reduction covers depends on the detector, its distance, and the energy, so a
# GIWAXS q–φ map that reaches 7 Å⁻¹ was being cut off at 3, and φ runs -179 to
# +179 rather than 0 to 180. The two buttons below fill the boxes explicitly.
_RANGE_KEYS = ("b_qx", "b_qz", "c_q", "c_phi", "d_q")


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
    st.caption(
        "Blank means the panel scales to the data it is showing. Colour limits "
        "are in **intensity** units (pre-log); auto colour uses robust "
        "percentiles of each panel."
    )
    _auto_columns = st.columns(2)
    auto_q = _auto_columns[0].checkbox(
        "Auto q limits",
        value=bool(st.session_state.get(AUTO_Q_KEY, True)),
        key=AUTO_Q_KEY,
        help=(
            "Frame the q-image, the q–φ q axis and I(q) on the data itself. A "
            "remeshed q-image covers only part of the qx–qz plane and the rest is "
            "blank, so a fixed window leaves the picture stranded in NaN. φ is "
            "left alone. Turn this off to pin your own q range."
        ),
    )
    auto_i = _auto_columns[1].checkbox(
        "Auto intensity limits",
        value=bool(st.session_state.get(AUTO_I_KEY, True)),
        key=AUTO_I_KEY,
        help=(
            "Set the I(q) limits from the points inside the q window that is "
            "actually shown — so choosing a q range by hand rescales the "
            "intensity to match, instead of leaving a flat line at the top of a "
            "panel scaled to the full four decades."
        ),
    )
    fill_left, fill_middle, fill_right = st.columns([1.2, 1.4, 2.4])
    if fill_left.button(
        "Fit to this frame", key=action_key(st.session_state, f"{STATE_PREFIX}_fit_ranges")
    ):
        measured = frame_axis_ranges(sel, b_mode)
        _fill_ranges(
            {
                "b_qx": measured.get("qr" if b_mode == "qr" else "qx"),
                "b_qz": measured.get("qz"),
                "c_q": measured.get("qphi_q"),
                "c_phi": measured.get("phi"),
                "d_q": measured.get("cir_q"),
            }
        )
        st.rerun()
    if fill_middle.button(
        f"{PROFILE['name']} preset",
        key=action_key(st.session_state, f"{STATE_PREFIX}_preset_ranges"),
    ):
        _fill_ranges(
            {
                "b_qx": PROFILE["qx_range"],
                "b_qz": PROFILE["qz_range"],
                "c_q": PROFILE["qphi_q_range"],
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

    ap, bp, cp = st.columns(3)
    ap.markdown("**A · raw**")
    a_vmin, a_vmax = _rng(ap, "I", "a_v")
    a_xr = _rng(ap, "x (px)", "a_x")  # pixel x limits (item 1)
    a_yr = _rng(ap, "y (px)", "a_y")  # pixel y limits (item 1)
    bp.markdown("**B · q-image**")
    b_vmin, b_vmax = _rng(bp, "I", "b_v")
    _bx_lab = "qr" if b_mode == "qr" else "qx"
    b_qxr = _rng(bp, _bx_lab, "b_qx", *PROFILE["qx_range"])
    b_qzr = _rng(bp, "qz", "b_qz", *PROFILE["qz_range"])
    cp.markdown("**C · q–φ**")
    c_vmin, c_vmax = _rng(cp, "I", "c_v")
    c_qr = _rng(cp, "q", "c_q", *PROFILE["qphi_q_range"])
    # The reduction writes φ over -179 … +179; the two halves are mirror images
    # for an isotropic film, so the review default is the upper half.
    c_phir = _rng(cp, "φ", "c_phi", *PROFILE["phi_range"])
    st.markdown("**D · circular average**")
    dp1, dp2 = st.columns(2)
    d_qr = _rng(dp1, "q", "d_q", *PROFILE["q_range"])
    d_ir = _rng(dp2, "I", "d_i")
    # The azimuth the re-integrated curve averages over. Blank means the whole
    # map, which is what makes it comparable with the circular average on disk;
    # narrowing it turns the same control into a sector average.
    _rp1, _rp2 = st.columns(2)
    _re_phi_lo = _rp1.number_input(
        "Re-integrate φ min",
        value=None,
        key=f"{STATE_PREFIX}_reint_phi_lo",
        format="%.4g",
        help="Blank = the whole azimuth. Set both for a sector average.",
    )
    _re_phi_hi = _rp2.number_input(
        "Re-integrate φ max", value=None, key=f"{STATE_PREFIX}_reint_phi_hi", format="%.4g"
    )
    _reintegrate_phi = (
        (float(_re_phi_lo), float(_re_phi_hi))
        if _re_phi_lo is not None and _re_phi_hi is not None
        else None
    )
    st.caption("D curve style")
    d_style = _curve_style_controls(
        f"{STATE_PREFIX}_d_style", defaults={"color": "Crimson", "width": 2.2}
    )

    # What the frame actually covers, always on screen. A q-image is a remesh
    # of a detector that reaches where it reaches: type a window outside that
    # and the panel is blank with nothing to say why. The numbers are measured
    # from the frame, so they are also the fastest way to see that a detector
    # sits off-centre — a Pilatus800 whose active area starts left of the beam
    # covers far more negative qx than positive.
    _coverage = frame_axis_ranges(sel, b_mode)
    _cov_bits = [
        f"{_name} {_span[0]:+.2f} … {_span[1]:+.2f}"
        for _name, _key in (
            ("qr" if b_mode == "qr" else "qx", "qr" if b_mode == "qr" else "qx"),
            ("qz", "qz"),
            ("q–φ q", "qphi_q"),
            ("I(q) q", "cir_q"),
        )
        if (_span := _coverage.get(_key))
    ]
    if _cov_bits:
        st.caption("This frame covers " + " · ".join(_cov_bits))


if auto_q:
    _measured = _coverage
    _fitted = _measured.get("qr" if b_mode == "qr" else "qx")
    if _fitted:
        b_qxr = _fitted
    if _measured.get("qz"):
        b_qzr = _measured["qz"]
    if _measured.get("qphi_q"):
        c_qr = _measured["qphi_q"]
    if _measured.get("cir_q"):
        d_qr = _measured["cir_q"]

if auto_i:
    # Deliberately after the q block: `d_qr` is by now the window actually on
    # screen, whether that came from auto-fit or from the boxes, and the
    # intensity is scaled to the points inside it.
    _curve_q, _curve_i = frame_curve(sel)
    if _curve_q is not None:
        _limits = intensity_limits_in_window(_curve_q, _curve_i, d_qr)
        if _limits:
            d_ir = _limits


def _heatmap_fig(title, z, x, y, xlab, ylab, **kw):
    """Thin wrapper injecting this page's colormap / log toggle / panel height
    into the shared engine ``heatmap_fig``."""
    return heatmap_fig(title, z, x, y, xlab, ylab, cmap=cmap, logI=logI, height=_PANEL_H, **kw)


def _aspect_arg():
    """Translate the aspect-mode control into the _heatmap_fig ``aspect`` arg."""
    if aspect_mode == "Equal (1:1)":
        return "equal"
    if aspect_mode == "Custom":
        return aspect_ratio
    return None


# ===========================================================================
# Line-cut controls (built first so we can overlay bands on the panels below)
# ===========================================================================
st.divider()
cut_source = ""
centers = []
_is_qr = False
_is_qcut = False
# The horizontal (in-plane) axis of the q-image follows the B-panel mode.
_bx = "qr" if b_mode == "qr" else "qx"
cut_options = []
if "q_image" in active_products:
    cut_options.append(f"q_image ({_bx}–qz)")
if "qphi" in active_products:
    cut_options.append("q–φ map")

if cut_options:
    st.subheader("✂️ Line-cuts")
    lc1, lc2, lc3, lc4 = st.columns([1.3, 1.6, 1.3, 1])
    cut_source = lc1.selectbox(
        "Cut on",
        cut_options,
        index=1 if len(cut_options) > 1 else 0,
        key=f"{STATE_PREFIX}_cut_source",
    )

    if cut_source.startswith("q_image"):
        cut_dir = lc2.selectbox(
            "Direction",
            [f"{_bx}-cut  (I vs {_bx}, fixed qz band)", f"qz-cut  (I vs qz, fixed {_bx} band)"],
            index=0,
            key=f"{STATE_PREFIX}_cut_dir_qimage",
        )
        _is_qr = cut_dir.startswith(_bx)
        centers_lab = "qz center(s)" if _is_qr else f"{_bx} center(s)"
        width_lab = "qz width" if _is_qr else f"{_bx} width"
        def_centers = PROFILE["qz_cut_center"]
        def_width = PROFILE["qz_cut_width"]
    else:
        cut_dir = lc2.selectbox(
            "Direction",
            ["q-cut  (I vs φ, fixed q band)", "φ-cut  (I vs q, fixed φ band)"],
            index=0,
            key=f"{STATE_PREFIX}_cut_dir_qphi",
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
    st.info("Select q_image or q–φ above to enable line-cuts.")

# Compute the cut profiles and the band rectangles to overlay on the map.
cut_curves = []  # list of (name, xarr, yarr)
qimg_shapes, qphi_shapes = [], []
_band_color = "rgba(255,0,0,0.15)"
_line_color = "crimson"

if centers:
    if cut_source.startswith("q_image") and sel["has_qimg"] and _qimg_data is not None:
        qimg, qx, qz, qmask, _ = resolve_qimage(_qimg_data, b_mode)
        if qimg is not None and despike:
            qimg = hot.clean(_apply_mask(qimg, qmask), _defect_mask_for("qimg"))
            qimg = _apply_user_mask(qimg, qx, qz, "qimage")
            qmask = None
        if qimg is not None:
            for c in centers:
                if _is_qr:  # band in qz → profile along in-plane axis (qx/qr)
                    res = _band_profile(qimg, qx, qz, c, width, qmask)
                    if res:
                        cut_curves.append((f"qz={c:g}", res[0], res[1]))
                    qimg_shapes.append(
                        dict(
                            type="rect",
                            xref="x",
                            yref="y",
                            x0=float(qx.min()),
                            x1=float(qx.max()),
                            y0=c - width / 2,
                            y1=c + width / 2,
                            fillcolor=_band_color,
                            line=dict(color=_line_color, width=1),
                        )
                    )
                else:  # band in in-plane axis → profile along qz
                    res = _band_profile(qimg, qz, qx, c, width, qmask)
                    if res:
                        cut_curves.append((f"{_bx}={c:g}", res[0], res[1]))
                    qimg_shapes.append(
                        dict(
                            type="rect",
                            xref="x",
                            yref="y",
                            y0=float(qz.min()),
                            y1=float(qz.max()),
                            x0=c - width / 2,
                            x1=c + width / 2,
                            fillcolor=_band_color,
                            line=dict(color=_line_color, width=1),
                        )
                    )
    elif cut_source.startswith("q–φ") and sel["has_qphi"]:
        try:
            q, phi, qphi, pmask = load_qphi(sel["qphi"])
        except DataReadError as exc:
            st.error(str(exc))
            q = phi = qphi = pmask = None
        # qphi_mask is stored on the raw-detector grid, not (nphi, nq); skip it.
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
# Selected scattering panels
# ===========================================================================
st.divider()
st.markdown(f"### 🖼️ {sel['stem']}")


# Figures kept as they are drawn, so the save panel below can offer any of them.
rendered_figures: dict[str, object] = {}
rendered_tables: dict[str, pd.DataFrame] = {}
rendered_arrays: dict[str, dict] = {}


def _render_image(path, title, *, flip=False):
    if not path:
        st.info(f"No {title.lower()} for this frame.")
        return
    try:
        raw = load_raw(path)
    except DataReadError as exc:
        st.error(str(exc))
        return
    z = raw.astype(float)
    # QC PNGs can be RGB/RGBA; use a luminance-like average for the shared
    # heatmap renderer while preserving the same panel behavior as raw images.
    if z.ndim == 3:
        z = z[..., :3].mean(axis=2)
    z[~np.isfinite(z)] = np.nan
    z[z <= 0] = np.nan
    if flip:
        z = np.flipud(z)
    ny0, nx0 = z.shape
    px_x, px_y = np.arange(nx0), np.arange(ny0)
    z, px_x, px_y = _downsample(z, px_x, px_y)
    fig = _heatmap_fig(
        title,
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
    rendered_figures[title] = fig
    rendered_arrays[title] = {"image": z}


def _render_panel(panel):
    """Render one selected product; unavailable frames stay localized."""
    if panel == "stitched":
        if sel["has_raw"]:
            _render_image(sel["raw"], "A · stitched raw", flip=True)
        else:
            st.info("No stitched raw image for this frame.")
    elif panel == "qc":
        if sel["has_qc"]:
            _render_image(sel["qc"], "QC image")
        else:
            st.info("No QC image for this frame.")
    elif panel == "q_image":
        if _qimg_error:
            st.error(_qimg_error)
        elif sel["has_qimg"] and _qimg_data is not None:
            qimg, qx, qz, qmask, b_xlab = resolve_qimage(_qimg_data, b_mode)
            z = _apply_mask(qimg, qmask)
            z = hot.clean(z, _defect_mask_for("qimg"))
            z = _apply_user_mask(z, qx, qz, "qimage")
            z, xx, yy = _downsample(z, qx, qz)
            fig = _heatmap_fig(
                f"B · q-image ({'qr–qz' if b_mode == 'qr' else 'qx–qz'})"
                if _has_qr
                else "B · q-image",
                z,
                xx,
                yy,
                b_xlab,
                "qz (Å⁻¹)",
                shapes=qimg_shapes,
                vmin_I=b_vmin,
                vmax_I=b_vmax,
                x_range=b_qxr,
                y_range=b_qzr,
                aspect=_aspect_arg(),
            )
            # Box- or lasso-select on the picture to define a mask region.
            # The selection comes back in data coordinates, so the shape is
            # stored in q and stays right when the frame or the zoom changes.
            fig.update_layout(dragmode="select" if _drawing else "zoom")
            if _drawing:
                add_selection_grid(fig, xx, yy)
            _event = st.plotly_chart(
                fig,
                use_container_width=True,
                key=action_key(st.session_state, f"{STATE_PREFIX}_qimg_chart"),
                on_select="rerun",
                selection_mode=("points", "box", "lasso"),
            )
            render_selection_capture(STATE_PREFIX, _event, "qimage")
            rendered_figures["B · q-image"] = fig
            rendered_arrays["B · q-image"] = {
                "qimg": z,
                b_mode: np.asarray(xx),
                "qz": np.asarray(yy),
            }
        else:
            st.info("No q-image for this frame.")
    elif panel == "qphi":
        if sel["has_qphi"]:
            try:
                q, phi, qphi, pmask = load_qphi(sel["qphi"])
            except DataReadError as exc:
                st.error(str(exc))
                return
            pmask = pmask if getattr(pmask, "shape", None) == getattr(qphi, "shape", None) else None
            z = _apply_mask(qphi, pmask)
            z = hot.clean(z, _defect_mask_for("qphi"))
            z = _apply_user_mask(z, q, phi, "qphi")
            fig = _heatmap_fig(
                "C · q–φ map",
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
            fig.update_layout(dragmode="select" if _drawing else "zoom")
            if _drawing:
                add_selection_grid(fig, q, phi)
            _event = st.plotly_chart(
                fig,
                use_container_width=True,
                key=action_key(st.session_state, f"{STATE_PREFIX}_qphi_chart"),
                on_select="rerun",
                selection_mode=("points", "box", "lasso"),
            )
            render_selection_capture(STATE_PREFIX, _event, "qphi")
            rendered_figures["C · q–φ map"] = fig
            rendered_arrays["C · q–φ map"] = {
                "qphi": z,
                "q": np.asarray(q),
                "phi": np.asarray(phi),
            }
        else:
            st.info("No q–φ map for this frame.")
    elif panel == "cir_avg":
        if sel["has_cir"]:
            try:
                qq, ii = load_cir(sel["cir"])
            except DataReadError as exc:
                st.error(str(exc))
                return
            tk = _apply_curve_style(
                dict(
                    x=qq,
                    y=ii,
                    name="I(q) · reduction",
                    hovertemplate="q=%{x:.4f}<br>I=%{y:.3g}<extra></extra>",
                ),
                d_style,
                base_color="crimson",
            )
            fig = go.Figure(go.Scatter(**tk))
            # The reduction's circular average was computed before anyone
            # looked at the data, so the hot pixels are in it and so is every
            # region excluded by hand afterwards. Nothing done in the 2D panels
            # can reach a CSV written weeks ago, so the curve that answers to
            # the masks has to be rebuilt here from the q–φ map.
            _clean_q, _clean_i, _clean_info = cleaning.curve(sel, _reintegrate_phi)
            if _clean_q is not None:
                _applied = []
                if hot.enabled:
                    _applied.append("hot pixels")
                if user_mask.enabled_regions():
                    _applied.append(f"{len(user_mask.enabled_regions())} masked region(s)")
                if _reintegrate_phi:
                    _applied.append(f"φ {_reintegrate_phi[0]:g}…{_reintegrate_phi[1]:g}°")
                _trace_name = "I(q) · re-integrated"
                if _applied:
                    _trace_name += " − " + ", ".join(_applied)
                fig.add_trace(
                    go.Scatter(
                        x=_clean_q,
                        y=_clean_i,
                        name=_trace_name,
                        mode="lines",
                        line=dict(color="#1f77b4", width=1.8),
                        hovertemplate="q=%{x:.4f}<br>I=%{y:.3g}<extra></extra>",
                    )
                )
                rendered_tables["D · I(q) re-integrated"] = pd.DataFrame(
                    {"q": _clean_q, "I": _clean_i}
                )
            fig.update_xaxes(title_text="q (Å⁻¹)", range=_axrange(d_qr[0], d_qr[1], logq))
            fig.update_yaxes(title_text="I(q)", range=_axrange(d_ir[0], d_ir[1], logiq))
            _style_1d_axes(fig, logq, logiq)
            fig.update_layout(
                title="D · circular average",
                height=_PANEL_H,
                template="plotly_white",
                margin=dict(l=60, r=15, t=40, b=45),
            )
            st.plotly_chart(fig, use_container_width=True)
            if _clean_q is not None:
                _pct = 100 * _clean_info.get("blanked", 0) / max(_clean_info.get("total", 1), 1)
                _bits = [
                    f"re-integrated over {_clean_info.get('bins', 0)} φ rows",
                    f"{_clean_info.get('blanked', 0):,} of {_clean_info.get('total', 0):,} "
                    f"q–φ pixels excluded ({_pct:.2f}%)",
                ]
                if _clean_info.get("empty"):
                    _bits.append(
                        f"{_clean_info['empty']:,} q bin(s) left with nothing — "
                        "a gap in the curve, not a zero"
                    )
                st.caption(" · ".join(_bits))
            rendered_figures["D · circular average"] = fig
            rendered_tables["D · circular average"] = pd.DataFrame({"q": qq, "I": ii})
        else:
            st.info("No circular average for this frame.")


panel_order = [p for p in ("stitched", "qc", "q_image", "qphi", "cir_avg") if p in active_products]
for start in range(0, len(panel_order), 2):
    row = st.columns(2)
    for col, panel in zip(row, panel_order[start : start + 2]):
        with col:
            _render_panel(panel)

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
            b_mode=b_mode,
            log_q=logq,
        ),
        key=f"{STATE_PREFIX}_panel_code",
        tab_name=f"{PROFILE['name']} Explorer",
        filename=f"{sel['stem']}_panel",
    )
    render_batch_process(
        work,
        panel_order,
        f"{PROFILE['name']} Explorer",
        key=STATE_PREFIX,
        panel_options=dict(
            cmap=cmap,
            logI=logI,
            height=_PANEL_H,
            b_mode=b_mode,
            aspect=_aspect_arg(),
            logq=logq,
            logiq=logiq,
        ),
        cleaning=cleaning,
        defaults={"iq": True, "manifest": True},
    )

# ===========================================================================
# Line-cut result plot + export
# ===========================================================================
if centers:
    st.divider()
    st.markdown("#### Line-cut profiles")
    if not cut_curves:
        st.warning("No data in the chosen band(s) — check centers / width / source panel.")
    else:
        along_is_q = (cut_source.startswith("q_image") and _is_qr) or (
            cut_source.startswith("q–φ") and not _is_qcut
        )
        if cut_source.startswith("q_image"):
            xlab = f"{_bx} (Å⁻¹)" if _is_qr else "qz (Å⁻¹)"
        else:
            xlab = "φ (deg)" if _is_qcut else "q (Å⁻¹)"
        xlog = logq and along_is_q

        # A φ profile opens on the upper half, matching the q–φ panel above it.
        _phi_profile = xlab.startswith("φ")
        with st.expander("🎛️ Line-cut plot: limits & style", expanded=True):
            lp1, lp2 = st.columns(2)
            lc_xr = (
                _rng(lp1, xlab, "lc_x_phi", *PROFILE["phi_range"])
                if _phi_profile
                else _rng(lp1, xlab, "lc_x")
            )
            lc_yr = _rng(lp2, "I", "lc_i")
            st.caption("Profile curve style (applied to all cuts)")
            lc_style = _curve_style_controls(f"{STATE_PREFIX}_lc_style", defaults={"width": 2.0})

        import plotly.express as px

        # Auto colour cycle unless the user picked a specific colour.
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
        frames = []
        for name, xa, ya in cut_curves:
            frames.append(pd.DataFrame({xlab: xa, f"I[{name}]": ya}))
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
        work[
            [
                "stem",
                "th",
                "well",
                "timestamp",
                "has_raw",
                "has_qc",
                "has_qimg",
                "has_qphi",
                "has_cir",
            ]
        ],
        width="stretch",
        hide_index=True,
    )
