"""A read-only terminal for finding data and building named file lists.

Clicking through a mounted proposal is slower than typing, and everyone here
already knows ``ls``, ``cd`` and ``cat``. Nothing is handed to a system shell:
each command is parsed in :mod:`pyscattviz.shell` and implemented with
``pathlib``, so there is no way to spell ``rm``.

The list built here *is* the dataset basket, so a list assembled with a couple of
``select`` lines shows up immediately in Quick Plot, in Publication Plot, and in
the explorers — and ``save <name>`` keeps it for another day.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from pyscattviz.app.components.datasource import known_folders, remember_folder
from pyscattviz.app.components.saving import render_save_panel
from pyscattviz.app.state import set_persistent_value
from pyscattviz.data_sources import load_path_mappings
from pyscattviz.shell import COMMAND_HELP, run_shell_command

TAB_NAME = "Terminal"
BASKET_KEY = "pyscattviz_dataset_paths"
CWD_KEY = "pyscattviz_shell_cwd"
HISTORY_KEY = "pyscattviz_shell_history"

st.set_page_config(page_title="Terminal", page_icon="🖥️", layout="wide")
st.title("🖥️ Terminal")
st.caption(
    "ls, cd, cat, find — and `select` to build a list that every plotting tab reads. "
    "Read-only: there is no command here that can change your data."
)

st.session_state.setdefault("pyscattviz_path_mappings", load_path_mappings())
st.session_state.setdefault(BASKET_KEY, [])
st.session_state.setdefault(HISTORY_KEY, [])
if CWD_KEY not in st.session_state:
    starting = known_folders()
    st.session_state[CWD_KEY] = starting[0] if starting else str(Path.home())

mappings = st.session_state["pyscattviz_path_mappings"]


def _run(command: str) -> None:
    """Run one command and fold its result back into the session."""

    result = run_shell_command(
        command,
        st.session_state[CWD_KEY],
        selection=tuple(st.session_state.get(BASKET_KEY, [])),
        path_mappings=mappings,
    )
    st.session_state[CWD_KEY] = result.cwd
    if result.selection_changed:
        st.session_state[BASKET_KEY] = list(result.selection)
    st.session_state["pyscattviz_shell_result"] = {
        "output": result.output,
        "rows": result.rows,
        "error": result.error,
    }
    history = st.session_state[HISTORY_KEY]
    if command.strip() and (not history or history[-1] != command.strip()):
        history.append(command.strip())
        del history[:-50]


folder_row = st.columns([4, 1])
folder_row[0].code(st.session_state[CWD_KEY], language=None)
if folder_row[1].button("Use as data folder", use_container_width=True):
    folder = st.session_state[CWD_KEY]
    set_persistent_value(st.session_state, "pyscattviz_file_root", folder)
    st.session_state["pyscattviz_active_root"] = folder
    remember_folder(folder)
    st.success(f"`{folder}` is now the active folder for the explorers.")

command_row = st.columns([5, 1])
command = command_row[0].text_input(
    "Command",
    value="",
    key="pyscattviz_shell_command",
    placeholder="ls *UV_2*      ·      select *UV_20* *UV_30*      ·      save uv_series",
    label_visibility="collapsed",
)
if command_row[1].button("Run", type="primary", use_container_width=True):
    _run(command)

quick = st.columns(6)
for index, (label, shortcut) in enumerate(
    [
        ("ls", "ls"),
        ("up one", "cd .."),
        ("list", "list"),
        ("saved lists", "lists"),
        ("size", "du"),
        ("help", "help"),
    ]
):
    if quick[index].button(
        label, key=f"pyscattviz_shell_quick_{shortcut}", use_container_width=True
    ):
        _run(shortcut)

result = st.session_state.get("pyscattviz_shell_result")
if result:
    if result["error"]:
        st.error(result["error"])
    elif result["output"]:
        st.code(result["output"], language=None)
    if result["rows"]:
        st.dataframe(pd.DataFrame(result["rows"]), width="stretch", hide_index=True)

basket = st.session_state.get(BASKET_KEY, [])
st.divider()
st.subheader(f"🧺 Current list — {len(basket):,} file(s)")
if not basket:
    st.info(
        "Empty. Move to a folder with `cd`, then `select *pattern*` — several "
        "patterns are OR-ed, so `select *UV_20* *UV_30*` takes both samples."
    )
else:
    listing = pd.DataFrame(
        [
            {"name": Path(item).name, "folder": str(Path(item).parent), "path": item}
            for item in basket
        ]
    )
    st.dataframe(listing, width="stretch", hide_index=True)
    st.caption(
        "Quick Plot, Publication Plot, and the explorers all read this list. "
        "`save <name>` keeps it under `~/.pyscattviz/collections/`."
    )
    render_save_panel(
        TAB_NAME,
        "terminal_list",
        key="terminal_list_save",
        table=listing,
        text="\n".join(basket),
        caption="Write the list to disk as a table or a plain list of full paths.",
    )

with st.expander("📖 Commands", expanded=not bool(result)):
    st.code(COMMAND_HELP, language=None)

history = st.session_state.get(HISTORY_KEY, [])
if history:
    with st.expander("🕘 History", expanded=False):
        st.code("\n".join(history[-25:]), language=None)
        if st.button("Run the last command again"):
            _run(history[-1])
            st.rerun()
