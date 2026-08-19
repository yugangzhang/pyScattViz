"""Build export-ready overlays from selected circular-average files."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from pyscattviz.app.components.datasource import (
    apply_term_filters,
    render_folder_picker,
    render_term_filters,
)
from pyscattviz.app.components.saving import render_save_panel
from pyscattviz.app.components.scattering import (
    discover_scattering_products,
    index_frames,
    load_cir,
)
from pyscattviz.dataio import DataReadError
from pyscattviz.filters import FilterSyntaxError
from pyscattviz.plotting import fig_to_bytes
from pyscattviz.publication import Curve, build_curve_figure

TAB_NAME = "Publication Plot"

st.set_page_config(page_title="Publication Plot", page_icon="📈", layout="wide")
st.title("📈 Publication Plot")
st.caption("Overlay selected circular averages and export PNG, SVG, or PDF.")

path_input = render_folder_picker(
    "pyscattviz_publication",
    "Result folder",
    help_text="A folder holding cir_avg, for example .../Results/giwaxs.",
)
if not path_input:
    st.info("Choose or paste a scattering result folder to start.")
    st.stop()

analysis_root, products, _focused = discover_scattering_products(path_input)
if "cir_avg" not in {product["key"] for product in products}:
    st.error("No cir_avg folder was found at this result path.")
    st.stop()
st.session_state["pyscattviz_active_root"] = analysis_root

saved_stems = st.session_state.get("pyscattviz_selected_stems", ())
saved_root = st.session_state.get("pyscattviz_selected_root")
saved_available = bool(saved_stems and saved_root == analysis_root)

c1, c2, c3 = st.columns([2, 1, 1])
use_saved = c2.checkbox(
    f"Saved selection ({len(saved_stems):,})",
    value=saved_available,
    disabled=not saved_available,
)
query = c1.text_input(
    "Boolean filename filter",
    placeholder="sample_A AND (0.10deg OR 0.15deg)",
    disabled=use_saved,
)
max_frames = c3.number_input("Maximum names", 1, 5_000, 500, 100, disabled=use_saved)

st.caption("Narrow the curve list")
kw_and, kw_or, kw_not = render_term_filters(
    "pyscattviz_publication",
    help_and="Every term must appear in the curve name.",
    help_or="At least one term must appear — this is how you overlay two samples.",
    help_not="Drop matching curves, for example the calibration scans.",
)

try:
    table = index_frames(
        analysis_root,
        product_keys=("cir_avg",),
        query="" if use_saved else query,
        filename_list=tuple(saved_stems) if use_saved else (),
        max_frames=len(saved_stems) if use_saved else int(max_frames),
    )
except FilterSyntaxError as exc:
    st.error(f"Filter error: {exc}")
    st.stop()

available = apply_term_filters(table[table["has_cir"]], kw_and, kw_or, kw_not)
if available.empty:
    st.warning("No circular-average files match this selection.")
    st.stop()

st.caption(f"{len(available):,} matching curves; filename scanning does not open CSV contents.")
options = available["stem"].tolist()
selected = st.multiselect(
    "Curves to plot (maximum 50)",
    options,
    default=options[: min(5, len(options))],
)
if not selected:
    st.info("Select at least one curve.")
    st.stop()
if len(selected) > 50:
    st.error("Select no more than 50 curves for one publication figure.")
    st.stop()

st.subheader("Figure controls")
f1, f2, f3, f4 = st.columns(4)
theme = f1.selectbox("Theme", ["science", "notebook", "present", "poster"])
normalization = f2.selectbox("Normalization", ["none", "maximum", "integral"])
logx = f3.checkbox("Log q", value=True)
logy = f4.checkbox("Log intensity", value=True)

r1, r2, r3, r4 = st.columns(4)
q_min = r1.number_input("q minimum (blank = auto)", value=None, format="%.5g")
q_max = r2.number_input("q maximum (blank = auto)", value=None, format="%.5g")
offset = r3.number_input("Vertical offset", value=0.0, format="%.5g")
legend = r4.checkbox("Show legend", value=True)

s1, s2, s3 = st.columns([2, 1, 1])
title = s1.text_input("Title", value="")
figure_width = s2.number_input("Width (in)", 3.0, 20.0, 7.0, 0.5)
figure_height = s3.number_input("Height (in)", 3.0, 20.0, 5.0, 0.5)

rows = available.set_index("stem")
curves = []
unreadable = []
for stem in selected:
    try:
        q, intensity = load_cir(rows.loc[stem, "cir"])
    except DataReadError as exc:
        unreadable.append(str(exc))
        continue
    curves.append(Curve(stem, q, intensity))
for message in unreadable:
    st.warning(message)
if not curves:
    st.error("None of the selected circular averages could be read.")
    st.stop()

try:
    figure = build_curve_figure(
        curves,
        theme=theme,
        normalization=normalization,
        q_min=q_min,
        q_max=q_max,
        offset=float(offset),
        logx=logx,
        logy=logy,
        title=title,
        ylabel="Normalized I(q)" if normalization != "none" else "I(q)",
        figsize=(float(figure_width), float(figure_height)),
        legend=legend,
    )
except ValueError as exc:
    st.error(str(exc))
    st.stop()

st.pyplot(figure, width="content")

e1, e2, e3 = st.columns([1, 1, 2])
export_format = e1.selectbox("Export format", ["png", "svg", "pdf"])
dpi = e2.number_input("DPI", 72, 1200, 300, 50, disabled=export_format != "png")
mime = {"png": "image/png", "svg": "image/svg+xml", "pdf": "application/pdf"}
with e3:
    st.write("")
    st.write("")
    st.download_button(
        "Download publication figure",
        fig_to_bytes(figure, format=export_format, dpi=int(dpi)),
        file_name=f"pyscattviz_curves.{export_format}",
        mime=mime[export_format],
        type="primary",
    )

curve_frames = [
    pd.DataFrame({f"q[{curve.name}]": curve.q, f"I[{curve.name}]": curve.intensity})
    for curve in curves
]
curve_table = pd.concat(curve_frames, axis=1) if curve_frames else None

render_save_panel(
    TAB_NAME,
    f"curves_{len(selected)}_{theme}",
    key="publication_save",
    figure=figure,
    figure_kind="matplotlib",
    table=curve_table,
    text="\n".join(selected),
    expanded=True,
    caption=(
        "Written under the Publication_Plot subfolder of the output root. Use the "
        "optional subfolder box to keep one manuscript figure's versions together."
    ),
)

plt.close(figure)
