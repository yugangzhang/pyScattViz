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
import re
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pyscattviz.app.components.batch import render_batch_export
from pyscattviz.app.components.saving import render_output_settings, render_save_panel

# Shared scattering engine (aliased to the underscore names used below).
from pyscattviz.app.components.scattering import (
    CMAPS,
    heatmap_fig,
    index_frames,
    load_cir,
    load_qphi,
    load_raw,
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
RAW_SUBDIR_CHOICES = PROFILE["raw_choices"]
RAW_SUBDIR = RAW_SUBDIR_CHOICES[0]


# ===========================================================================
st.set_page_config(
    page_title=f"{PROFILE['short']} Explorer",
    page_icon=PROFILE["icon"],
    layout="wide",
)

st.title(f"{PROFILE['icon']} {PROFILE['name']} Explorer")
st.caption(PROFILE["description"])

with st.sidebar:
    st.header(f"📁 {PROFILE['short']} analysis folder")

    # Folders collected on Data Selection are the fastest way to move between
    # samples without retyping a long mounted path.
    basket_folders = [
        item
        for item in st.session_state.get("pyscattviz_dataset_paths", [])
        if Path(item).expanduser().is_dir()
    ]
    if basket_folders:
        picked = st.selectbox(
            f"Folder from the dataset basket ({len(basket_folders)})",
            ["— type a path below —", *basket_folders],
            format_func=lambda item: (
                "/".join(Path(item).parts[-2:]) if item in basket_folders else item
            ),
            key=f"{STATE_PREFIX}_basket_pick",
        )
        if picked in basket_folders and picked != st.session_state.get("pyscattviz_active_root"):
            st.session_state["pyscattviz_active_root"] = picked
            st.rerun()

    analysis = st.text_input(
        f"Data path ({PROFILE['folder']}/analysis or one product folder)",
        value=st.session_state.get("pyscattviz_active_root", ""),
    )
    analysis_available = bool(analysis and Path(analysis).expanduser().is_dir())
    if analysis_available:
        st.session_state["pyscattviz_active_root"] = analysis
    elif analysis:
        st.session_state.pop("pyscattviz_active_root", None)

    pending_remote = str(st.session_state.get("pyscattviz_file_root", ""))
    if not analysis_available:
        if pending_remote.startswith("/nsls2/"):
            st.warning(
                "The selected `/nsls2` folder is not mounted. Open Data Sources & "
                "Mounts, complete the SFTP mount, and register its local path before "
                "opening this viewer."
            )
        elif analysis:
            st.warning(
                "This data path is not available on this computer. Choose an existing "
                "local or mounted folder."
            )
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
        placeholder="sample AND (10s OR 30s) NOT AgBH",
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

    hide_cal = st.checkbox("Hide calibration", value=True)
    kw = st.text_input(
        "Filter by keyword(s), comma-sep", value="", help="AND filter on the filename stem."
    )

    st.divider()
    st.subheader("💾 Saving")
    render_output_settings(st)

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
st.markdown(f"**{sel['stem']}**  ·  well `{sel['well']}`  ·  t = {ts}")

# --- Display controls -------------------------------------------------------
dc1, dc2, dc3, dc4 = st.columns(4)
logI = dc1.checkbox("log I (2D panels)", value=True)
logq = dc2.checkbox("log q (1D)", value=PROFILE["logq"])
logiq = dc3.checkbox("log I (1D)", value=True)
cmap = dc4.selectbox("2D colormap", CMAPS, index=0)  # default Turbo

dc5, _ = st.columns(2)
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


with st.expander("🎛️ Ranges & colour scaling (blank = auto)", expanded=False):
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
    c_qr = _rng(
        cp,
        "q",
        "c_q",
        lo_val=PROFILE["q_range"][0],
        hi_val=PROFILE["q_range"][1],
    )
    c_phir = _rng(cp, "φ", "c_phi", lo_val=0.0, hi_val=180.0)  # default φ [0,180]
    dp.markdown("**D · I(q)**")
    d_qr = _rng(
        dp,
        "q",
        "d_q",
        lo_val=PROFILE["q_range"][0],
        hi_val=PROFILE["q_range"][1],
    )
    d_ir = _rng(dp, "I", "d_i")
    st.caption("D curve style")
    d_style = _curve_style_controls(
        f"{STATE_PREFIX}_d_style", defaults={"color": "Crimson", "width": 2.2}
    )


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
        "Direction", ["q-cut  (I vs φ, fixed q band)", "φ-cut  (I vs q, fixed φ band)"], index=0
    )
    _is_qcut = cut_dir.startswith("q-cut")
    centers_lab = "q center(s)" if _is_qcut else "φ center(s)"
    width_lab = "q width" if _is_qcut else "φ width"
    def_centers, def_width = (
        (PROFILE["q_cut_center"], PROFILE["q_cut_width"]) if _is_qcut else ("0", 10.0)
    )

    centers_txt = lc3.text_input(
        centers_lab, value=def_centers, help="Comma / space separated; one profile per center."
    )
    width = lc4.number_input(
        width_lab, value=float(def_width), min_value=0.0, step=0.01, format="%.3f"
    )
    centers = _parse_centers(centers_txt)
