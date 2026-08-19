"""Write and run your own Python against the data this session already has.

The GUI covers the plots I could anticipate; this covers the rest. Every
plotting page can hand its figure over as a script — *Show the Python for this
figure* — and that script lands here ready to change.

The namespace arrives loaded: `basket` is the current file list, `folder` the
active data folder, and the plotting, reading, and saving helpers are already
imported, so the first line can be about the science.

This runs your code in this process with your permissions, exactly like typing
it at a Python prompt. pyScattViz listens on 127.0.0.1, and the page refuses to
run anything if the server has been bound somewhere other people can reach.
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

import pyscattviz.plotting as pv
from pyscattviz.app.components.saving import output_root, render_save_panel
from pyscattviz.app.state import keep_widget_state
from pyscattviz.console import STARTER_SNIPPETS, is_local_only, run_snippet
from pyscattviz.dataio import read_arrays, read_curve, read_image, read_table, stack_curves
from pyscattviz.discovery import find_files, find_folders, ls_dir
from pyscattviz.exporting import resolve_output_dir, save_matplotlib_figure, save_plotly_figure
from pyscattviz.publication import Curve, build_curve_figure

TAB_NAME = "Python Console"
BASKET_KEY = "pyscattviz_dataset_paths"
CODE_KEY = "pyscattviz_console_code"
NAMESPACE_KEY = "pyscattviz_console_namespace"

st.set_page_config(page_title="Python Console", page_icon="🐍", layout="wide")

# Streamlit forgets a page's widgets as soon as another page is opened. Keep them.
keep_widget_state(st.session_state)
st.title("🐍 Python Console")
st.caption(
    "Your own code, with this session's data already loaded. A trailing "
    "expression is shown, as in a notebook."
)

try:
    address = st.get_option("server.address")
except Exception:  # pragma: no cover - older Streamlit without the option
    address = None

if not is_local_only(address):
    st.error(
        f"The console is disabled because this server is listening on `{address}`, "
        "which other people on the network can reach — running code typed into a "
        "browser would then be running it for them too.\n\n"
        "Start pyScattViz without `--address`, or with `--address 127.0.0.1`, to "
        "use the console."
    )
    st.stop()

st.session_state.setdefault(BASKET_KEY, [])
st.session_state.setdefault(CODE_KEY, "")

basket = list(st.session_state.get(BASKET_KEY, []))
folder = str(st.session_state.get("pyscattviz_active_root", ""))


def _namespace() -> dict:
    """The names a snippet starts with; kept between runs like a notebook."""

    namespace = st.session_state.get(NAMESPACE_KEY)
    if namespace is None:
        namespace = {"__name__": "pyscattviz_console"}
        st.session_state[NAMESPACE_KEY] = namespace
    namespace.update(
        {
            "np": np,
            "pd": pd,
            "plt": plt,
            "go": go,
            "pv": pv,
            "Path": Path,
            "basket": basket,
            "folder": folder,
            "output_root": output_root(),
            "read_curve": read_curve,
            "read_table": read_table,
            "read_arrays": read_arrays,
            "read_image": read_image,
            "stack_curves": stack_curves,
            "ls_dir": ls_dir,
            "find_files": find_files,
            "find_folders": find_folders,
            "Curve": Curve,
            "build_curve_figure": build_curve_figure,
            "resolve_output_dir": resolve_output_dir,
            "save_matplotlib_figure": save_matplotlib_figure,
            "save_plotly_figure": save_plotly_figure,
        }
    )
    return namespace


status = st.columns(3)
status[0].metric("Files in `basket`", f"{len(basket):,}")
status[1].metric("`folder`", Path(folder).name if folder else "—")
status[2].metric("Figures saved to", Path(output_root()).name)

handoff = st.session_state.pop("pyscattviz_console_handoff", None)
if handoff:
    st.session_state[CODE_KEY] = handoff
    st.success("Loaded the code from the page you came from.")

starter_row = st.columns([3, 1])
starter = starter_row[0].selectbox(
    "Start from an example",
    ["— keep what is in the editor —", *STARTER_SNIPPETS],
    key="pyscattviz_console_starter",
)
with starter_row[1]:
    st.write("")
    if st.button(
        "Load example", use_container_width=True, disabled=starter not in STARTER_SNIPPETS
    ):
        st.session_state[CODE_KEY] = STARTER_SNIPPETS[starter]
        st.rerun()

code = st.text_area(
    "Code",
    value=st.session_state[CODE_KEY],
    height=320,
    key="pyscattviz_console_editor",
    label_visibility="collapsed",
)
st.session_state[CODE_KEY] = code

run_row = st.columns([1, 1, 1, 3])
run_clicked = run_row[0].button("▶ Run", type="primary", use_container_width=True)
if run_row[1].button(
    "Reset names", use_container_width=True, help="Forget variables from earlier runs."
):
    st.session_state[NAMESPACE_KEY] = None
    st.success("The namespace is empty again.")
if run_row[2].button("Clear output", use_container_width=True):
    st.session_state.pop("pyscattviz_console_result", None)
run_row[3].caption(
    "Available: `np` `pd` `plt` `go` `pv`, `basket`, `folder`, `read_curve`, "
    "`ls_dir`, `find_folders`, `stack_curves`, `build_curve_figure`, "
    "`save_matplotlib_figure`, `resolve_output_dir`."
)

if run_clicked:
    plt.close("all")
    before = set(plt.get_fignums())
    outcome = run_snippet(code, _namespace())
    st.session_state["pyscattviz_console_result"] = {
        "stdout": outcome.stdout,
        "error": outcome.error,
        "value": outcome.value if outcome.has_value else None,
        "has_value": outcome.has_value,
        "figures": [plt.figure(number) for number in plt.get_fignums() if number not in before],
    }

result = st.session_state.get("pyscattviz_console_result")
if result:
    st.divider()
    if result["error"]:
        st.error("The snippet raised an error.")
        st.code(result["error"], language="text")
    if result["stdout"]:
        st.subheader("Output")
        st.code(result["stdout"], language="text")

    value = result["value"]
    figures = list(result["figures"])
    shown_value = False

    if isinstance(value, go.Figure):
        st.plotly_chart(value, use_container_width=True)
        render_save_panel(
            TAB_NAME,
            "console_figure",
            key="console_plotly_save",
            figure=value,
            figure_kind="plotly",
        )
        shown_value = True
    elif isinstance(value, matplotlib.figure.Figure):
        st.pyplot(value, width="content")
        render_save_panel(
            TAB_NAME,
            "console_figure",
            key="console_mpl_save",
            figure=value,
            figure_kind="matplotlib",
        )
        figures = [item for item in figures if item is not value]
        shown_value = True
    elif isinstance(value, pd.DataFrame):
        st.dataframe(value, width="stretch")
        render_save_panel(TAB_NAME, "console_table", key="console_table_save", table=value)
        shown_value = True
    elif isinstance(value, np.ndarray) and value.ndim == 2:
        st.write(f"array {value.shape}")
        st.plotly_chart(
            pv.imshow(value, interactive=True, log=False, title="result"),
            use_container_width=True,
        )
        shown_value = True

    if result["has_value"] and not shown_value:
        st.subheader("Value")
        st.code(repr(value)[:5000], language="text")

    for index, figure in enumerate(figures):
        st.pyplot(figure, width="content")
        render_save_panel(
            TAB_NAME,
            f"console_figure_{index + 1}",
            key=f"console_extra_save_{index}",
            figure=figure,
            figure_kind="matplotlib",
        )

if code.strip():
    render_save_panel(
        TAB_NAME,
        "console_script",
        key="console_script_save",
        text=code,
        caption="Keep the snippet itself; it is written as a .txt beside your figures.",
    )
