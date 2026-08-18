"""GIWAXS / GISAXS Explorer — selectable reduction panels per frame.

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
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Shared scattering engine — indexing, loaders, array/plot helpers, styling.
# Some are aliased to the underscore names this page's body already uses.
from pyscattviz.app.components.scattering import (
    CMAPS,
    heatmap_fig,
    index_frames,
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
from pyscattviz.filters import FilterSyntaxError

# ===========================================================================
st.set_page_config(page_title="GIWAXS Explorer", page_icon="🧭", layout="wide")

st.title("🧭 GISAXS / GIWAXS Explorer")
st.caption(
    "Choose the reduction products to display — raw, QC, q-image, "
    "q–φ, or circular-average — with q-image / q–φ line-cuts."
)

with st.sidebar:
    st.header("📁 GISAXS / GIWAXS data")
    analysis = st.text_input(
        "Data path (gisaxs/giwaxs/ or one product folder)",
        value=st.session_state.get("pyscattviz_active_root", ""),
    )
    if analysis:
        st.session_state["pyscattviz_active_root"] = analysis

    analysis_root, products, selected_products = scattering_product_selector(
        "giwaxs_products", analysis
    )
    saved_stems = st.session_state.get("pyscattviz_selected_stems", ())
    saved_root = st.session_state.get("pyscattviz_selected_root")
    saved_available = bool(saved_stems and saved_root == analysis_root)
    use_saved = st.checkbox(
        f"Use saved File Selection ({len(saved_stems):,} frames)",
        value=saved_available,
        disabled=not saved_available,
    )
    query = st.text_input(
        "Boolean filename filter",
        value="",
        placeholder="Kim AND 0.1000deg NOT AgBH",
        disabled=use_saved,
    )
    max_frames = st.number_input("Maximum frames", 1, 50_000, 5_000, 500, disabled=use_saved)
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

    hide_cal = st.checkbox("Hide calibration", value=True)
    kw = st.text_input(
        "Filter by keyword(s), comma-sep", value="", help="AND filter on the filename stem."
    )

work = df.copy()
if hide_cal:
    work = work[~work["is_calibration"]]
if kw.strip():
    for tok in [k.strip() for k in kw.split(",") if k.strip()]:
        work = work[work["stem"].str.contains(re.escape(tok))]
work = work.reset_index(drop=True)
if work.empty:
    st.warning("Nothing matches the filter.")
    st.stop()

# --- Frame picker -----------------------------------------------------------
active_products = set(selected_products)
c1, c2 = st.columns([4, 1])
labels = work["stem"].tolist()
chosen = c1.selectbox("Frame", options=labels, index=0) if len(labels) > 1 else labels[0]
idx = labels.index(chosen)
sel = work.iloc[int(idx)]
c2.metric("Frame", f"{int(idx) + 1}/{len(labels)}")

ts = sel["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if pd.notna(sel["timestamp"]) else "—"
th = f"{sel['th']:.3f}°" if pd.notna(sel["th"]) else "—"
st.markdown(f"**{sel['stem']}**  ·  θ = {th}  ·  well `{sel['well']}`  ·  t = {ts}")

# --- Display controls -------------------------------------------------------
dc1, dc2, dc3, dc4 = st.columns(4)
logI = dc1.checkbox("log I (2D panels)", value=True)
logq = dc2.checkbox("log q (1D)", value=False)
logiq = dc3.checkbox("log I (1D)", value=True)
cmap = dc4.selectbox("2D colormap", CMAPS, index=0)  # default Turbo (item 4)

# Second row: aspect ratio (shared by A & B, item 2) + B-panel axis mode (item 3)
dc5, dc6 = st.columns(2)
aspect_mode = dc5.selectbox(
    "Aspect ratio (A & B)",
    ["Auto", "Equal (1:1)", "Custom"],
    index=1,
    help="Equal locks y/x to 1:1 in data units; Custom sets the y:x ratio.",
)
aspect_ratio = 1.0
if aspect_mode == "Custom":
    aspect_ratio = dc5.number_input(
        "y:x ratio", value=1.0, min_value=0.05, max_value=20.0, step=0.1, format="%.2f"
    )
# Does the current frame's q_image expose a qr–qz representation?
_qimg_data = load_qimg(sel["qimg"]) if "q_image" in active_products and sel["has_qimg"] else None
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
)
b_mode = "qr" if b_axis_mode.startswith("qr") else "qx"
if b_mode == "qr" and not _has_qr:
    dc6.caption("⚠️ No qr key in this npz yet — showing qx–qz.")

_PANEL_H = 380


def _rng(col, label, key, lo_val=None, hi_val=None, fmt="%.4g"):
    """Two side-by-side optional number inputs → (min, max); None means auto."""
    a, b = col.columns(2)
    lo = a.number_input(f"{label} min", value=lo_val, key=f"{key}_lo", format=fmt)
    hi = b.number_input(f"{label} max", value=hi_val, key=f"{key}_hi", format=fmt)
    return lo, hi


with st.expander("🎛️ Ranges & colour scaling (blank = auto)", expanded=False):
    st.caption(
        "Colour limits are in **intensity** units (pre-log). "
        "Auto colour uses robust percentiles of each panel."
    )
    ap, bp, cp = st.columns(3)
    ap.markdown("**A · raw**")
    a_vmin, a_vmax = _rng(ap, "I", "a_v")
    a_xr = _rng(ap, "x (px)", "a_x")  # pixel x limits (item 1)
    a_yr = _rng(ap, "y (px)", "a_y")  # pixel y limits (item 1)
    bp.markdown("**B · q-image**")
    b_vmin, b_vmax = _rng(bp, "I", "b_v")
    _bx_lab = "qr" if b_mode == "qr" else "qx"
    b_qxr = _rng(bp, _bx_lab, "b_qx")
    b_qzr = _rng(bp, "qz", "b_qz", lo_val=0.0, hi_val=3.0)  # default qz [0,3] (item 4)
    cp.markdown("**C · q–φ**")
    c_vmin, c_vmax = _rng(cp, "I", "c_v")
    c_qr = _rng(cp, "q", "c_q")
    c_phir = _rng(cp, "φ", "c_phi", lo_val=0.0, hi_val=180.0)  # default φ [0,180] (item 4)
    st.markdown("**D · circular average**")
    dp1, dp2 = st.columns(2)
    d_qr = _rng(dp1, "q", "d_q")
    d_ir = _rng(dp2, "I", "d_i")
    st.caption("D curve style")
    d_style = _curve_style_controls("d_style", defaults={"color": "Crimson", "width": 2.2})


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
    cut_source = lc1.selectbox("Cut on", cut_options, index=1 if len(cut_options) > 1 else 0)

    if cut_source.startswith("q_image"):
        cut_dir = lc2.selectbox(
            "Direction",
            [f"{_bx}-cut  (I vs {_bx}, fixed qz band)", f"qz-cut  (I vs qz, fixed {_bx} band)"],
            index=0,
        )
        _is_qr = cut_dir.startswith(_bx)
        centers_lab = "qz center(s)" if _is_qr else f"{_bx} center(s)"
        width_lab = "qz width" if _is_qr else f"{_bx} width"
        def_centers, def_width = ("0.0", 0.05)
    else:
        cut_dir = lc2.selectbox(
            "Direction", ["q-cut  (I vs φ, fixed q band)", "φ-cut  (I vs q, fixed φ band)"], index=0
        )
        _is_qcut = cut_dir.startswith("q-cut")
        centers_lab = "q center(s)" if _is_qcut else "φ center(s)"
        width_lab = "q width" if _is_qcut else "φ width"
        def_centers, def_width = ("1.0", 0.05) if _is_qcut else ("0", 10.0)

    centers_txt = lc3.text_input(
        centers_lab, value=def_centers, help="Comma / space separated; one profile per center."
    )
    width = lc4.number_input(
        width_lab, value=float(def_width), min_value=0.0, step=0.01, format="%.3f"
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
    if cut_source.startswith("q_image") and sel["has_qimg"]:
        qimg, qx, qz, qmask, _ = resolve_qimage(_qimg_data, b_mode)
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
        q, phi, qphi, pmask = load_qphi(sel["qphi"])
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


def _render_image(path, title, *, flip=False):
    if not path:
        st.info(f"No {title.lower()} for this frame.")
        return
    raw = load_raw(path)
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
        if sel["has_qimg"] and _qimg_data is not None:
            qimg, qx, qz, qmask, b_xlab = resolve_qimage(_qimg_data, b_mode)
            z = _apply_mask(qimg, qmask)
            z, xx, yy = _downsample(z, qx, qz)
            fig = _heatmap_fig(
                "B · q-image",
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
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No q-image for this frame.")
    elif panel == "qphi":
        if sel["has_qphi"]:
            q, phi, qphi, pmask = load_qphi(sel["qphi"])
            pmask = pmask if getattr(pmask, "shape", None) == getattr(qphi, "shape", None) else None
            z = _apply_mask(qphi, pmask)
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
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No q–φ map for this frame.")
    elif panel == "cir_avg":
        if sel["has_cir"]:
            qq, ii = load_cir(sel["cir"])
            tk = _apply_curve_style(
                dict(
                    x=qq, y=ii, name="I(q)", hovertemplate="q=%{x:.4f}<br>I=%{y:.3g}<extra></extra>"
                ),
                d_style,
                base_color="crimson",
            )
            fig = go.Figure(go.Scatter(**tk))
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
        else:
            st.info("No circular average for this frame.")


panel_order = [p for p in ("stitched", "qc", "q_image", "qphi", "cir_avg") if p in active_products]
for start in range(0, len(panel_order), 2):
    row = st.columns(2)
    for col, panel in zip(row, panel_order[start : start + 2]):
        with col:
            _render_panel(panel)

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

        # Styling + axis limits for the line-cut profiles (items 4-6).
        # When the profile runs along φ (q-cut on q–φ), default x to [0,180].
        _x_is_phi = xlab.startswith("φ")
        with st.expander("🎛️ Line-cut plot: limits & style", expanded=True):
            lp1, lp2 = st.columns(2)
            lc_xr = _rng(
                lp1,
                xlab,
                "lc_x",
                lo_val=0.0 if _x_is_phi else None,
                hi_val=180.0 if _x_is_phi else None,
            )
            lc_yr = _rng(lp2, "I", "lc_i")
            st.caption("Profile curve style (applied to all cuts)")
            lc_style = _curve_style_controls("lc_style", defaults={"width": 2.0})

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
        use_container_width=True,
        hide_index=True,
    )
