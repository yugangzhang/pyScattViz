"""Cross-platform NSLS-II SFTP mount setup and local-folder registration."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

from pyscattviz.app.state import prepare_persistent_widget, store_persistent_widget
from pyscattviz.data_sources import (
    add_path_mapping,
    load_path_mappings,
    save_path_mappings,
)
from pyscattviz.mounts import (
    RAIDRIVE_URL,
    RAIDRIVE_WINGET_ID,
    SFTP_HOST,
    SFTP_HOST_KEY_FINGERPRINT,
    make_mount_folder_command,
    mount_remote_path,
    sftp_test_command,
    sshfs_mount_command,
    suggested_mount_folder,
    unmount_command,
)

st.set_page_config(page_title="Data Sources & Mounts", page_icon="🗂️", layout="wide")
st.title("🗂️ Data Sources & Mounts")
st.caption("Mount NSLS-II data on demand, then register the mounted/local folder.")

st.session_state.setdefault("pyscattviz_path_mappings", load_path_mappings())

scope_key = prepare_persistent_widget(
    st.session_state, "pyscattviz_mount_scope", "Proposal"
)
scope = st.selectbox(
    "Remote mount scope",
    ["Proposal", "Beamline proposals", "NSLS-II data", "Custom"],
    key=scope_key,
    on_change=store_persistent_widget,
    args=(st.session_state, "pyscattviz_mount_scope"),
    help=(
        "Proposal is safest and fastest. A broader root is convenient for users who "
        "work across proposals, but it exposes more directory names in the mounted drive."
    ),
)

top1, top2, top3, top4 = st.columns([1, 1, 1, 1])
beamline_key = prepare_persistent_widget(
    st.session_state, "pyscattviz_mount_beamline", "SMI"
)
beamline = top1.selectbox(
    "Beamline",
    ["SMI", "CMS"],
    key=beamline_key,
    on_change=store_persistent_widget,
    args=(st.session_state, "pyscattviz_mount_beamline"),
)
cycle_key = prepare_persistent_widget(
    st.session_state, "pyscattviz_mount_cycle", "2026-2"
)
cycle = top2.text_input(
    "Cycle",
    key=cycle_key,
    on_change=store_persistent_widget,
    args=(st.session_state, "pyscattviz_mount_cycle"),
    placeholder="2026-2",
)
proposal_key = prepare_persistent_widget(
    st.session_state, "pyscattviz_mount_proposal", ""
)
proposal = top3.text_input(
    "Six-digit proposal",
    key=proposal_key,
    on_change=store_persistent_widget,
    args=(st.session_state, "pyscattviz_mount_proposal"),
    placeholder="319371",
)
username_key = prepare_persistent_widget(
    st.session_state, "pyscattviz_mount_username", ""
)
username = top4.text_input(
    "BNL username",
    key=username_key,
    on_change=store_persistent_widget,
    args=(st.session_state, "pyscattviz_mount_username"),
    placeholder="yuzhang",
)

custom_path = ""
if scope == "Custom":
    custom_key = prepare_persistent_widget(
        st.session_state, "pyscattviz_mount_custom_path", "/nsls2/data"
    )
    custom_path = st.text_input(
        "Custom NSLS-II folder",
        key=custom_key,
        on_change=store_persistent_widget,
        args=(st.session_state, "pyscattviz_mount_custom_path"),
        placeholder="/nsls2/data/smi/proposals",
    )

remote_root = ""
try:
    remote_root = mount_remote_path(scope, beamline, cycle, proposal, custom_path)
except ValueError as exc:
    if scope != "Proposal" or proposal:
        st.error(str(exc))
else:
    st.markdown("**Remote folder to mount**")
    st.code(remote_root, language=None)

mount_tab, folders_tab = st.tabs(["Mount setup", "Mounted / local folders"])

with mount_tab:
    st.info(
        "BNL password and Duo prompts require an interactive terminal or a desktop "
        "SFTP-mount application. pyScattViz does not request, receive, or store those "
        "credentials. After mounting, return here to test and register the local path."
    )

    if sys.platform.startswith("win"):
        detected_platform = "Windows"
    elif sys.platform == "darwin":
        detected_platform = "macOS"
    else:
        detected_platform = "Linux"
    platform_key = prepare_persistent_widget(
        st.session_state, "pyscattviz_mount_platform", detected_platform
    )
    platform_name = st.selectbox(
        "Instructions for",
        ["Windows", "Linux", "macOS"],
        key=platform_key,
        on_change=store_persistent_widget,
        args=(st.session_state, "pyscattviz_mount_platform"),
    )

    if platform_name == "Windows":
        st.subheader("Windows: RaiDrive SFTP mount")
        st.success(
            "RaiDrive has been verified with the NSLS-II SFTP server, BNL password, "
            "Duo Push, and a mounted Windows drive such as Z:."
        )
        st.markdown(
            "Install the free RaiDrive edition from PowerShell or download it from "
            "the official site. pyScattViz needs read access only."
        )
        st.code(
            f"winget install --exact --id {RAIDRIVE_WINGET_ID}",
            language="powershell",
        )
        st.link_button("Download RaiDrive for Windows", RAIDRIVE_URL)
        st.markdown(
            """
In RaiDrive, add a new **SFTP** storage connection with these settings:

- **Type:** SFTP
- **Address:** `sftp.nsls2.bnl.gov`
- **Port:** `22`
- **Username:** your BNL username
- **Path:** the remote folder shown above
- **Drive letter:** `Z:` or any available letter
- **Access:** read-only when that option is available

