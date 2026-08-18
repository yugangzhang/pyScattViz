"""Primary NSLS-II Globus workflow and local-folder registration."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

import streamlit as st

from pyscattviz.data_sources import load_path_mappings, save_path_mappings
from pyscattviz.globus import (
    BNL_GLOBUS_GUIDE,
    GLOBUS_FILE_MANAGER,
    NSLS2_GLOBUS_GUIDE,
    default_cache,
    globus_file_manager_url,
    proposal_path,
)
from pyscattviz.globus_cli import (
    NSLS2_COLLECTION_ID,
    TRANSFER_ALL_SCOPE,
    GlobusCLIError,
    GlobusConsentRequired,
    collection_data_access_scope,
    find_current_nsls2_collection,
    find_globus_cli,
    globus_identity,
    list_globus_directory,
)

st.set_page_config(page_title="Globus & Data Sources", page_icon="🌐", layout="wide")
st.title("🌐 Globus & Data Sources")
st.caption("Browse the NSLS2 collection online, or register a mounted/local data folder.")

st.session_state.setdefault("pyscattviz_path_mappings", load_path_mappings())
globus_tab, cli_tab, local_tab = st.tabs(
    ["Globus online / transfer", "Globus CLI browser", "Local folders"]
)

with globus_tab:
    st.markdown(
        """
Globus File Manager can browse the proposal without downloading it. When data
must be opened in pyScattViz, transfer only the required result folders, or use
a network/mounted folder that appears as a normal path on this computer.

1. Connect to the BNL campus network or VPN when required by the local setup.
2. Install and start **Globus Connect Personal** on the destination computer.
3. Sign in to Globus with **Brookhaven National Laboratory** and BNL Domain credentials.
4. Search Collections for **NSLS2** with all collection filters unchecked.
5. Paste the proposal path below into the NSLS2 side of File Manager.
6. Select the personal collection and start a transfer into the local cache.
"""
    )

    c1, c2, c3 = st.columns([1, 1, 1])
    beamline = c1.selectbox("Beamline", ["CMS", "SMI"])
    cycle = c2.text_input("Cycle", value="2026-2", placeholder="2026-2")
    proposal = c3.text_input("Six-digit proposal", placeholder="123456")

    remote_path = ""
    if proposal:
        try:
            remote_path = proposal_path(beamline, cycle, proposal)
            st.markdown("**NSLS2 collection path**")
            st.code(remote_path, language=None)
            st.link_button(
                "Browse this proposal in Globus (no transfer)",
                globus_file_manager_url(remote_path),
                type="primary",
            )
            st.caption(
                "If Globus asks for a collection, select **NSLS2**, then paste the path "
                "shown above. Browsing alone does not download the proposal."
            )
            suggested = str(default_cache(proposal))
        except ValueError as exc:
            st.error(str(exc))
            suggested = str(default_cache(""))
    else:
        suggested = str(default_cache(""))

    destination = st.text_input(
        "Local destination folder",
        value=st.session_state.get("pyscattviz_cache", suggested),
        help="Globus Connect Personal must permit access to this folder.",
    )
    if st.button("Save transferred folder", disabled=not destination):
        resolved = str(Path(destination).expanduser().resolve(strict=False))
        st.session_state["pyscattviz_cache"] = resolved
        st.session_state["pyscattviz_active_root"] = resolved
        roots = st.session_state.setdefault("pyscattviz_roots", [])
        if resolved not in roots:
            roots.append(resolved)
        st.success(f"Active local folder: {resolved}")

    link1, link2, link3 = st.columns(3)
    link1.link_button("Open Globus File Manager", GLOBUS_FILE_MANAGER)
    link2.link_button("NSLS-II Globus guide", NSLS2_GLOBUS_GUIDE)
    link3.link_button("BNL illustrated guide", BNL_GLOBUS_GUIDE)

    st.info(
        "A Globus path such as /nsls2/data/... is a remote reference, not a Windows "
        "or local filesystem path. The Globus CLI browser can list it without a transfer; "
        "loading arrays still requires selective transfer into a local cache."
    )

def _select_globus_path(path: str) -> None:
    st.session_state["pyscattviz_globus_path"] = path
    st.session_state["pyscattviz_globus_auto_browse"] = True


def _retry_globus_listing() -> None:
    st.session_state["pyscattviz_globus_auto_browse"] = True


def _prepare_remote_file_selection(path: str) -> None:
    """Hand off a remote root without retaining an unrelated local selection."""

    st.session_state["pyscattviz_file_root"] = path
    for key in (
        "pyscattviz_active_root",
        "pyscattviz_selection_table",
        "pyscattviz_selected_stems",
        "pyscattviz_selected_root",
        "pyscattviz_selected_products",
    ):
        st.session_state.pop(key, None)


with cli_tab:
    st.markdown(
        """
