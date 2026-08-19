"""Plot any list of data files — no reduction layout required.

Collaborators send me a list of full paths far more often than a tidy
``Results/giwaxs`` tree: a handful of circular averages, a two-column ``.dat``
from a laboratory instrument, an ``.npz`` a student wrote, a detector ``.tif``.
This page takes that list, whether it comes from the dataset basket, from a
folder with a filter, or from paste, and plots it as 1D curves, a stacked
intensity map, or 2D images. Everything drawn here can be written straight to a
folder on the local disk.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pyscattviz.app.components.files import (
    cached_arrays,
    cached_curve,
    cached_image,
    collect_files,
    file_signature,
)
from pyscattviz.app.components.saving import render_output_settings, render_save_panel
from pyscattviz.app.components.scattering import CMAPS, color_limits, downsample, log_scale
from pyscattviz.data_sources import load_path_mappings
from pyscattviz.dataio import (
    ARRAY_SUFFIXES,
    CURVE_SUFFIXES,
    IMAGE_SUFFIXES,
    DataReadError,
    common_prefix_suffix,
    integrate_curve,
    short_label,
    stack_curves,
)
from pyscattviz.datasets import normalize_paths
from pyscattviz.discovery import parse_terms
from pyscattviz.publication import Curve, build_curve_figure

TAB_NAME = "Quick Plot"
BASKET_KEY = "pyscattviz_dataset_paths"

st.set_page_config(page_title="Quick Plot", page_icon="⚡", layout="wide")
st.title("⚡ Quick Plot")
st.caption(
    "Give it full paths — files or folders — and it plots them. Nothing is opened "
    "until a file is actually selected below."
)

st.session_state.setdefault("pyscattviz_path_mappings", load_path_mappings())
st.session_state.setdefault(BASKET_KEY, [])
mappings = st.session_state["pyscattviz_path_mappings"]

with st.sidebar:
    st.header("📁 Files to plot")
    basket = list(st.session_state.get(BASKET_KEY, []))
    source_options = ["Dataset basket", "One folder", "Paste full paths"]
    default_index = 0 if basket else 1
    source = st.radio(
        "Where the paths come from",
        source_options,
        index=default_index,
        key="quickplot_source",
    )

    if source == "Dataset basket":
        st.caption(f"{len(basket):,} path(s) in the basket. Build it on Data Selection.")
        raw_paths = basket
    elif source == "One folder":
        folder = st.text_input(
            "Folder",
            value=str(st.session_state.get("pyscattviz_active_root", "")),
            key="quickplot_folder",
        )
        raw_paths = [folder] if folder.strip() else []
    else:
        pasted = st.text_area(
            "Full paths (one per line)",
            height=140,
            key="quickplot_pasted",
        )
        raw_paths = pasted.splitlines()

    st.divider()
    st.subheader("Narrow the list")
    and_text = st.text_input("Must contain (AND)", key="quickplot_and")
    or_text = st.text_input("May contain (OR)", key="quickplot_or")
    no_text = st.text_input("Must not contain (EXCLUDE)", value="", key="quickplot_not")
    depth = st.number_input("Folder depth", 1, 8, 3, 1, key="quickplot_depth")
    max_files = st.number_input("Maximum files", 1, 20_000, 500, 50, key="quickplot_max")
    if st.button("🔄 Re-read files from disk"):
        cached_curve.clear()
        cached_image.clear()
        cached_arrays.clear()

    st.divider()
    st.subheader("Saving")
    render_output_settings(st)

resolved = normalize_paths(raw_paths, mappings)
if not resolved:
    st.info(
        "No paths yet. Build a basket on **Data Selection**, type one folder in the "
        "sidebar, or paste a list of full paths."
    )
    st.stop()

files, truncated = collect_files(
    resolved,
    and_list=parse_terms(and_text),
    or_list=parse_terms(or_text),
    no_list=parse_terms(no_text),
    max_depth=int(depth),
    max_files=int(max_files),
)
if not files:
    st.warning(
        "None of those paths contain files pyScattViz can open. Supported "
        f"extensions: {', '.join((*CURVE_SUFFIXES, *ARRAY_SUFFIXES, *IMAGE_SUFFIXES))}."
    )
    st.stop()
if truncated:
    st.warning(f"Stopped at the {int(max_files):,}-file cap; narrow the terms or raise it.")

curve_files = [item for item in files if Path(item).suffix.lower() in CURVE_SUFFIXES]
array_files = [item for item in files if Path(item).suffix.lower() in ARRAY_SUFFIXES]
image_files = [item for item in files if Path(item).suffix.lower() in IMAGE_SUFFIXES]
st.success(
    f"{len(files):,} file(s): {len(curve_files):,} table · {len(array_files):,} array · "
    f"{len(image_files):,} image."
)

tab_1d, tab_stack, tab_2d, tab_list = st.tabs(
    ["📈 1D curves", "🌊 Stacked map", "🗺️ 2D images", "📋 File list"]
)

# ---------------------------------------------------------------------------
# Shared curve loading
# ---------------------------------------------------------------------------
one_d_candidates = curve_files + array_files


def _labels(paths):
    stems = [Path(path).stem for path in paths]
    prefix, suffix = common_prefix_suffix(stems)
    return [short_label(stem, prefix, suffix) for stem in stems]


def _load_curves(paths, x_column, y_column):
    """Load the selected curves, reporting the ones that could not be read."""

    loaded, failures = [], []
    for path in paths:
        try:
            curve = cached_curve(
                path,
                x_column or None,
                y_column or None,
                file_signature(path),
            )
        except DataReadError as exc:
            failures.append(f"{Path(path).name}: {exc}")
            continue
        loaded.append(dict(curve))
    return loaded, failures


def _normalize(values, method, x_values, reference):
    result = np.asarray(values, dtype=float)
    if method == "maximum":
        scale = np.nanmax(np.abs(result))
    elif method == "integral":
        scale = abs(integrate_curve(result, x_values))
    elif method == "at x":
        index = int(np.argmin(np.abs(np.asarray(x_values, dtype=float) - reference)))
        scale = abs(result[index]) if result.size else 0.0
    else:
        return result
    return result / scale if np.isfinite(scale) and scale > 0 else result


with tab_1d:
    if not one_d_candidates:
        st.info("No table or array files in this selection.")
    else:
        default_count = min(8, len(one_d_candidates))
        chosen = st.multiselect(
            "Curves",
            one_d_candidates,
            default=one_d_candidates[:default_count],
            format_func=lambda path: Path(path).name,
            key="quickplot_1d_files",
        )
        if not chosen:
            st.info("Select at least one file.")
        else:
            try:
                probe = cached_curve(chosen[0], None, None, file_signature(chosen[0]))
                available_columns = ["auto", *probe["columns"]]
            except DataReadError as exc:
                st.error(str(exc))
                available_columns = ["auto"]

            column_row = st.columns(4)
            x_column = column_row[0].selectbox("x column", available_columns, key="quickplot_1d_x")
            y_column = column_row[1].selectbox("y column", available_columns, key="quickplot_1d_y")
            normalization = column_row[2].selectbox(
                "Normalize",
                ["none", "maximum", "integral", "at x"],
                key="quickplot_1d_norm",
            )
            reference_x = column_row[3].number_input(
                "Normalize at x",
                value=0.1,
                format="%.5g",
                key="quickplot_1d_refx",
                disabled=normalization != "at x",
            )

            axis_row = st.columns(4)
            log_x = axis_row[0].checkbox("Log x", value=True, key="quickplot_1d_logx")
            log_y = axis_row[1].checkbox("Log y", value=True, key="quickplot_1d_logy")
            offset = axis_row[2].number_input(
                "Vertical offset per curve", value=0.0, format="%.5g", key="quickplot_1d_offset"
            )
            multiplier = axis_row[3].number_input(
                "Multiply each curve by",
                value=1.0,
                min_value=0.0001,
                format="%.5g",
                key="quickplot_1d_mult",
                help="A factor of 2 stacks curves as 1, 2, 4, 8 … on a log axis.",
            )

            range_row = st.columns(4)
            x_min = range_row[0].number_input(
                "x min (blank = auto)", value=None, format="%.5g", key="quickplot_1d_xmin"
            )
            x_max = range_row[1].number_input(
                "x max (blank = auto)", value=None, format="%.5g", key="quickplot_1d_xmax"
            )
            markers = range_row[2].checkbox("Markers", value=False, key="quickplot_1d_markers")
            legend = range_row[3].checkbox("Legend", value=True, key="quickplot_1d_legend")

            title = st.text_input("Figure title", value="", key="quickplot_1d_title")

            curves, failures = _load_curves(
                chosen,
                None if x_column == "auto" else x_column,
                None if y_column == "auto" else y_column,
            )
            for message in failures:
                st.warning(message)

            if not curves:
                st.error("None of the selected files could be read as a curve.")
            else:
                labels = _labels([curve["path"] for curve in curves])
                figure = go.Figure()
                export_frames = []
                import plotly.express as px

                palette = px.colors.sample_colorscale(
                    "Turbo", np.linspace(0.05, 0.95, max(1, len(curves)))
                )
                for index, (curve, label, color) in enumerate(zip(curves, labels, palette)):
                    x_values = curve["x"]
                    keep = np.ones(x_values.shape, dtype=bool)
                    if x_min is not None:
                        keep &= x_values >= x_min
                    if x_max is not None:
                        keep &= x_values <= x_max
                    if not keep.any():
                        st.warning(f"{label}: nothing inside the selected x range.")
                        continue
                    x_values = x_values[keep]
                    y_values = _normalize(curve["y"][keep], normalization, x_values, reference_x)
                    y_values = y_values * (multiplier**index) + index * float(offset)
                    curve["plot_x"], curve["plot_y"], curve["plot_label"] = (
                        x_values,
                        y_values,
                        label,
                    )
                    figure.add_trace(
                        go.Scatter(
                            x=x_values,
                            y=y_values,
                            name=label,
                            mode="lines+markers" if markers else "lines",
                            line=dict(width=2, color=color),
                            marker=dict(size=5, color=color),
                            hovertemplate=f"{label}<br>x=%{{x:.5g}}<br>y=%{{y:.5g}}<extra></extra>",
                        )
                    )
                    export_frames.append(
                        pd.DataFrame({f"x[{label}]": x_values, f"y[{label}]": y_values})
                    )

                figure.update_xaxes(
                    title_text=curves[0]["x_name"], type="log" if log_x else "linear"
                )
                figure.update_yaxes(
                    title_text=(
                        "Normalized intensity" if normalization != "none" else curves[0]["y_name"]
                    ),
                    type="log" if log_y else "linear",
                )
                figure.update_layout(
                    title=title,
                    height=600,
                    template="plotly_white",
                    hovermode="closest",
                    showlegend=legend,
                    legend=dict(orientation="v", x=1.01, y=1),
                    margin=dict(l=70, r=20, t=50, b=55),
                )
                st.plotly_chart(figure, width="stretch", key="quickplot_1d_chart")

                plotted = [curve for curve in curves if "plot_x" in curve]
                export_table = pd.concat(export_frames, axis=1) if export_frames else None
                render_save_panel(
                    TAB_NAME,
                    f"curves_{len(plotted)}",
                    key="quickplot_1d_save",
                    figure=figure,
                    figure_kind="plotly",
                    table=export_table,
                    expanded=False,
                    caption=(
                        "HTML keeps the plot interactive; PNG/SVG/PDF need the free "
                        "kaleido package."
                    ),
                )

                with st.expander("📐 Publication figure (matplotlib themes)", expanded=False):
                    theme_row = st.columns(4)
                    theme = theme_row[0].selectbox(
                        "Theme",
                        ["science", "notebook", "present", "poster"],
                        key="quickplot_1d_theme",
                    )
                    width = theme_row[1].number_input(
                        "Width (in)", 3.0, 20.0, 7.0, 0.5, key="quickplot_1d_w"
                    )
                    height = theme_row[2].number_input(
                        "Height (in)", 3.0, 20.0, 5.0, 0.5, key="quickplot_1d_h"
                    )
                    xlabel = theme_row[3].text_input(
                        "x label", value=curves[0]["x_name"], key="quickplot_1d_xlabel"
                    )
                    try:
                        static = build_curve_figure(
                            [
                                Curve(curve["plot_label"], curve["plot_x"], curve["plot_y"])
                                for curve in plotted
                            ],
                            theme=theme,
                            normalization="none",
                            logx=log_x,
                            logy=log_y,
                            title=title,
                            xlabel=xlabel,
                            ylabel=(
                                "Normalized intensity"
                                if normalization != "none"
                                else curves[0]["y_name"]
                            ),
                            figsize=(float(width), float(height)),
                            legend=legend,
                        )
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.pyplot(static, width="content")
                        render_save_panel(
                            TAB_NAME,
                            f"publication_curves_{len(plotted)}",
                            key="quickplot_1d_static_save",
                            figure=static,
                            figure_kind="matplotlib",
                            expanded=False,
                        )
                        plt.close(static)

# ---------------------------------------------------------------------------
# Stacked intensity map
# ---------------------------------------------------------------------------
with tab_stack:
    st.caption(
        "Interpolate every selected curve onto one x grid and show the set as an "
        "intensity map or a waterfall. This is how an in-situ or angle series is "
        "read at a glance."
    )
    if not one_d_candidates:
        st.info("No table or array files in this selection.")
    else:
        stack_files = st.multiselect(
            "Curves in the stack",
            one_d_candidates,
            default=one_d_candidates[: min(30, len(one_d_candidates))],
            format_func=lambda path: Path(path).name,
            key="quickplot_stack_files",
        )
        if len(stack_files) < 2:
            st.info("Select at least two curves.")
        else:
            option_row = st.columns(5)
            representation = option_row[0].selectbox(
                "Show as", ["Intensity map", "Waterfall"], key="quickplot_stack_kind"
            )
            stack_logx = option_row[1].checkbox("Log x", value=True, key="quickplot_stack_logx")
            stack_logI = option_row[2].checkbox(
                "Log intensity", value=True, key="quickplot_stack_logI"
            )
            stack_cmap = option_row[3].selectbox("Colormap", CMAPS, key="quickplot_stack_cmap")
            grid_points = option_row[4].number_input(
                "Grid points", 50, 4000, 600, 50, key="quickplot_stack_points"
            )
            range_row = st.columns(3)
            stack_xmin = range_row[0].number_input(
                "x min (blank = auto)", value=None, format="%.5g", key="quickplot_stack_xmin"
            )
            stack_xmax = range_row[1].number_input(
                "x max (blank = auto)", value=None, format="%.5g", key="quickplot_stack_xmax"
            )
            waterfall_offset = range_row[2].number_input(
                "Waterfall offset",
                value=1.0,
                format="%.5g",
                key="quickplot_stack_offset",
                disabled=representation != "Waterfall",
                help="Multiplicative on a log axis, additive otherwise.",
            )

            stacked, failures = _load_curves(stack_files, None, None)
            for message in failures:
                st.warning(message)
            if len(stacked) < 2:
                st.error("At least two readable curves are needed for a stack.")
            else:
                labels = _labels([curve["path"] for curve in stacked])
                for curve, label in zip(stacked, labels):
                    curve["label"] = label
                try:
                    grid, names, matrix = stack_curves(
                        stacked,
                        points=int(grid_points),
                        x_min=stack_xmin,
                        x_max=stack_xmax,
                        log_x=stack_logx,
                    )
                except DataReadError as exc:
                    st.error(str(exc))
                else:
                    if representation == "Intensity map":
                        if stack_logI:
                            display = log_scale(np.where(matrix > 0, matrix, np.nan))
                        else:
                            display = matrix
                        zmin, zmax = color_limits(matrix, None, None, stack_logI)
                        stack_figure = go.Figure(
                            go.Heatmap(
                                z=display,
                                x=grid,
                                y=np.arange(len(names)),
                                colorscale=stack_cmap,
                                zmin=zmin,
                                zmax=zmax,
                                colorbar=dict(title="log I" if stack_logI else "I"),
                                hovertemplate=(
                                    "x=%{x:.5g}<br>curve %{y}<br>I=%{z:.4g}<extra></extra>"
                                ),
                            )
                        )
                        stack_figure.update_yaxes(
                            title_text="curve",
                            tickmode="array",
                            tickvals=list(range(len(names))),
                            ticktext=names,
                        )
                        stack_figure.update_xaxes(
                            title_text=stacked[0]["x_name"],
                            type="log" if stack_logx else "linear",
                        )
                        stack_figure.update_layout(
                            height=max(420, 22 * len(names)),
                            template="plotly_white",
                            margin=dict(l=200, r=20, t=40, b=55),
                        )
                    else:
                        stack_figure = go.Figure()
                        import plotly.express as px

                        palette = px.colors.sample_colorscale(
                            stack_cmap, np.linspace(0.05, 0.95, len(names))
                        )
                        for index, (name, color) in enumerate(zip(names, palette)):
                            row = matrix[index]
                            shifted = (
                                row * (float(waterfall_offset) ** index)
                                if stack_logI
                                else row + index * float(waterfall_offset)
                            )
                            stack_figure.add_trace(
                                go.Scatter(
                                    x=grid,
                                    y=shifted,
                                    name=name,
                                    mode="lines",
                                    line=dict(width=1.6, color=color),
                                )
                            )
                        stack_figure.update_xaxes(
                            title_text=stacked[0]["x_name"],
                            type="log" if stack_logx else "linear",
                        )
                        stack_figure.update_yaxes(
                            title_text="Offset intensity",
                            type="log" if stack_logI else "linear",
                        )
                        stack_figure.update_layout(
                            height=650,
                            template="plotly_white",
                            margin=dict(l=70, r=20, t=40, b=55),
                        )
                    st.plotly_chart(stack_figure, width="stretch", key="quickplot_stack_chart")

                    stack_table = pd.DataFrame(matrix.T, columns=names)
                    stack_table.insert(0, stacked[0]["x_name"], grid)
                    render_save_panel(
                        TAB_NAME,
                        f"stack_{len(names)}_curves",
                        key="quickplot_stack_save",
                        figure=stack_figure,
                        figure_kind="plotly",
                        table=stack_table,
                        arrays={"x": grid, "intensity": matrix},
                        caption="The array bundle holds the interpolated x grid and matrix.",
                    )

# ---------------------------------------------------------------------------
# 2D images and arrays
# ---------------------------------------------------------------------------
with tab_2d:
    two_d_candidates = image_files + array_files
    if not two_d_candidates:
        st.info("No image or array files in this selection.")
    else:
        chosen_2d = st.selectbox(
            "File",
            two_d_candidates,
            format_func=lambda path: Path(path).name,
            key="quickplot_2d_file",
        )
        arrays: dict[str, np.ndarray] = {}
        try:
            if Path(chosen_2d).suffix.lower() in ARRAY_SUFFIXES:
                arrays = {
                    name: np.asarray(value)
                    for name, value in cached_arrays(chosen_2d, file_signature(chosen_2d)).items()
                    if np.ndim(value) == 2
                }
            else:
                arrays = {Path(chosen_2d).stem: cached_image(chosen_2d, file_signature(chosen_2d))}
        except DataReadError as exc:
            st.error(str(exc))

        if not arrays:
            st.warning("This file holds no two-dimensional array.")
        else:
            control_row = st.columns(5)
            array_name = control_row[0].selectbox("Array", list(arrays), key="quickplot_2d_array")
            cmap_2d = control_row[1].selectbox("Colormap", CMAPS, key="quickplot_2d_cmap")
            log_2d = control_row[2].checkbox("Log intensity", value=True, key="quickplot_2d_log")
            equal_2d = control_row[3].checkbox(
                "Equal aspect", value=False, key="quickplot_2d_equal"
            )
            flip_2d = control_row[4].checkbox(
                "Flip vertically", value=False, key="quickplot_2d_flip"
            )
            percentiles = st.slider(
                "Robust display percentiles",
                0.0,
                100.0,
                (1.0, 99.5),
                0.5,
                key="quickplot_2d_percentiles",
            )

            image = np.asarray(arrays[array_name], dtype=float)
            if flip_2d:
                image = np.flipud(image)
            finite = image[np.isfinite(image)]
            if finite.size:
                vmin, vmax = np.nanpercentile(finite, list(percentiles))
            else:
                vmin, vmax = None, None
            shown, x_axis, y_axis = downsample(
                image, np.arange(image.shape[1]), np.arange(image.shape[0])
            )
            display = log_scale(shown) if log_2d else shown
            zmin, zmax = color_limits(shown, vmin, vmax, log_2d)
            figure_2d = go.Figure(
                go.Heatmap(
                    z=display,
                    x=x_axis,
                    y=y_axis,
                    colorscale=cmap_2d,
                    zmin=zmin,
                    zmax=zmax,
                    colorbar=dict(title="log I" if log_2d else "I"),
                    hovertemplate="x=%{x}<br>y=%{y}<br>I=%{z:.4g}<extra></extra>",
                )
            )
            figure_2d.update_xaxes(title_text="x index")
            figure_2d.update_yaxes(title_text="y index")
            if equal_2d:
                figure_2d.update_xaxes(constrain="domain")
                figure_2d.update_yaxes(scaleanchor="x", scaleratio=1.0, constrain="domain")
            figure_2d.update_layout(
                title=f"{Path(chosen_2d).name} · {array_name}",
                height=680,
                template="plotly_white",
                plot_bgcolor="#101010",
                margin=dict(l=60, r=20, t=50, b=50),
            )
            st.plotly_chart(figure_2d, width="stretch", key="quickplot_2d_chart")
            st.caption(
                f"Shape {image.shape[0]} × {image.shape[1]}; displayed at "
                f"{shown.shape[0]} × {shown.shape[1]} after decimation."
            )

            render_save_panel(
                TAB_NAME,
                f"{Path(chosen_2d).stem}_{array_name}",
                key="quickplot_2d_save",
                figure=figure_2d,
                figure_kind="plotly",
                arrays={array_name: image},
            )

# ---------------------------------------------------------------------------
# File list
# ---------------------------------------------------------------------------
with tab_list:
    listing = pd.DataFrame(
        [
            {
                "name": Path(path).name,
                "kind": (
                    "curve"
                    if Path(path).suffix.lower() in CURVE_SUFFIXES
                    else "array"
                    if Path(path).suffix.lower() in ARRAY_SUFFIXES
                    else "image"
                ),
                "folder": str(Path(path).parent),
                "path": path,
            }
            for path in files
        ]
    )
    st.dataframe(listing, width="stretch", hide_index=True)
    render_save_panel(
        TAB_NAME,
        "quick_plot_files",
        key="quickplot_list_save",
        table=listing,
        text="\n".join(files),
        caption="Keep the exact file list that produced these figures.",
    )
