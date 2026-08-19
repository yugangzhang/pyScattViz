"""Build export-ready overlays from selected circular-average files."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from pyscattviz.app.components.codeview import render_code_export
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
from pyscattviz.app.state import coerce_choices, keep_widget_state
from pyscattviz.codegen import publication_code
from pyscattviz.dataio import DataReadError
from pyscattviz.filters import FilterSyntaxError
from pyscattviz.plotting import fig_to_bytes
from pyscattviz.publication import (
    LEGEND_LOCATIONS,
    LINE_STYLES,
    MARKERS,
    TICK_DIRECTIONS,
    Curve,
    CurveStyle,
    build_curve_figure,
)

TAB_NAME = "Publication Plot"

st.set_page_config(page_title="Publication Plot", page_icon="📈", layout="wide")

# Streamlit forgets a page's widgets as soon as another page is opened. Keep them.
keep_widget_state(st.session_state)
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
    key="pub_use_saved",
)
query = c1.text_input(
    "Boolean filename filter",
    placeholder="sample_A AND (0.10deg OR 0.15deg)",
    disabled=use_saved,
    key="pub_query",
)
max_frames = c3.number_input(
    "Maximum names", 1, 5_000, 500, 100, disabled=use_saved, key="pub_max_names"
)

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
coerce_choices(st.session_state, "pyscattviz_publication_curves", options)
selected = st.multiselect(
    "Curves to plot (maximum 50)",
    options,
    key="pyscattviz_publication_curves",
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
theme = f1.selectbox("Theme", ["science", "notebook", "present", "poster"], key="pub_theme")
normalization = f2.selectbox(
    "Normalization", ["none", "maximum", "integral"], key="pub_normalization"
)
logx = f3.checkbox("Log q", value=True, key="pub_logx")
logy = f4.checkbox("Log intensity", value=True, key="pub_logy")

r1, r2, r3, r4 = st.columns(4)
q_min = r1.number_input("q minimum (blank = auto)", value=None, format="%.5g", key="pub_qmin")
q_max = r2.number_input("q maximum (blank = auto)", value=None, format="%.5g", key="pub_qmax")
offset = r3.number_input("Vertical offset", value=0.0, format="%.5g", key="pub_offset")
legend = r4.checkbox("Show legend", value=True, key="pub_legend")

s1, s2, s3 = st.columns([2, 1, 1])
title = s1.text_input("Title", value="", key="pub_title")
figure_width = s2.number_input("Width (in)", 3.0, 20.0, 7.0, 0.5, key="pub_width")
figure_height = s3.number_input("Height (in)", 3.0, 20.0, 5.0, 0.5, key="pub_height")

with st.expander("📐 Axes, ticks, and legend", expanded=False):
    a1, a2, a3, a4 = st.columns(4)
    x_low = a1.number_input("x min (blank = auto)", value=None, format="%.5g", key="pub_xlim_lo")
    x_high = a2.number_input("x max (blank = auto)", value=None, format="%.5g", key="pub_xlim_hi")
    y_low = a3.number_input("y min (blank = auto)", value=None, format="%.5g", key="pub_ylim_lo")
    y_high = a4.number_input("y max (blank = auto)", value=None, format="%.5g", key="pub_ylim_hi")

    b1, b2, b3, b4 = st.columns(4)
    xlabel = b1.text_input("x label", value=r"q ($\AA^{-1}$)", key="pub_xlabel")
    ylabel_override = b2.text_input("y label (blank = automatic)", value="", key="pub_ylabel")
    multiplier = b3.number_input(
        "Multiply curve n by",
        value=1.0,
        min_value=0.0001,
        format="%.5g",
        key="pub_multiplier",
        help="A factor of 2 stacks curves as 1, 2, 4, 8 … on a log axis.",
    )
    font_size = b4.number_input("Base font size", 5.0, 30.0, 10.0, 0.5, key="pub_font_size")

    c1_, c2_, c3_, c4_ = st.columns(4)
    grid = c1_.checkbox("Grid", value=False, key="pub_grid")
    minor_grid = c2_.checkbox("Minor grid", value=False, key="pub_minor_grid")
    minor_ticks = c3_.checkbox("Minor ticks", value=True, key="pub_minor_ticks")
    grid_alpha = c4_.slider("Grid opacity", 0.05, 1.0, 0.3, 0.05, key="pub_grid_alpha")

    d1, d2, d3, d4 = st.columns(4)
    tick_direction = d1.selectbox("Tick direction", TICK_DIRECTIONS, key="pub_tick_direction")
    tick_length = d2.number_input("Tick length", 0.0, 20.0, 4.0, 0.5, key="pub_tick_length")
    tick_width = d3.number_input("Tick width", 0.1, 5.0, 1.0, 0.1, key="pub_tick_width")
    spine_width = d4.number_input("Frame width", 0.1, 5.0, 1.0, 0.1, key="pub_spine_width")

    e1_, e2_, e3_, e4_ = st.columns(4)
    tick_top = e1_.checkbox("Ticks on top", value=True, key="pub_tick_top")
    tick_right = e2_.checkbox("Ticks on right", value=True, key="pub_tick_right")
    legend_frame = e3_.checkbox("Legend box", value=True, key="pub_legend_frame")
    legend_columns = e4_.number_input("Legend columns", 1, 6, 1, 1, key="pub_legend_cols")

    f1_, f2_ = st.columns(2)
    legend_location = f1_.selectbox("Legend position", LEGEND_LOCATIONS, key="pub_legend_loc")
    legend_font_size = f2_.number_input(
        "Legend font size", 4.0, 24.0, 9.0, 0.5, key="pub_legend_font"
    )

with st.expander("🎨 Per-curve style", expanded=False):
    st.caption(
        "One row per curve, in plotting order. Leave the colour blank to follow "
        "the theme's own cycle."
    )
    style_table = pd.DataFrame(
        {
            "curve": selected,
            "label": ["" for _ in selected],
            "color": ["" for _ in selected],
            "line": ["solid" for _ in selected],
            "width": [1.6 for _ in selected],
            "marker": ["none" for _ in selected],
            "marker size": [5.0 for _ in selected],
            "every nth marker": [1 for _ in selected],
            "opacity": [1.0 for _ in selected],
        }
    )
    edited_styles = st.data_editor(
        style_table,
        width="stretch",
        hide_index=True,
        disabled=["curve"],
        column_config={
            "line": st.column_config.SelectboxColumn(options=list(LINE_STYLES)),
            "marker": st.column_config.SelectboxColumn(options=list(MARKERS)),
            "color": st.column_config.TextColumn(help="A matplotlib colour: crimson, #1f77b4, C0"),
            "width": st.column_config.NumberColumn(min_value=0.1, max_value=10.0, step=0.1),
            "marker size": st.column_config.NumberColumn(min_value=0.0, max_value=30.0, step=0.5),
            "every nth marker": st.column_config.NumberColumn(min_value=1, max_value=500, step=1),
            "opacity": st.column_config.NumberColumn(min_value=0.05, max_value=1.0, step=0.05),
        },
        key="pub_curve_styles",
    )

curve_styles = [
    CurveStyle(
        color=(str(row["color"]).strip() or None),
        linestyle=LINE_STYLES.get(str(row["line"]), "-"),
        linewidth=float(row["width"]),
        marker=MARKERS.get(str(row["marker"])),
        markersize=float(row["marker size"]),
        markevery=int(row["every nth marker"]),
        alpha=float(row["opacity"]),
        label=(str(row["label"]).strip() or None),
    )
    for _index, row in edited_styles.iterrows()
]

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
        xlabel=xlabel,
        ylabel=ylabel_override or ("Normalized I(q)" if normalization != "none" else "I(q)"),
        figsize=(float(figure_width), float(figure_height)),
        legend=legend,
        styles=curve_styles,
        multiplier=float(multiplier),
        xlim=(x_low, x_high),
        ylim=(y_low, y_high),
        grid=grid,
        minor_grid=minor_grid,
        grid_alpha=float(grid_alpha),
        minor_ticks=minor_ticks,
        tick_direction=tick_direction,
        tick_top=tick_top,
        tick_right=tick_right,
        tick_length=float(tick_length),
        tick_width=float(tick_width),
        spine_width=float(spine_width),
        font_size=float(font_size),
        legend_location=legend_location,
        legend_columns=int(legend_columns),
        legend_font_size=float(legend_font_size),
    )
except ValueError as exc:
    st.error(str(exc))
    st.stop()

st.pyplot(figure, width="content")

e1, e2, e3 = st.columns([1, 1, 2])
export_format = e1.selectbox("Export format", ["png", "svg", "pdf"], key="pub_export_format")
dpi = e2.number_input("DPI", 72, 1200, 300, 50, disabled=export_format != "png", key="pub_dpi")
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

render_code_export(
    publication_code(
        [rows.loc[stem, "cir"] for stem in selected if stem in rows.index],
        theme=theme,
        normalization=normalization,
        q_min=q_min,
        q_max=q_max,
        offset=float(offset),
        log_x=logx,
        log_y=logy,
        title=title,
        figsize=(float(figure_width), float(figure_height)),
        legend=legend,
    ),
    key="publication_code",
    tab_name=TAB_NAME,
    filename=f"publication_{len(selected)}_curves",
)
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