Connect, complete the BNL password and Duo Push prompts, and confirm the mounted
drive in Windows File Explorer. If a host-key dialog appears, verify the
fingerprint below.
"""
        )
        st.code(SFTP_HOST_KEY_FINGERPRINT, language=None)
        if username:
            st.markdown("**PowerShell connectivity test**")
            st.code(sftp_test_command(username), language="powershell")
        suggested_local = "Z:\\"
        st.warning(
            "The mounted account may have write permission. Use read-only mode when "
            "possible and do not rename, move, or delete proposal data during review. "
            "The File Selection command bar itself provides read-only commands only."
        )
    else:
        st.subheader(f"{platform_name}: SSHFS mount")
        if platform_name == "Linux":
            st.markdown("Install SSHFS using the command for the Linux distribution:")
            st.code(
                "sudo apt update && sudo apt install sshfs\n"
                "# Fedora/RHEL alternative:\n"
                "sudo dnf install fuse-sshfs",
                language="bash",
            )
        else:
            st.markdown(
                "Install macFUSE and the maintained SSHFS formula. macOS may request "
                "approval of the system extension under Privacy & Security."
            )
            st.code(
                "brew install --cask macfuse\n"
                "brew install gromgit/fuse/sshfs-mac",
                language="bash",
            )
        suggested_local = str(
            suggested_mount_folder(beamline, proposal, scope, custom_path)
        )

    mount_path_name = f"pyscattviz_mount_path_{platform_name.lower()}"
    suggestion_key = f"{mount_path_name}__suggested"
    previous_suggestion = st.session_state.get(suggestion_key)
    if (
        mount_path_name not in st.session_state
        or st.session_state[mount_path_name] == previous_suggestion
    ):
        st.session_state[mount_path_name] = suggested_local
    st.session_state[suggestion_key] = suggested_local
    mount_path_key = prepare_persistent_widget(
        st.session_state, mount_path_name, suggested_local
    )
    local_mount = st.text_input(
        "Mounted path on this computer",
        key=mount_path_key,
        on_change=store_persistent_widget,
        args=(st.session_state, mount_path_name),
        placeholder=(
            "Z:\\"
            if platform_name == "Windows"
            else str(Path.home() / "NSLS_II_Link" / "smi-pass-319371")
        ),
    )

    if platform_name in {"Linux", "macOS"} and remote_root and username and local_mount:
        st.markdown("**Run in a terminal**")
        st.code(
            make_mount_folder_command(local_mount)
            + "\n"
            + sshfs_mount_command(username, remote_root, local_mount),
            language="bash",
        )
        st.caption(
            "Use the copy icon and paste both lines into a terminal. If this is the "
            "first connection, verify the host fingerprint shown below. Enter the BNL "
            "password, choose Duo option 1, and approve the push."
        )
        st.code(SFTP_HOST_KEY_FINGERPRINT, language=None)
        st.markdown("**Unmount later**")
        st.code(
            unmount_command(local_mount, platform_name),
            language="bash",
        )
    elif not remote_root or not username:
        st.caption("Enter the proposal and BNL username to generate the exact mount command.")

    test_left, save_right = st.columns(2)
    test_requested = test_left.button(
        "Test mounted path",
        disabled=not local_mount,
        use_container_width=True,
    )
    save_requested = save_right.button(
        "Register mount for File Selection",
        type="primary",
        disabled=not local_mount or not remote_root,
        use_container_width=True,
    )
    expanded_mount = Path(local_mount).expanduser() if local_mount else None
    mount_available = bool(expanded_mount and expanded_mount.is_dir())
    if test_requested:
        if mount_available:
            st.success(f"Mounted folder is available: {expanded_mount}")
        else:
            st.error(
                "The mounted path is not available yet. Complete the terminal/Desktop "
                "mount first, then test again."
            )
    if save_requested:
        if not mount_available:
            st.error("The mapping was not saved because the mounted path is unavailable.")
        else:
            resolved = str(expanded_mount.resolve(strict=False))
            mappings = add_path_mapping(
                st.session_state["pyscattviz_path_mappings"],
                remote_root,
                resolved,
            )
            try:
                save_path_mappings(mappings)
            except OSError as exc:
                st.error(str(exc))
            else:
                st.session_state["pyscattviz_path_mappings"] = mappings
                st.session_state["pyscattviz_file_root"] = resolved
                st.session_state["pyscattviz_active_root"] = resolved
                roots = st.session_state.setdefault("pyscattviz_roots", [])
                if resolved not in roots:
                    roots.append(resolved)
                st.success(
                    f"Registered `{remote_root}` → `{resolved}`. Open File Selection "
                    "and browse to the result folder."
                )

with folders_tab:
    st.markdown(
        "Register any existing local disk, network share, or mounted SFTP folder. "
        "Enter one path per line."
    )
    existing = st.session_state.get("pyscattviz_roots", [])
    paths_text = st.text_area(
        "Folder paths",
        value="\n".join(existing),
        height=160,
        placeholder=(
            r"Z:\projects\sample\Results\giwaxs"
            if os.name == "nt"
            else "/path/to/Results/giwaxs"
        ),
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
            st.session_state["pyscattviz_file_root"] = roots[0]
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
        st.session_state["pyscattviz_file_root"] = active
        if Path(active).is_dir():
            st.success("Folder is available on this computer.")
        else:
            st.warning("Folder is saved but is not currently available.")

    mappings = st.session_state["pyscattviz_path_mappings"]
    if mappings:
        st.subheader("Saved remote-to-mounted mappings")
        st.dataframe(mappings, width="stretch", hide_index=True)
        remove_mapping = st.selectbox(
            "Mapping to remove",
            mappings,
            format_func=lambda item: f"{item['remote_root']}  →  {item['local_root']}",
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

st.caption(
    f"SFTP host: {SFTP_HOST}. Mounted files are read on demand by the operating system; "
    "pyScattViz opens array contents only for the selected frame."
)
