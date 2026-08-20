"""Filename filtering and saved-frame selection without loading arrays."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from pyscattviz.app.components.datasource import ensure_remembered_folders, remember_folder
from pyscattviz.app.components.saving import render_save_panel
from pyscattviz.app.components.scattering import (
    SCATTERING_PRODUCTS,
    discover_scattering_products,
    index_frames,
)
from pyscattviz.app.state import (
    keep_widget_state,
    prepare_persistent_widget,
    set_persistent_value,
    store_persistent_widget,
)
from pyscattviz.browser import list_directory, run_browser_command
from pyscattviz.data_sources import load_path_mappings, translate_remote_path
from pyscattviz.filters import FilterSyntaxError, parse_filename_list

TAB_NAME = "File Selection"

st.set_page_config(page_title="File Selection", page_icon="🔎", layout="wide")

# Streamlit forgets a page's widgets as soon as another page is opened. Keep them.
keep_widget_state(st.session_state)
ensure_remembered_folders()
st.title("🔎 File Selection")
st.caption("Filter filenames first; detector and q-space arrays remain unopened.")

st.session_state.setdefault("pyscattviz_path_mappings", load_path_mappings())
default_root = st.session_state.get("pyscattviz_active_root", "")
st.session_state.setdefault("pyscattviz_file_root", default_root)
browser_start = (
    default_root if default_root and Path(default_root).expanduser().is_dir() else Path.home()
)
st.session_state.setdefault("pyscattviz_browser_cwd", str(browser_start))


def _browse_to(path: str) -> None:
    result = run_browser_command(
        f'cd "{path}"',
        st.session_state["pyscattviz_browser_cwd"],
        st.session_state["pyscattviz_path_mappings"],
    )
    st.session_state["pyscattviz_browser_result"] = result
    if not result["error"]:
        st.session_state["pyscattviz_browser_cwd"] = result["cwd"]


with st.expander(
    "📁 Browse local/mounted folders or use pwd / ls / cd / du",
    expanded=True,
):
    browser_cwd = st.session_state["pyscattviz_browser_cwd"]
    st.markdown("**Current folder**")
    st.code(browser_cwd, language=None)

    command = st.text_input(
        "Folder command",
        value="ls",
        placeholder='cd projects or ls "folder with spaces"',
        help=(
            "Supported read-only commands: pwd, ls [path], cd <path>, du [path]. "
            "du is capped at 5,000 files so a large network tree cannot scan forever."
        ),
        key="fs_command",
    )
    if st.button("Run command"):
        result = run_browser_command(
            command, browser_cwd, st.session_state["pyscattviz_path_mappings"]
        )
        st.session_state["pyscattviz_browser_result"] = result
        if not result["error"]:
            st.session_state["pyscattviz_browser_cwd"] = result["cwd"]
            if result["cwd"] != browser_cwd:
                st.rerun()

    result = st.session_state.get("pyscattviz_browser_result")
    if result is None:
        try:
            rows, truncated = list_directory(browser_cwd)
            result = {
                "cwd": browser_cwd,
                "output": browser_cwd + (" (first 500 entries)" if truncated else ""),
                "rows": rows,
                "error": None,
            }
        except OSError as exc:
            result = {"cwd": browser_cwd, "output": "", "rows": [], "error": str(exc)}

    if result["error"]:
        st.error(result["error"])
    elif result["output"]:
        st.code(result["output"], language=None)

    rows = result["rows"]
    if rows:
        display_rows = [
            {key: row[key] for key in ("name", "type", "size", "modified")} for row in rows
        ]
        st.dataframe(display_rows, width="stretch", hide_index=True)
        folders = [row for row in rows if row["is_dir"]]
        if folders:
            selected_folder = st.selectbox(
                "Subfolder", folders, format_func=lambda row: row["name"], key="fs_subfolder"
            )
            st.button(
                "Open selected subfolder",
                on_click=_browse_to,
                args=(selected_folder["path"],),
            )

    nav_left, nav_right = st.columns(2)
    nav_left.button(
        "↑ Parent folder",
        on_click=_browse_to,
        args=(str(Path(st.session_state["pyscattviz_browser_cwd"]).parent),),
        use_container_width=True,
    )
    if nav_right.button("Use current folder", type="primary", use_container_width=True):
        set_persistent_value(
            st.session_state,
            "pyscattviz_file_root",
            st.session_state["pyscattviz_browser_cwd"],
        )

file_root_widget_key = prepare_persistent_widget(
    st.session_state,
    "pyscattviz_file_root",
    default_root,
)
root_input = st.text_input(
    "Result folder",
    key=file_root_widget_key,
    on_change=store_persistent_widget,
    args=(st.session_state, "pyscattviz_file_root"),
    placeholder=r"Z:\projects\sample\Results\giwaxs or /mounted/Results/giwaxs",
    help=(
        "Use a local or mounted filesystem path. An original /nsls2 path works only "
        "after its mount mapping is registered under Data Sources & Mounts."
    ),
)
effective_root, active_mapping = translate_remote_path(
    root_input, st.session_state["pyscattviz_path_mappings"]
)
effective_path_available = Path(effective_root).expanduser().is_dir()
unavailable_mapping = bool(active_mapping and not effective_path_available)
unmounted_remote = root_input.startswith("/nsls2/") and (not active_mapping or unavailable_mapping)

if root_input and not unmounted_remote:
    st.session_state["pyscattviz_active_root"] = str(
        Path(effective_root).expanduser().resolve(strict=False)
    )
    remember_folder(st.session_state["pyscattviz_active_root"])
if active_mapping and effective_path_available:
    st.info(f"Remote path mapped through `{active_mapping['remote_root']}` to `{effective_root}`.")
elif unmounted_remote:
    detail = ""
    if unavailable_mapping:
        detail = f" The saved mapping points to unavailable folder `{effective_root}`."
    st.warning(
        "This `/nsls2` path is not mounted on this computer. Open Data Sources & "
        "Mounts, complete the SFTP mount in a terminal/Desktop client, test it, and "
        f"register the mounted path.{detail}"
    )
    st.stop()

if not root_input or not effective_path_available:
    st.info("Select an available local or mounted result folder to start.")
    st.stop()

normalized_root, available, _focused = discover_scattering_products(effective_root)
if not available:
    st.error("No cir_avg, q_image, qphi, qc, or stitched product folders were found.")
    st.stop()

available_keys = [item["key"] for item in available]
selected_products = st.multiselect(
    "Products to index",
    available_keys,
    default=available_keys,
    format_func=lambda key: SCATTERING_PRODUCTS[key]["label"],
    key="fs_products",
)

left, right = st.columns(2)
with left:
    query = st.text_input(
        "Boolean filename filter",
        placeholder="sampleA AND (0.1000deg OR 0.1500deg) NOT AgBH",
        help=(
            "AND, OR, NOT, parentheses, quoted phrases, and wildcards are supported. "
            "Adjacent terms imply AND."
        ),
        key="fs_query",
    )
with right:
    pasted = st.text_area(
        "Exact filename or stem list (optional)",
        height=110,
        placeholder="One filename per line, or a comma-separated list",
        key="fs_pasted",
    )
    upload = st.file_uploader("Load a .txt/.csv filename list", type=["txt", "csv"])

uploaded_text = ""
if upload is not None:
    try:
        uploaded_text = upload.getvalue().decode("utf-8-sig")
    except UnicodeDecodeError:
        st.error("The filename list must be UTF-8 text.")

exact_names = parse_filename_list([pasted, uploaded_text])
max_frames = st.number_input(
    "Maximum matching frames kept in memory",
    min_value=1,
    max_value=50_000,
    value=5_000,
    step=500,
    key="fs_max_frames",
)

if st.button("Scan filenames", type="primary", disabled=not selected_products):
    try:
        with st.spinner("Scanning names only …"):
            frame_table = index_frames(
                normalized_root,
                product_keys=tuple(selected_products),
                query=query,
                filename_list=tuple(exact_names),
                max_frames=int(max_frames),
            )
    except FilterSyntaxError as exc:
        st.error(f"Filter error: {exc}")
    else:
        st.session_state["pyscattviz_selection_table"] = frame_table
        st.session_state["pyscattviz_selected_stems"] = tuple(frame_table["stem"].tolist())
        st.session_state["pyscattviz_selected_root"] = normalized_root
        st.session_state["pyscattviz_selected_products"] = tuple(selected_products)

frame_table = st.session_state.get("pyscattviz_selection_table")
selected_root = st.session_state.get("pyscattviz_selected_root")
if frame_table is not None and selected_root == normalized_root:
    scanned = frame_table.attrs.get("scanned_entries", 0)
    st.success(f"Selected {len(frame_table):,} frame(s) after scanning {scanned:,} names.")
    if frame_table.attrs.get("truncated"):
        st.warning(
            f"The match reached the {frame_table.attrs.get('max_frames'):,}-frame cap. "
            "Add a more specific filter or raise the cap."
        )
    display_columns = [
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
    display_columns = [column for column in display_columns if column in frame_table]
    st.dataframe(frame_table[display_columns], width="stretch", hide_index=True)
    text_export = "\n".join(frame_table["stem"].tolist())
    st.download_button(
        "Download selected filename list",
        text_export,
        file_name="pyscattviz_selected_frames.txt",
        mime="text/plain",
    )
    render_save_panel(
        TAB_NAME,
        f"selection_{Path(normalized_root).name}",
        key="file_selection_save",
        table=frame_table[display_columns],
        text=text_export,
        caption=(
            "Keep the exact frame list that produced a figure — the table records "
            "which products each frame has, the plain list feeds a later session."
        ),
    )
    basket_columns = st.columns([1.4, 3])
    if basket_columns[0].button("Add these files to the dataset basket"):
        basket = list(st.session_state.get("pyscattviz_dataset_paths", []))
        added = 0
        for column in ("cir", "qimg", "qphi", "qc", "raw"):
            if column not in frame_table:
                continue
            for value in frame_table[column].dropna().tolist():
                if value not in basket:
                    basket.append(str(value))
                    added += 1
        st.session_state["pyscattviz_dataset_paths"] = basket
        st.success(f"Added {added} file path(s); Quick Plot reads the basket directly.")
    basket_columns[1].caption(
        "The saved selection is already available in every scattering viewer."
    )
