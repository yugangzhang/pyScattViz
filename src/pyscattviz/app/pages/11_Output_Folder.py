"""Choose where saved figures go, and see what has been written there.

Every page that draws something offers a **Save to disk** panel. They all share
the output root set here, and each writes into its own subfolder named after the
page, so a day's review sorts itself:

``<output root>/GIWAXS_Explorer/``, ``<output root>/Quick_Plot/``,
``<output root>/Publication_Plot/`` …

Nothing on this page touches proposal data; it only manages the folder the user
has chosen for their own figures and tables.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from pyscattviz.app.components.saving import (
    HISTORY_KEY,
    ensure_output_settings,
    output_root,
    render_output_settings,
    set_output_root,
    target_folder,
)
from pyscattviz.browser import human_size
from pyscattviz.exporting import (
    ExportError,
    default_output_root,
    resolve_output_dir,
    safe_component,
    settings_file,
)

PAGE_FOLDERS = (
    "Data Selection",
    "File Selection",
    "GISAXS Explorer",
    "GIWAXS Explorer",
    "Transmission SAXS",
    "Transmission WAXS",
    "Quick Plot",
    "Publication Plot",
    "Plotting Studio",
)

st.set_page_config(page_title="Output Folder", page_icon="📂", layout="wide")
st.title("📂 Output Folder")
st.caption("One place to choose where pyScattViz writes figures, tables, and arrays.")

ensure_output_settings()

st.subheader("Where saved output goes")
render_output_settings(st)

root = Path(output_root()).expanduser()
if root.is_dir():
    st.success(f"`{root}` exists and is ready.")
elif root.parent.is_dir() or root.parent == root:
    st.info(f"`{root}` will be created the first time something is saved.")
else:
    st.warning(
        f"`{root.parent}` does not exist on this computer. Choose a folder inside an "
        "available disk, or create the parent folder first."
    )

reset_columns = st.columns([1, 1, 2])
if reset_columns[0].button("Create it now"):
    try:
        resolve_output_dir(root, create=True)
    except ExportError as exc:
        st.error(str(exc))
    else:
        st.success(f"Created {root}")
        st.rerun()
if reset_columns[1].button("Use the default folder"):
    set_output_root(str(default_output_root()))
    st.rerun()
reset_columns[2].caption(
    f"Preferences are stored in `{settings_file()}`. "
    "`PYSCATTVIZ_OUTPUT_DIR` overrides the default on a new installation."
)

st.divider()
st.subheader("Folder each page will use")
st.caption(
    "These are created on demand. Turning off *Subfolder per page* above makes every "
    "page write directly into the output root instead."
)
st.dataframe(
    pd.DataFrame(
        [
            {
                "page": name,
                "folder": str(target_folder(name)),
                "exists": target_folder(name).is_dir(),
            }
            for name in PAGE_FOLDERS
        ]
    ),
    width="stretch",
    hide_index=True,
)

st.divider()
st.subheader("Create a folder of your own")
custom_columns = st.columns([3, 1])
custom_name = custom_columns[0].text_input(
    "Subfolder name",
    value="",
    placeholder="microbeam_Kim_2026_08",
    help="Created below the output root. Use it to keep one sample's figures together.",
)
with custom_columns[1]:
    st.write("")
    st.write("")
    if st.button("Create subfolder", disabled=not custom_name.strip()):
        try:
            created = resolve_output_dir(output_root(), custom_name, create=True)
        except ExportError as exc:
            st.error(str(exc))
        else:
            st.success(f"Created {created}")
if custom_name.strip():
    st.code(str(Path(output_root()).expanduser() / safe_component(custom_name)), language=None)

st.divider()
st.subheader("What has been saved")
history = st.session_state.get(HISTORY_KEY, [])
if history:
    st.caption("Saved during this session, newest first.")
    st.code("\n".join(history[:15]), language=None)

if root.is_dir():
    rows = []
    for folder, _subfolders, names in os.walk(root):
        for name in names:
            item = Path(folder) / name
            try:
                stat = item.stat()
            except OSError:
                continue
            rows.append(
                {
                    "file": name,
                    "subfolder": str(Path(folder).relative_to(root)) or ".",
                    "size": human_size(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    "path": str(item),
                }
            )
            if len(rows) >= 2000:
                break
        if len(rows) >= 2000:
            break
    if rows:
        rows.sort(key=lambda entry: entry["modified"], reverse=True)
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption(f"{len(rows):,} file(s) below `{root}`.")
    else:
        st.info("The output folder is empty so far.")
else:
    st.info("The output folder has not been created yet.")
