"""Interactive front end for the consolidated pyScattViz plotting API."""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

import pyscattviz.plotting as pv
from pyscattviz.app.components.saving import render_output_settings, render_save_panel
from pyscattviz.app.components.scattering import load_qimg
from pyscattviz.app.state import action_key, keep_widget_state
from pyscattviz.dataio import DataReadError
from pyscattviz.studio import (
    demo_curve_table,
    demo_image,
    read_array_bundle,
    read_numeric_table,
    two_dimensional_arrays,
)

TAB_NAME = "Plotting Studio"

st.set_page_config(page_title="Plotting Studio", page_icon="🎨", layout="wide")

# Streamlit forgets a page's widgets as soon as another page is opened. Keep them.
keep_widget_state(st.session_state)
st.title("🎨 Plotting Studio")
st.markdown(
    """
Build exploratory and export-ready figures with Yugang's consolidated plotting
tools. The four workspaces share the supported `pyscattviz.plotting` API:
**1D curves**, **2D arrays**, **3D surfaces**, and **multi-axes layouts**.
Uploaded or selected data stay in this local Streamlit session.
"""
)


with st.sidebar:
    st.header("💾 Saving")
    render_output_settings(st)
    st.caption(
        "Every workspace below writes into the Plotting_Studio subfolder of this output root."
    )


def _uploaded_table(widget_key: str, fallback: pd.DataFrame) -> pd.DataFrame:
    upload = st.file_uploader(
        "Upload CSV, TXT, or DAT",
        type=["csv", "txt", "dat"],
        key=action_key(st.session_state, widget_key),
    )
    if upload is None:
        return fallback
    try:
        return read_numeric_table(upload.getvalue(), upload.name)
    except ValueError as exc:
        st.error(str(exc))
        return fallback


