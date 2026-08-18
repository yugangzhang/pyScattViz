"""Filename filtering and saved-frame selection without loading arrays."""

from __future__ import annotations

import posixpath
from pathlib import Path, PurePosixPath

import streamlit as st

from pyscattviz.app.components.scattering import (
    SCATTERING_PRODUCTS,
    discover_scattering_products,
    index_frames,
    index_remote_frames,
)
from pyscattviz.app.state import (
    prepare_persistent_widget,
    set_persistent_value,
    store_persistent_widget,
)
from pyscattviz.browser import list_directory, run_browser_command
from pyscattviz.data_sources import load_path_mappings, translate_remote_path
from pyscattviz.filters import FilterSyntaxError, parse_filename_list
from pyscattviz.globus import local_path_to_globus_path
from pyscattviz.globus_cli import (
    NSLS2_COLLECTION_ID,
    GlobusCLIError,
    find_globus_cli,
    find_personal_collections,
    globus_task_status,
    list_globus_directory,
    submit_file_transfer,
)

st.set_page_config(page_title="File Selection", page_icon="🔎", layout="wide")
st.title("🔎 File Selection")
st.caption("Filter filenames first; detector and q-space arrays remain unopened.")

st.session_state.setdefault("pyscattviz_path_mappings", load_path_mappings())
default_root = st.session_state.get("pyscattviz_active_root", "")
st.session_state.setdefault("pyscattviz_file_root", default_root)
initial_remote_root = str(st.session_state.get("pyscattviz_file_root", "")).startswith(
    "/nsls2/"
)
browser_start = (
    default_root
    if default_root and Path(default_root).expanduser().is_dir()
    else Path.home()
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


def _activate_local_cache(path: str) -> None:
    local_root = str(Path(path).expanduser().resolve(strict=False))
    set_persistent_value(st.session_state, "pyscattviz_file_root", local_root)
    st.session_state["pyscattviz_active_root"] = local_root
    st.session_state["pyscattviz_browser_cwd"] = local_root
    st.session_state.pop("pyscattviz_selection_table", None)
    st.session_state.pop("pyscattviz_selected_stems", None)


def _remote_cache_name(remote_root: str) -> str:
    parts = [part for part in PurePosixPath(remote_root).parts if part not in {"/", "Results"}]
    useful = parts[-2:] if len(parts) >= 2 else parts
    return "-".join(useful) or "nsls2-data"


def _render_remote_selection(remote_root: str) -> None:
    """Index a remote result folder and selectively transfer matching files."""

    focused_product = PurePosixPath(remote_root).name
    if focused_product in SCATTERING_PRODUCTS:
        dataset_root = str(PurePosixPath(remote_root).parent)
    else:
        focused_product = None
        dataset_root = remote_root
    st.info(
        "This is an NSLS2 Globus path. pyScattViz can scan its filenames online, "
        "but arrays must reach a local Globus Connect Personal cache before a viewer "
        "can open them. The complete proposal is never transferred."
    )
    executable = find_globus_cli()
    if not executable:
        st.error("Globus CLI was not found in this Python environment.")
        return
    source_collection_key = prepare_persistent_widget(
        st.session_state,
        "pyscattviz_file_source_collection",
        st.session_state.get("pyscattviz_globus_collection_id", NSLS2_COLLECTION_ID),
    )
    collection_id = st.text_input(
        "Source NSLS2 collection ID",
        key=source_collection_key,
        on_change=store_persistent_widget,
        args=(st.session_state, "pyscattviz_file_source_collection"),
    )

    product_state = st.session_state.get("pyscattviz_remote_products")
    if st.button("Find remote product folders", type="primary"):
        if focused_product:
            product_state = {"root": remote_root, "keys": [focused_product]}
            st.session_state["pyscattviz_remote_products"] = product_state
        else:
            try:
                root_rows = list_globus_directory(
                    dataset_root, collection_id=collection_id, executable=executable
                )
            except GlobusCLIError as exc:
                st.error(str(exc))
            else:
                folder_names = {
                    row["name"].rstrip("/") for row in root_rows if row["is_dir"]
                }
                available_keys = [
                    key for key in SCATTERING_PRODUCTS if key in folder_names
                ]
                product_state = {"root": remote_root, "keys": available_keys}
                st.session_state["pyscattviz_remote_products"] = product_state

    if not product_state or product_state.get("root") != remote_root:
        st.caption(
            "Paste or hand off a result root containing folders such as `q_image`, "
            "`qphi`, `cir_avg`, `qc`, or `stitched`, then find its product folders."
        )
        return
    available_keys = product_state["keys"]
    if not available_keys:
        st.error("No recognized scattering product folders were found remotely.")
        return

    if st.session_state.get("pyscattviz_remote_controls_root") != remote_root:
        set_persistent_value(
            st.session_state,
            "pyscattviz_remote_selected_products",
            available_keys,
        )
        st.session_state["pyscattviz_remote_controls_root"] = remote_root
    else:
        saved_products = st.session_state.get(
            "pyscattviz_remote_selected_products", available_keys
        )
        valid_products = [key for key in saved_products if key in available_keys]
        if valid_products != saved_products:
            set_persistent_value(
                st.session_state,
                "pyscattviz_remote_selected_products",
                valid_products,
            )
    selected_products_key = prepare_persistent_widget(
        st.session_state,
        "pyscattviz_remote_selected_products",
        available_keys,
    )
    selected_products = st.multiselect(
        "Remote products to index and transfer",
        available_keys,
        format_func=lambda key: SCATTERING_PRODUCTS[key]["label"],
        key=selected_products_key,
        on_change=store_persistent_widget,
        args=(st.session_state, "pyscattviz_remote_selected_products"),
    )
    left, right = st.columns(2)
    with left:
        remote_query_key = prepare_persistent_widget(
            st.session_state, "pyscattviz_remote_query", ""
        )
        query = st.text_input(
            "Boolean filename filter",
            placeholder="Kim AND (0.1000deg OR 0.1500deg) NOT AgBH",
            key=remote_query_key,
            on_change=store_persistent_widget,
            args=(st.session_state, "pyscattviz_remote_query"),
        )
    with right:
        remote_names_key = prepare_persistent_widget(
            st.session_state, "pyscattviz_remote_exact_names", ""
        )
        pasted = st.text_area(
            "Exact filename or stem list (optional)",
            height=110,
            key=remote_names_key,
            on_change=store_persistent_widget,
            args=(st.session_state, "pyscattviz_remote_exact_names"),
        )
        upload = st.file_uploader(
            "Load a .txt/.csv filename list",
            type=["txt", "csv"],
            key="pyscattviz_remote_upload",
        )
    uploaded_text = ""
    if upload is not None:
        try:
            uploaded_text = upload.getvalue().decode("utf-8-sig")
        except UnicodeDecodeError:
            st.error("The filename list must be UTF-8 text.")
    exact_names = parse_filename_list([pasted, uploaded_text])
    remote_max_key = prepare_persistent_widget(
        st.session_state, "pyscattviz_remote_max_frames", 5_000
    )
    max_frames = st.number_input(
        "Maximum matching remote frames",
        min_value=1,
        max_value=50_000,
        value=5_000,
        step=500,
        key=remote_max_key,
        on_change=store_persistent_widget,
        args=(st.session_state, "pyscattviz_remote_max_frames"),
    )

    if st.button(
        "Scan remote filenames",
        type="primary",
        disabled=not selected_products,
    ):
        try:
            with st.spinner("Reading remote filenames only …"):
                entries = {
                    key: list_globus_directory(
                        posixpath.join(dataset_root, key),
                        collection_id=collection_id,
                        executable=executable,
                    )
                    for key in selected_products
                }
                frame_table = index_remote_frames(
                    entries,
                    query=query,
                    filename_list=tuple(exact_names),
                    max_frames=int(max_frames),
                )
        except FilterSyntaxError as exc:
            st.error(f"Filter error: {exc}")
        except GlobusCLIError as exc:
            st.error(str(exc))
        else:
            st.session_state["pyscattviz_remote_selection_table"] = frame_table
            st.session_state["pyscattviz_remote_selection_root"] = remote_root

    frame_table = st.session_state.get("pyscattviz_remote_selection_table")
    if (
        frame_table is None
        or st.session_state.get("pyscattviz_remote_selection_root") != remote_root
    ):
        return
    scanned = frame_table.attrs.get("scanned_entries", 0)
    st.success(
        f"Selected {len(frame_table):,} remote frame(s) after scanning "
        f"{scanned:,} filenames. No arrays have been downloaded."
    )
    st.caption(
        "This path, filter, product choice, and scan table are saved while the GUI is "
        "running, so you can visit another page and return without rescanning."
    )
    display_columns = [
        column
        for column in (
            "stem",
            "th",
            "well",
            "timestamp",
            "has_raw",
            "has_qc",
            "has_qimg",
            "has_qphi",
            "has_cir",
        )
        if column in frame_table
    ]
    st.dataframe(frame_table[display_columns], width="stretch", hide_index=True)
    if frame_table.empty:
        st.warning("No remote files match the current filter.")
        return

    st.subheader("Transfer the selected frames to a local cache")
    st.caption(
        "Start Globus Connect Personal first. The two destination fields below must "
        "describe the same folder: once as Globus sees it and once as Windows/macOS/Linux "
        "sees it. You can confirm the collection path in Globus File Manager."
    )
    if st.button("Find my Globus Connect Personal collections"):
        try:
            st.session_state["pyscattviz_personal_collections"] = (
                find_personal_collections(executable)
            )
        except GlobusCLIError as exc:
            st.error(str(exc))
    personal = st.session_state.get("pyscattviz_personal_collections", [])
    selected_personal_id = ""
    if personal:
        personal_by_id = {item["id"]: item for item in personal}
        personal_ids = list(personal_by_id)
        if st.session_state.get("pyscattviz_personal_collection_id") not in personal_ids:
            set_persistent_value(
                st.session_state,
                "pyscattviz_personal_collection_id",
                personal_ids[0],
            )
        personal_collection_key = prepare_persistent_widget(
            st.session_state,
            "pyscattviz_personal_collection_id",
            personal_ids[0],
        )
        selected_personal_id = st.selectbox(
            "Personal destination collection",
            personal_ids,
            format_func=lambda collection_id: (
                f"{personal_by_id[collection_id]['display_name']} — {collection_id}"
                + (
                    " (offline)"
                    if personal_by_id[collection_id].get("connected") is False
                    else ""
                )
            ),
            key=personal_collection_key,
            on_change=store_persistent_widget,
            args=(st.session_state, "pyscattviz_personal_collection_id"),
        )
    manual_destination_key = prepare_persistent_widget(
        st.session_state, "pyscattviz_manual_destination_id", ""
    )
    manual_destination_id = st.text_input(
        "Or paste destination collection ID",
        placeholder="Collection UUID from Globus File Manager",
        key=manual_destination_key,
        on_change=store_persistent_widget,
        args=(st.session_state, "pyscattviz_manual_destination_id"),
    ).strip()
    destination_collection_id = manual_destination_id or selected_personal_id

    cache_name = _remote_cache_name(dataset_root)
    suggested_local_cache = Path.home() / "pyScattViz-data" / cache_name
    if st.session_state.get("pyscattviz_remote_cache_config_root") != dataset_root:
        set_persistent_value(
            st.session_state,
            "pyscattviz_local_cache_path",
            str(suggested_local_cache),
        )
        set_persistent_value(
            st.session_state,
            "pyscattviz_destination_collection_path",
            local_path_to_globus_path(suggested_local_cache),
        )
        st.session_state["pyscattviz_remote_cache_config_root"] = dataset_root
    local_cache_key = prepare_persistent_widget(
        st.session_state,
        "pyscattviz_local_cache_path",
        str(suggested_local_cache),
    )
    local_cache = st.text_input(
        "The same destination folder on this computer",
        key=local_cache_key,
        on_change=store_persistent_widget,
        args=(st.session_state, "pyscattviz_local_cache_path"),
        placeholder=r"C:\Users\yuzhang\pyScattViz-data\microbeam_Kim-giwaxs",
    )
    destination_folder_key = prepare_persistent_widget(
        st.session_state,
        "pyscattviz_destination_collection_path",
        local_path_to_globus_path(suggested_local_cache),
    )
    destination_folder = st.text_input(
        "Destination folder as shown in the personal Globus collection",
        key=destination_folder_key,
        on_change=store_persistent_widget,
        args=(st.session_state, "pyscattviz_destination_collection_path"),
        placeholder="/C/Users/yuzhang/pyScattViz-data/microbeam_Kim-giwaxs",
    )
    transfer_columns = ("raw", "qc", "qimg", "qphi", "cir")
    source_files = sorted(
        {
            str(value)
            for column in transfer_columns
            if column in frame_table
            for value in frame_table[column].dropna().tolist()
        }
    )
    st.caption(
        f"This task will transfer {len(source_files):,} files for the "
        f"{len(frame_table):,} matching frames."
    )
    if st.button(
        "Start selective Globus transfer",
        type="primary",
        disabled=not destination_collection_id or not destination_folder or not local_cache,
    ):
        normalized_destination = "/" + destination_folder.strip().strip("/")
        path_pairs = [
            (
                source,
                posixpath.join(
                    normalized_destination,
                    posixpath.relpath(source, dataset_root),
                ),
            )
            for source in source_files
        ]
        try:
            task_id = submit_file_transfer(
                collection_id,
                destination_collection_id,
                path_pairs,
                executable=executable,
            )
        except GlobusCLIError as exc:
            st.error(str(exc))
        else:
            st.session_state["pyscattviz_transfer_task"] = {
                "id": task_id,
                "local_root": local_cache,
                "remote_root": remote_root,
                "status": "SUBMITTED",
            }

    task = st.session_state.get("pyscattviz_transfer_task")
    if task and task.get("remote_root") == remote_root:
        st.code(f"Globus task: {task['id']}", language=None)
        if st.button("Check transfer status"):
            try:
                details = globus_task_status(task["id"], executable=executable)
            except GlobusCLIError as exc:
                st.error(str(exc))
            else:
                task["status"] = str(details.get("status") or "UNKNOWN").upper()
                task["details"] = details
        status = task.get("status", "SUBMITTED")
        if status == "SUCCEEDED":
            local_path = Path(task["local_root"]).expanduser()
            if local_path.is_dir():
                st.success("Globus transfer succeeded and the local cache is available.")
                if st.button("Open transferred files in File Selection", type="primary"):
                    _activate_local_cache(str(local_path))
                    st.rerun()
            else:
                st.warning(
                    "Globus reports success, but the local cache path is not visible to "
                    "pyScattViz. Check that the Globus destination path and local folder "
                    "refer to the same place."
                )
        elif status in {"FAILED", "INACTIVE"}:
            st.error(f"Globus transfer status: {status}")
        else:
            st.info(f"Globus transfer status: {status}. Check again in a moment.")


with st.expander(
    "📁 Browse local/mounted folders or use pwd / ls / cd / du",
    expanded=not initial_remote_root,
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
            {key: row[key] for key in ("name", "type", "size", "modified")}
            for row in rows
        ]
        st.dataframe(display_rows, width="stretch", hide_index=True)
        folders = [row for row in rows if row["is_dir"]]
        if folders:
            selected_folder = st.selectbox(
                "Subfolder",
                folders,
                format_func=lambda row: row["name"],
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
    placeholder="/nsls2/data/.../Results/giwaxs or Z:\\...\\Results\\giwaxs",
    help=(
        "Paste an original /nsls2 Globus path, a local folder, or a mapped-drive path. "
        "Remote Globus paths are indexed by filename and selectively transferred here."
    ),
)
effective_root, active_mapping = translate_remote_path(
    root_input, st.session_state["pyscattviz_path_mappings"]
)
effective_path_available = Path(effective_root).expanduser().is_dir()
unavailable_mapping = bool(active_mapping and not effective_path_available)
is_remote_globus = root_input.startswith("/nsls2/") and (
    not active_mapping or unavailable_mapping
)
if root_input and not is_remote_globus:
    st.session_state["pyscattviz_active_root"] = str(
        Path(effective_root).expanduser().resolve(strict=False)
    )
if active_mapping and effective_path_available:
    st.info(
        f"Remote path mapped through `{active_mapping['remote_root']}` to "
        f"`{effective_root}`."
    )
elif unavailable_mapping:
    st.warning(
        f"The saved mapping `{active_mapping['remote_root']}` → "
        f"`{active_mapping['local_root']}` was ignored because `{effective_root}` "
        "is not available on this computer. Remote Globus browsing will be used. "
        "You can remove the old mapping under Globus & Data Sources → Local folders."
    )

if is_remote_globus:
    _render_remote_selection(root_input.rstrip("/"))
    st.stop()

if not root_input or not effective_path_available:
    st.info("Select an available result folder to start.")
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
)

left, right = st.columns(2)
with left:
    query = st.text_input(
        "Boolean filename filter",
        placeholder="Kim AND (0.1000deg OR 0.1500deg) NOT AgBH",
        help=(
            "AND, OR, NOT, parentheses, quoted phrases, and wildcards are supported. "
            "Adjacent terms imply AND."
        ),
    )
with right:
    pasted = st.text_area(
        "Exact filename or stem list (optional)",
        height=110,
        placeholder="One filename per line, or a comma-separated list",
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
    st.info("The saved selection is now available in both scattering viewers.")
