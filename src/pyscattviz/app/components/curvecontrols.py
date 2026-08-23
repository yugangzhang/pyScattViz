"""Every matplotlib control a 1-D curve figure has, in one reusable block.

These started life inline on the Publication Plot page, which is why Quick Plot
had a handful of them and Publication Plot had all of them — the same figure
builder underneath, two different sets of knobs in front of it. Extracted here
so both pages offer the whole set and neither drifts.

:func:`render_figure_controls` returns the keyword arguments for
:func:`pyscattviz.publication.build_curve_figure`; :func:`render_curve_styles`
returns the per-curve :class:`~pyscattviz.publication.CurveStyle` list. Every
widget key is built from ``prefix``, so a page keeps whatever keys it already
had — Publication Plot passes ``"pub"`` and its settings survive the move.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pyscattviz.app.state import register_widget_suffix
from pyscattviz.publication import (
    LEGEND_LOCATIONS,
    LINE_STYLES,
    MARKERS,
    TICK_DIRECTIONS,
    CurveStyle,
)

__all__ = ["render_curve_styles", "render_figure_controls"]

# `st.data_editor` rejects assignment through session_state, and rejects it when
# the widget is created — so `keep_widget_state` re-asserting the key kills the
# page on its second render. Registered here, next to the widget that needs it.
register_widget_suffix("_curve_styles")


def render_figure_controls(
    prefix: str,
    *,
    show_theme: bool = True,
    show_normalization: bool = True,
    default_xlabel: str = r"q ($\AA^{-1}$)",
    expanded: bool = False,
) -> dict:
    """Draw the controls and return ``build_curve_figure`` keyword arguments.

    The headline four — theme, normalization, log axes — stay on the page; the
    rest go in an expander, because a figure is usually right after the first
    four and the other thirty are for the day it is not.
    """

    settings: dict = {}

    first = st.columns(4)
    if show_theme:
        settings["theme"] = first[0].selectbox(
            "Theme", ["science", "notebook", "present", "poster"], key=f"{prefix}_theme"
        )
    if show_normalization:
        settings["normalization"] = first[1].selectbox(
            "Normalization", ["none", "maximum", "integral"], key=f"{prefix}_normalization"
        )
    settings["logx"] = first[2].checkbox("Log q", value=True, key=f"{prefix}_logx")
    settings["logy"] = first[3].checkbox("Log intensity", value=True, key=f"{prefix}_logy")

    second = st.columns(4)
    settings["q_min"] = second[0].number_input(
        "q minimum (blank = auto)", value=None, format="%.5g", key=f"{prefix}_qmin"
    )
    settings["q_max"] = second[1].number_input(
        "q maximum (blank = auto)", value=None, format="%.5g", key=f"{prefix}_qmax"
    )
    settings["offset"] = second[2].number_input(
        "Vertical offset", value=0.0, format="%.5g", key=f"{prefix}_offset"
    )
    settings["legend"] = second[3].checkbox("Show legend", value=True, key=f"{prefix}_legend")

    third = st.columns([2, 1, 1])
    settings["title"] = third[0].text_input("Title", value="", key=f"{prefix}_title")
    width = third[1].number_input("Width (in)", 3.0, 20.0, 7.0, 0.5, key=f"{prefix}_width")
    height = third[2].number_input("Height (in)", 3.0, 20.0, 5.0, 0.5, key=f"{prefix}_height")
    settings["figsize"] = (float(width), float(height))

    with st.expander("📐 Axes, ticks, and legend", expanded=expanded):
        row = st.columns(4)
        x_low = row[0].number_input(
            "x min (blank = auto)", value=None, format="%.5g", key=f"{prefix}_xlim_lo"
        )
        x_high = row[1].number_input(
            "x max (blank = auto)", value=None, format="%.5g", key=f"{prefix}_xlim_hi"
        )
        y_low = row[2].number_input(
            "y min (blank = auto)", value=None, format="%.5g", key=f"{prefix}_ylim_lo"
        )
        y_high = row[3].number_input(
            "y max (blank = auto)", value=None, format="%.5g", key=f"{prefix}_ylim_hi"
        )
        # None for a whole limit rather than a half-set pair: matplotlib takes
        # (None, 5) happily, and "blank = auto" should mean auto on that side.
        settings["xlim"] = (x_low, x_high) if (x_low is not None or x_high is not None) else None
        settings["ylim"] = (y_low, y_high) if (y_low is not None or y_high is not None) else None

        row = st.columns(4)
        settings["xlabel"] = row[0].text_input(
            "x label", value=default_xlabel, key=f"{prefix}_xlabel"
        )
        ylabel = row[1].text_input("y label (blank = automatic)", value="", key=f"{prefix}_ylabel")
        if ylabel.strip():
            settings["ylabel"] = ylabel
        settings["multiplier"] = row[2].number_input(
            "Multiply curve n by",
            value=1.0,
            min_value=0.0001,
            format="%.5g",
            key=f"{prefix}_multiplier",
            help="A factor of 2 stacks curves as 1, 2, 4, 8 … on a log axis.",
        )
        settings["font_size"] = row[3].number_input(
            "Base font size", 5.0, 30.0, 10.0, 0.5, key=f"{prefix}_font_size"
        )

        row = st.columns(4)
        settings["grid"] = row[0].checkbox("Grid", value=False, key=f"{prefix}_grid")
        settings["minor_grid"] = row[1].checkbox(
            "Minor grid", value=False, key=f"{prefix}_minor_grid"
        )
        settings["minor_ticks"] = row[2].checkbox(
            "Minor ticks", value=True, key=f"{prefix}_minor_ticks"
        )
        settings["grid_alpha"] = row[3].slider(
            "Grid opacity", 0.05, 1.0, 0.3, 0.05, key=f"{prefix}_grid_alpha"
        )

        row = st.columns(4)
        settings["tick_direction"] = row[0].selectbox(
            "Tick direction", TICK_DIRECTIONS, key=f"{prefix}_tick_direction"
        )
        settings["tick_length"] = row[1].number_input(
            "Tick length", 0.0, 20.0, 4.0, 0.5, key=f"{prefix}_tick_length"
        )
        settings["tick_width"] = row[2].number_input(
            "Tick width", 0.1, 5.0, 1.0, 0.1, key=f"{prefix}_tick_width"
        )
        settings["spine_width"] = row[3].number_input(
            "Frame width", 0.1, 5.0, 1.0, 0.1, key=f"{prefix}_spine_width"
        )

        row = st.columns(4)
        settings["tick_top"] = row[0].checkbox("Ticks on top", value=True, key=f"{prefix}_tick_top")
        settings["tick_right"] = row[1].checkbox(
            "Ticks on right", value=True, key=f"{prefix}_tick_right"
        )
        settings["legend_frame"] = row[2].checkbox(
            "Legend box", value=True, key=f"{prefix}_legend_frame"
        )
        settings["legend_columns"] = row[3].number_input(
            "Legend columns", 1, 6, 1, 1, key=f"{prefix}_legend_cols"
        )

        row = st.columns(2)
        settings["legend_location"] = row[0].selectbox(
            "Legend position", LEGEND_LOCATIONS, key=f"{prefix}_legend_loc"
        )
        settings["legend_font_size"] = row[1].number_input(
            "Legend font size", 4.0, 24.0, 9.0, 0.5, key=f"{prefix}_legend_font"
        )

    return settings


def render_curve_styles(prefix: str, labels, expanded: bool = False) -> list:
    """One editable row per curve → a list of :class:`CurveStyle`."""

    names = list(labels)
    with st.expander("🎨 Per-curve style", expanded=expanded):
        st.caption(
            "One row per curve, in plotting order. Leave the colour blank to "
            "follow the theme's own cycle."
        )
        table = pd.DataFrame(
            {
                "curve": names,
                "label": ["" for _ in names],
                "color": ["" for _ in names],
                "line": ["solid" for _ in names],
                "width": [1.6 for _ in names],
                "marker": ["none" for _ in names],
                "marker size": [5.0 for _ in names],
                "every nth marker": [1 for _ in names],
                "opacity": [1.0 for _ in names],
            }
        )
        edited = st.data_editor(
            table,
            width="stretch",
            hide_index=True,
            disabled=["curve"],
            column_config={
                "line": st.column_config.SelectboxColumn(options=list(LINE_STYLES)),
                "marker": st.column_config.SelectboxColumn(options=list(MARKERS)),
                "color": st.column_config.TextColumn(
                    help="A matplotlib colour: crimson, #1f77b4, C0"
                ),
                "width": st.column_config.NumberColumn(min_value=0.1, max_value=10.0, step=0.1),
                "marker size": st.column_config.NumberColumn(
                    min_value=0.0, max_value=30.0, step=0.5
                ),
                "every nth marker": st.column_config.NumberColumn(
                    min_value=1, max_value=500, step=1
                ),
                "opacity": st.column_config.NumberColumn(min_value=0.05, max_value=1.0, step=0.05),
            },
            key=f"{prefix}_curve_styles",
        )

    return [
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
        for _index, row in edited.iterrows()
    ]