def _normalize(values: np.ndarray, method: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if method == "maximum":
        scale = np.nanmax(np.abs(result))
    elif method == "integral":
        scale = np.nansum(np.abs(result))
    else:
        return result
    return result / scale if np.isfinite(scale) and scale > 0 else result


tab_1d, tab_2d, tab_3d, tab_multi = st.tabs(["📈 1D", "🗺️ 2D", "⛰️ 3D", "▦ Multi-axes"])

with tab_1d:
    st.subheader("1D curves and overlays")
    st.caption(
        "Upload a numeric table or start with the demo. Choose one x column and "
        "multiple y columns; no array is opened until it is selected here."
    )
    source = st.radio(
        "1D data source",
        ["Scattering demo", "Upload table"],
        horizontal=True,
        key="studio_1d_source",
    )
    table_1d = demo_curve_table()
    if source == "Upload table":
        table_1d = _uploaded_table("studio_1d_upload", table_1d)
    columns = table_1d.columns.tolist()
    c1, c2 = st.columns([1, 2])
    x_column = c1.selectbox("x column", columns, key="studio_1d_x")
    y_options = [column for column in columns if column != x_column]
    y_columns = c2.multiselect(
        "y column(s)",
        y_options,
        default=y_options[: min(3, len(y_options))],
        key="studio_1d_y",
    )
    p1, p2, p3, p4 = st.columns(4)
    log_x = p1.checkbox("Log x", value=True, key="studio_1d_logx")
    log_y = p2.checkbox("Log y", value=True, key="studio_1d_logy")
    markers = p3.checkbox("Show markers", value=False, key="studio_1d_markers")
    normalization = p4.selectbox("Normalize", ["none", "maximum", "integral"], key="studio_1d_norm")
    title_1d = st.text_input("Figure title", "1D scattering comparison", key="studio_1d_title")

    if y_columns:
        datasets = [
            {
                "x": table_1d[x_column].to_numpy(),
                "y": _normalize(table_1d[column].to_numpy(), normalization),
                "label": column,
                "marker": "o" if markers else None,
            }
            for column in y_columns
        ]
        figure_1d = pv.plot1d_multi(
            datasets,
            interactive=True,
            logx=log_x,
            logy=log_y,
            xlabel=x_column,
            ylabel="normalized value" if normalization != "none" else "value",
            title=title_1d,
        )
        figure_1d.update_layout(
            template="plotly_white",
            hovermode="x unified",
            height=540,
            legend=dict(orientation="h", y=1.03),
        )
        figure_1d.update_xaxes(showgrid=True, minor=dict(showgrid=True))
        figure_1d.update_yaxes(showgrid=True, minor=dict(showgrid=True))
        st.plotly_chart(figure_1d, use_container_width=True, key="studio_1d_chart")
        export_1d = table_1d[[x_column, *y_columns]].to_csv(index=False)
        st.download_button(
            "Download plotted table",
            export_1d,
            file_name="pyscattviz_1d.csv",
            mime="text/csv",
        )
        render_save_panel(
            TAB_NAME,
            "studio_1d",
            key="studio_1d_save",
            figure=figure_1d,
            figure_kind="plotly",
            table=table_1d[[x_column, *y_columns]],
        )
    else:
        st.info("Choose at least one y column.")

with tab_2d:
    st.subheader("2D array and image viewer")
    st.caption(
        "View NPY/NPZ arrays, numeric tables, detector images, or a q-image saved "
        "by File Selection. Robust percentile limits prevent isolated hot pixels "
        "from flattening the contrast."
    )
    selected_table = st.session_state.get("pyscattviz_selection_table")
    has_selected_qimg = bool(
        isinstance(selected_table, pd.DataFrame)
        and not selected_table.empty
        and "qimg" in selected_table
        and selected_table["qimg"].notna().any()
    )
    source_options = ["Reciprocal-space demo", "Upload array/image"]
    if has_selected_qimg:
        source_options.append("Saved q-image selection")
    source_2d = st.radio(
        "2D data source",
        source_options,
        horizontal=True,
        key="studio_2d_source",
    )
    bundle: dict[str, np.ndarray] = {"demo_intensity": demo_image()}
    if source_2d == "Upload array/image":
        upload_2d = st.file_uploader(
            "Upload NPY, NPZ, CSV, TXT, TIFF, PNG, or JPEG",
            type=["npy", "npz", "csv", "txt", "dat", "tif", "tiff", "png", "jpg", "jpeg"],
            key=action_key(st.session_state, "studio_2d_upload"),
        )
        if upload_2d is not None:
            try:
                bundle = read_array_bundle(upload_2d.getvalue(), upload_2d.name)
            except ValueError as exc:
                st.error(str(exc))
    elif source_2d == "Saved q-image selection":
        available_qimg = selected_table[selected_table["qimg"].notna()]
        chosen_stem = st.selectbox(
            "Saved frame",
            available_qimg["stem"].tolist(),
            key="studio_2d_saved_frame",
        )
        qimg_path = available_qimg.set_index("stem").loc[chosen_stem, "qimg"]
        try:
            bundle = {name: np.asarray(value) for name, value in load_qimg(qimg_path).items()}
        except DataReadError as exc:
            st.error(str(exc))

    arrays_2d = two_dimensional_arrays(bundle)
    if arrays_2d:
        a1, a2, a3, a4 = st.columns(4)
        array_name = a1.selectbox("2D array", list(arrays_2d), key="studio_2d_array")
        cmap_2d = a2.selectbox(
            "Colormap", ["Turbo", "Viridis", "Cividis", "Plasma", "Magma"], key="studio_2d_cmap"
        )
        log_2d = a3.checkbox("Log intensity", value=True, key="studio_2d_log")
        equal_2d = a4.checkbox("Equal pixels", value=False, key="studio_2d_equal")
        percentiles = st.slider(
            "Robust display percentiles",
            0.0,
            100.0,
            (1.0, 99.5),
            0.5,
            key="studio_2d_percentiles",
        )
        image_2d = arrays_2d[array_name]
        figure_2d = pv.imshow(
            image_2d,
            interactive=True,
            log=log_2d,
            cmap=cmap_2d,
            zlim=(percentiles[0] / 100, percentiles[1] / 100),
            aspect="equal" if equal_2d else "auto",
            origin="lower",
            xlabel="x index",
            ylabel="y index",
            title=array_name,
        )
        figure_2d.update_layout(template="plotly_white", height=620)
        st.plotly_chart(figure_2d, use_container_width=True, key="studio_2d_chart")
        array_buffer = io.BytesIO()
        np.save(array_buffer, image_2d, allow_pickle=False)
        st.download_button(
            "Download displayed array (NPY)",
            array_buffer.getvalue(),
            file_name=f"{array_name}.npy",
            mime="application/octet-stream",
        )
        render_save_panel(
            TAB_NAME,
            f"studio_2d_{array_name}",
            key="studio_2d_save",
            figure=figure_2d,
            figure_kind="plotly",
            arrays={array_name: image_2d},
        )
    else:
        st.warning("No two-dimensional numeric array was found in this source.")

with tab_3d:
    st.subheader("3D surfaces, wireframes, and contours")
    st.caption(
        "Render a two-dimensional intensity matrix as z(x, y). Interactive Plotly "
        "rotation is enabled for surfaces and wireframes."
    )
    d1, d2 = st.columns(2)
    source_3d = d1.radio(
        "3D data source",
        ["Surface demo", "Upload matrix"],
        horizontal=True,
        key="studio_3d_source",
    )
    kind_3d = d2.selectbox(
        "Demo surface", ["ripple", "gaussian", "saddle", "volcano"], key="studio_3d_demo"
    )
    if source_3d == "Surface demo":
        x_3d, y_3d, z_3d = pv.make_demo_data(kind_3d, n=70)
        name_3d = kind_3d
    else:
        upload_3d = st.file_uploader(
            "Upload a 2D NPY, NPZ, CSV, TXT, or image",
            type=["npy", "npz", "csv", "txt", "dat", "tif", "tiff", "png", "jpg", "jpeg"],
            key=action_key(st.session_state, "studio_3d_upload"),
        )
        uploaded_bundle = {"demo_intensity": demo_image(120)}
        if upload_3d is not None:
            try:
                uploaded_bundle = read_array_bundle(upload_3d.getvalue(), upload_3d.name)
            except ValueError as exc:
                st.error(str(exc))
        matrices = two_dimensional_arrays(uploaded_bundle)
        if not matrices:
            st.warning("No 2D matrix was found; showing the demo intensity surface.")
            matrices = {"demo_intensity": demo_image(120)}
        name_3d = st.selectbox("Surface matrix", list(matrices), key="studio_3d_matrix")
        z_3d = matrices[name_3d]
        step_y = max(1, int(np.ceil(z_3d.shape[0] / 100)))
        step_x = max(1, int(np.ceil(z_3d.shape[1] / 100)))
        z_3d = z_3d[::step_y, ::step_x]
        x_3d, y_3d = np.meshgrid(np.arange(z_3d.shape[1]), np.arange(z_3d.shape[0]))

    g1, g2, g3 = st.columns(3)
    plot_type = g1.selectbox(
        "3D representation", ["Surface", "Wireframe", "Top-down contour"], key="studio_3d_type"
    )
    cmap_3d = g2.selectbox(
        "3D colormap", ["Viridis", "Turbo", "Plasma", "Cividis"], key="studio_3d_cmap"
    )
    opacity = g3.slider("Opacity", 0.1, 1.0, 0.9, 0.05, key="studio_3d_opacity")
    common_3d = dict(
        interactive=True,
        title=name_3d,
        xlabel="x",
        ylabel="y",
        zlabel="intensity",
        cmap=cmap_3d,
        alpha=opacity,
    )
    if plot_type == "Wireframe":
        figure_3d = pv.wireframe(x_3d, y_3d, z_3d, **common_3d)
    elif plot_type == "Top-down contour":
        figure_3d = pv.contour(x_3d, y_3d, z_3d, **common_3d)
    else:
        figure_3d = pv.surface(x_3d, y_3d, z_3d, **common_3d)
    figure_3d.update_layout(template="plotly_white", height=650)
    st.plotly_chart(figure_3d, use_container_width=True, key="studio_3d_chart")
    render_save_panel(
        TAB_NAME,
        f"studio_3d_{name_3d}",
        key="studio_3d_save",
        figure=figure_3d,
        figure_kind="plotly",
        arrays={"z": np.asarray(z_3d)},
    )

with tab_multi:
    st.subheader("Multi-axes figure builder")
    st.caption(
        "Build grids, a main-plus-residual figure, or a named mosaic. Each panel "
        "uses the same labels and publication themes as the Python plotting API."
    )
    source_multi = st.radio(
        "Multi-axes data source",
        ["Scattering demo", "Upload table"],
        horizontal=True,
        key="studio_multi_source",
    )
    table_multi = demo_curve_table()
    if source_multi == "Upload table":
        table_multi = _uploaded_table("studio_multi_upload", table_multi)
    multi_columns = table_multi.columns.tolist()
    m1, m2, m3 = st.columns(3)
    multi_x = m1.selectbox("Shared x column", multi_columns, key="studio_multi_x")
    multi_y_options = [column for column in multi_columns if column != multi_x]
    multi_y = m2.multiselect(
        "Panel y columns",
        multi_y_options,
        default=multi_y_options[: min(4, len(multi_y_options))],
        key="studio_multi_y",
    )
    layout = m3.selectbox(
        "Layout", ["Grid", "Main + residual", "Mosaic"], key="studio_multi_layout"
    )
    f1, f2, f3, f4 = st.columns(4)
    theme = f1.selectbox(
        "Theme", ["science", "notebook", "present", "poster"], key="studio_multi_theme"
    )
    multi_logx = f2.checkbox("Log x", value=True, key="studio_multi_logx")
    multi_logy = f3.checkbox("Log y", value=True, key="studio_multi_logy")
    export_format = f4.selectbox("Export", ["png", "svg", "pdf"], key="studio_multi_export")

    if multi_y:
        x_values = table_multi[multi_x].to_numpy()
        with pv.theme_context(theme):
            if layout == "Main + residual":
                figure_multi, main_axis, residual_axis = pv.create_axes_ratio(
                    ratio=4, figsize=(9, 7)
                )
                datasets = [
                    {
                        "x": x_values,
                        "y": table_multi[column].to_numpy(),
                        "label": column,
                    }
                    for column in multi_y
                ]
                pv.plot1d_multi(
                    datasets,
                    ax=main_axis,
                    logx=multi_logx,
                    logy=multi_logy,
                    ylabel="value",
                )
                first = table_multi[multi_y[0]].to_numpy(dtype=float)
                trend = pd.Series(first).rolling(25, center=True, min_periods=1).mean()
                residual_axis.plot(x_values, first - trend, color="crimson", lw=1.2)
                residual_axis.axhline(0, color="0.4", lw=0.8)
                residual_axis.set_xlabel(multi_x)
                residual_axis.set_ylabel("residual")
                if multi_logx:
                    residual_axis.set_xscale("log")
            elif layout == "Mosaic":
                figure_multi, axes_by_name = pv.create_axes_mosaic("AAB\nCCD", figsize=(11, 7))
                axes = list(axes_by_name.values())
                for axis, column in zip(axes, multi_y):
                    pv.plot1d(
                        table_multi[column].to_numpy(),
                        x=x_values,
                        ax=axis,
                        logx=multi_logx,
                        logy=multi_logy,
                        title=column,
                        xlabel=multi_x,
                    )
            else:
                panel_count = len(multi_y)
                cols = 2 if panel_count > 1 else 1
                rows = int(np.ceil(panel_count / cols))
                figure_multi, axes = pv.create_axes(rows, cols, figsize=(10, 3.8 * rows))
                for axis, column in zip(axes, multi_y):
                    pv.plot1d(
                        table_multi[column].to_numpy(),
                        x=x_values,
                        ax=axis,
                        logx=multi_logx,
                        logy=multi_logy,
                        title=column,
                        xlabel=multi_x,
                    )
                for axis in axes[len(multi_y) :]:
                    axis.set_visible(False)

        st.pyplot(figure_multi, width="stretch")
        mime = {"png": "image/png", "svg": "image/svg+xml", "pdf": "application/pdf"}
        st.download_button(
            "Download multi-axes figure",
            pv.fig_to_bytes(figure_multi, format=export_format, dpi=300),
            file_name=f"pyscattviz_multi_axes.{export_format}",
            mime=mime[export_format],
            type="primary",
        )
        render_save_panel(
            TAB_NAME,
            f"studio_multi_axes_{layout.replace(' ', '_').lower()}",
            key="studio_multi_save",
            figure=figure_multi,
            figure_kind="matplotlib",
            table=table_multi[[multi_x, *multi_y]],
        )
        plt.close(figure_multi)
    else:
        st.info("Choose at least one y column for the panels.")