This browser uses the Globus CLI login already completed in PowerShell. It can
list NSLS-II folders without SSHFS, a Windows drive, or a bulk transfer. The BNL
login and Duo tokens remain in Globus CLI's own local credential store.
"""
    )
    cli_display_command = (
        ".\\.venv\\Scripts\\globus.exe" if os.name == "nt" else "./.venv/bin/globus"
    )
    shell_language = "powershell" if os.name == "nt" else "bash"
    st.markdown("**One-time Globus CLI login**")
    st.code(
        f"{cli_display_command} login",
        language=shell_language,
    )

    cli_executable = find_globus_cli()
    if cli_executable:
        st.success(f"Globus CLI found: `{cli_executable}`")
    else:
        st.error(
            "Globus CLI was not found in this environment. Reinstall pyScattViz with "
            "`.\\.venv\\Scripts\\python.exe -m pip install --upgrade .`, then log in."
        )

    if st.button("Check Globus login", disabled=not cli_executable):
        try:
            identity = globus_identity(cli_executable)
        except GlobusCLIError as exc:
            st.error(str(exc))
        else:
            st.session_state["pyscattviz_globus_identity"] = identity
    if st.session_state.get("pyscattviz_globus_identity"):
        st.success(f"Logged in as {st.session_state['pyscattviz_globus_identity']}")

    st.markdown("**Active NSLS2 collection**")
    st.session_state.setdefault("pyscattviz_globus_collection_id", NSLS2_COLLECTION_ID)
    if st.button("Refresh current NSLS2 collection ID", disabled=not cli_executable):
        try:
            current_collection = find_current_nsls2_collection(cli_executable)
        except GlobusCLIError as exc:
            st.error(str(exc))
        else:
            st.session_state["pyscattviz_globus_collection_id"] = current_collection
            st.success(f"Current NSLS2 collection: {current_collection}")
    collection_id = st.text_input(
        "Collection ID",
        key="pyscattviz_globus_collection_id",
        help="Editable in case NSLS-II replaces its Globus collection in the future.",
    )
    st.caption("The retired `88c7648d-...` collection is intentionally not used.")

    st.session_state.setdefault(
        "pyscattviz_globus_path",
        remote_path or "/nsls2/data/smi/proposals",
    )
    remote_browser_path = st.text_input(
        "Remote NSLS-II folder",
        key="pyscattviz_globus_path",
        placeholder="/nsls2/data/smi/proposals/2026-2/pass-319371/projects",
    )
    if remote_path:
        st.button(
            "Use proposal path from the first tab",
            on_click=_select_globus_path,
            args=(remote_path,),
        )

    browse_requested = st.button(
        "List remote folder",
        type="primary",
        disabled=not cli_executable,
    )
    browse_requested = browse_requested or st.session_state.pop(
        "pyscattviz_globus_auto_browse", False
    )
    if browse_requested and cli_executable:
        try:
            remote_rows = list_globus_directory(
                remote_browser_path,
                collection_id=collection_id,
                executable=cli_executable,
            )
        except GlobusConsentRequired as exc:
            st.session_state["pyscattviz_globus_listing"] = {
                "path": remote_browser_path,
                "rows": [],
                "error": None,
                "consent_required": str(exc),
                "required_scopes": exc.required_scopes
                or (
                    TRANSFER_ALL_SCOPE,
                    collection_data_access_scope(collection_id),
                ),
            }
        except GlobusCLIError as exc:
            st.session_state["pyscattviz_globus_listing"] = {
                "path": remote_browser_path,
                "rows": [],
                "error": str(exc),
                "consent_required": None,
                "required_scopes": (),
            }
        else:
            st.session_state["pyscattviz_globus_listing"] = {
                "path": remote_browser_path,
                "rows": remote_rows,
                "error": None,
                "consent_required": None,
                "required_scopes": (),
            }

    remote_listing = st.session_state.get("pyscattviz_globus_listing")
    if remote_listing:
        if remote_listing.get("consent_required"):
            st.warning(remote_listing["consent_required"])
            st.markdown(
                "Run this once in a separate terminal. A browser will open for BNL "
                "approval/Duo:"
            )
            consent_scopes = remote_listing.get("required_scopes") or (
                TRANSFER_ALL_SCOPE,
                collection_data_access_scope(collection_id),
            )
            quoted_scopes = " ".join(f'"{scope}"' for scope in consent_scopes)
            st.code(
                f"{cli_display_command} session consent {quoted_scopes}",
                language=shell_language,
            )
            st.caption(
                "After Globus reports that the CLI session was updated, return here and "
                "retry. The running GUI does not need to be restarted."
            )
            st.button(
                "Retry remote listing after consent",
                type="primary",
                on_click=_retry_globus_listing,
            )
        elif remote_listing["error"]:
            st.error(remote_listing["error"])
        else:
            st.success(
                f"Found {len(remote_listing['rows']):,} entries in "
                f"{remote_listing['path']}"
            )
            display_rows = [
                {
                    key: row[key]
                    for key in ("name", "type", "size", "modified")
                }
                for row in remote_listing["rows"]
            ]
            st.dataframe(display_rows, width="stretch", hide_index=True)
            folders = [row for row in remote_listing["rows"] if row["is_dir"]]
            if folders:
                selected_remote_folder = st.selectbox(
                    "Remote subfolder",
                    folders,
                    format_func=lambda row: row["name"],
                )
                folder_left, folder_right = st.columns(2)
                folder_left.button(
                    "Open selected remote subfolder",
                    on_click=_select_globus_path,
                    args=(selected_remote_folder["path"],),
                    use_container_width=True,
                )
                if folder_right.button(
                    "Use selected folder in File Selection",
                    type="primary",
                    use_container_width=True,
                ):
                    _prepare_remote_file_selection(selected_remote_folder["path"])
                    st.switch_page("pages/2_File_Selection.py")

    parent_path = str(PurePosixPath(remote_browser_path).parent)
    st.button(
        "↑ Remote parent folder",
        on_click=_select_globus_path,
        args=(parent_path,),
        disabled=remote_browser_path == "/",
    )
    if st.button(
        "Use current remote folder in File Selection",
        type="primary",
        disabled=not remote_browser_path.startswith("/nsls2/"),
    ):
        _prepare_remote_file_selection(remote_browser_path)
        st.switch_page("pages/2_File_Selection.py")
    st.info(
        "Use either File Selection button after reaching a result folder. File Selection "
        "indexes remote names, then transfers only the matching frame files into a local "
        "cache; Globus is not a filesystem mount."
    )

with local_tab:
    st.markdown(
        "Use this tab for a local disk, external disk, SMB share, or a mounted remote "
        "folder. On Windows, a mapped network drive typically looks like `Z:\\\\...`."
    )
    existing = st.session_state.get("pyscattviz_roots", [])
    paths_text = st.text_area(
        "Folder paths (one per line)",
        value="\n".join(existing),
        height=180,
        placeholder="/path/to/pass-123456/projects/sample/Results/giwaxs",
    )
    if st.button("Save folder list"):
        roots = []
        for line in paths_text.splitlines():
            if line.strip():
                value = str(Path(line.strip()).expanduser().resolve(strict=False))
                if value not in roots:
                    roots.append(value)
        st.session_state["pyscattviz_roots"] = roots
        if roots:
            st.session_state["pyscattviz_active_root"] = roots[0]
        st.success(f"Saved {len(roots)} folder(s).")

    roots = st.session_state.get("pyscattviz_roots", [])
    if roots:
        active = st.selectbox(
            "Active folder",
            roots,
            index=(
                roots.index(st.session_state.get("pyscattviz_active_root"))
                if st.session_state.get("pyscattviz_active_root") in roots
                else 0
            ),
        )
        st.session_state["pyscattviz_active_root"] = active
        if Path(active).is_dir():
            st.success("Folder is available on this computer.")
        else:
            st.info("Folder is saved but is not currently available.")

    mappings = st.session_state["pyscattviz_path_mappings"]
    if mappings:
        with st.expander("Remove an old mounted-drive path mapping"):
            st.caption(
                "These mappings are retained for real institutional/network mounts. "
                "Remove the failed SSHFS-Win mapping if `Z:\\` was never created."
            )
            st.dataframe(mappings, width="stretch", hide_index=True)
            remove_mapping = st.selectbox(
                "Mapping to remove",
                mappings,
                format_func=lambda item: (
                    f"{item['remote_root']}  →  {item['local_root']}"
                ),
            )
            if st.button("Remove selected mapping"):
                remaining = [item for item in mappings if item != remove_mapping]
                try:
                    save_path_mappings(remaining)
                except OSError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["pyscattviz_path_mappings"] = remaining
                    st.rerun()