else:
    st.info("Select the q–φ product above to enable line-cuts.")

cut_curves = []  # list of (name, xarr, yarr)
qphi_shapes = []
_band_color = "rgba(255,0,0,0.15)"
_line_color = "crimson"

if centers and "qphi" in active_products and sel["has_qphi"]:
    q, phi, qphi, pmask = load_qphi(sel["qphi"])
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

rowA = st.columns(2)
rowB = st.columns(2)

# A) raw image ---------------------------------------------------------------
with rowA[0]:
    if "stitched" not in active_products:
        pass
    elif sel["has_raw"]:
        raw = load_raw(sel["raw"])
        z = raw.astype(float).copy()
        z[~np.isfinite(z)] = np.nan
        z[z <= 0] = np.nan
        z = np.flipud(z)  # right-side-up, lower-left origin
        ny0, nx0 = z.shape
        px_x, px_y = np.arange(nx0), np.arange(ny0)
        z, px_x, px_y = _downsample(z, px_x, px_y)
        fig = _heatmap_fig(
            "A · raw",
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
        st.plotly_chart(fig, width="stretch")
        rendered_figures["A · raw"] = fig
        rendered_arrays["A · raw"] = {"image": z}
    elif "stitched" in active_products:
        st.info("No raw image for this frame.")

# B) q-image (reserved — no remesh for transmission data yet) ----------------
with rowA[1]:
    if "q_image" not in active_products:
        pass
    elif sel["has_qimg"]:
        from pyscattviz.app.components.scattering import load_qimg, resolve_qimage

        data = load_qimg(sel["qimg"])
        qimg, qx, qz, qmask, b_xlab = resolve_qimage(data, "qx")
        z = _apply_mask(qimg, qmask)
        z, xx, yy = _downsample(z, qx, qz)
        fig = _heatmap_fig(
            "B · q-image",
            z,
            xx,
            yy,
            b_xlab,
            "qz (Å⁻¹)",
            vmin_I=None,
            vmax_I=None,
            aspect=_aspect_arg(),
        )
        st.plotly_chart(fig, width="stretch")
        rendered_figures["B · q-image"] = fig
        rendered_arrays["B · q-image"] = {
            "qimg": z,
            "qx": np.asarray(xx),
            "qz": np.asarray(yy),
        }
    elif "q_image" in active_products:
        st.info(
            "🔧 **q-image** — no qx–qz remesh exists for this transmission "
            "dataset yet. This panel is reserved: it will render "
            "automatically once `q_image/qimg_*.npz` files are produced."
        )

# C) q–φ map -----------------------------------------------------------------
with rowB[0]:
    if "qphi" not in active_products:
        pass
    elif sel["has_qphi"]:
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
        st.plotly_chart(fig, width="stretch")
        rendered_figures["C · q–φ map"] = fig
        rendered_arrays["C · q–φ map"] = {
            "qphi": z,
            "q": np.asarray(q),
            "phi": np.asarray(phi),
        }
    elif "qphi" in active_products:
        st.info("No qphi map for this frame.")

# D) I(q) circular average ---------------------------------------------------
with rowB[1]:
    if "cir_avg" not in active_products:
        pass
    elif sel["has_cir"]:
        qq, ii = load_cir(sel["cir"])
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
            title="D · I(q)",
            height=_PANEL_H,
            template="plotly_white",
            margin=dict(l=60, r=15, t=40, b=45),
        )
        st.plotly_chart(fig, width="stretch")
        rendered_figures["D · I(q)"] = fig
        rendered_tables["D · I(q)"] = pd.DataFrame({"q": qq, "I": ii})
    elif "cir_avg" in active_products:
        st.info("No circular average for this frame.")

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
    render_batch_export(
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
    )

if "qc" in active_products:
    st.subheader("QC image")
    qc_cols = st.columns(2)
    with qc_cols[0]:
        if sel["has_qc"]:
            st.image(sel["qc"], caption="QC image", width="stretch")
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
        _x_is_phi = xlab.startswith("φ")

        with st.expander("🎛️ Line-cut plot: limits & style", expanded=True):
            lp1, lp2 = st.columns(2)
            lc_xr = _rng(
                lp1,
                xlab,
                "tsaxs_lc_x",
                lo_val=0.0 if _x_is_phi else None,
                hi_val=180.0 if _x_is_phi else None,
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
        st.plotly_chart(fig, width="stretch")

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
