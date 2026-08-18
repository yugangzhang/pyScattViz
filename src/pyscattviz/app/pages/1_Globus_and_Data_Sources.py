"""Primary NSLS-II Globus workflow and local-folder registration."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from pyscattviz.data_sources import (
    add_path_mapping,
    load_path_mappings,
    save_path_mappings,
    sshfs_windows_unc,
    translate_remote_path,
)
from pyscattviz.globus import (
    BNL_GLOBUS_GUIDE,
    GLOBUS_FILE_MANAGER,
    NSLS2_GLOBUS_GUIDE,
    default_cache,
    globus_file_manager_url,
    proposal_path,
)

st.set_page_config(page_title="Globus & Data Sources", page_icon="🌐", layout="wide")
st.title("🌐 Globus & Data Sources")
st.caption("Browse the NSLS2 collection online, or register a mounted/local data folder.")

st.session_state.setdefault("pyscattviz_path_mappings", load_path_mappings())
globus_tab, mount_tab, local_tab = st.tabs(
    ["Globus online / transfer", "Remote mount (lazy access)", "Local folders"]
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
        "or local filesystem path. pyScattViz can browse it in Globus, but loading a "
        "frame requires a transferred result folder or an SFTP/SSHFS/network mount."
    )

with mount_tab:
    st.markdown(
        """
An SSHFS mount makes an NSLS-II SFTP folder appear as a normal drive. The data
remain at NSLS-II; directory names and only the files opened by pyScattViz cross
the network. This is separate from Globus and requires BNL SFTP access plus the
BNL network or VPN.

### Windows one-time setup

Open **PowerShell as Administrator** and install the filesystem drivers:
"""
    )
    st.code(
        "winget install --exact --id WinFsp.WinFsp\n"
        "winget install --exact --id SSHFS-Win.SSHFS-Win",
        language="powershell",
    )
    st.caption("Restart Windows after the first installation, then start the BNL VPN.")

    mount_remote = st.text_input(
        "NSLS-II folder to mount",
        value=remote_path or "/nsls2/data/smi/proposals",
        placeholder="/nsls2/data/smi/proposals/2026-2/pass-319371",
    )
    mount_left, mount_right, mount_drive = st.columns([2, 2, 1])
    bnl_username = mount_left.text_input(
        "BNL username",
        placeholder="yuzhang",
        help="Used only to generate the mount address; pyScattViz does not save a password.",
    )
    mounted_folder = mount_right.text_input(
        "Mounted/local folder",
        value="Z:\\",
        help="The Windows drive or local mount point representing the remote folder.",
    )
    drive_letter = mount_drive.text_input("Windows drive", value="Z:")

    if bnl_username and mount_remote:
        try:
            unc_path = sshfs_windows_unc(bnl_username, mount_remote)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.markdown("**Map the drive**")
            st.markdown(
                "In File Explorer, open **This PC → ⋯ → Map network drive**, choose the "
                f"drive **{drive_letter}**, and paste this folder address:"
            )
            st.code(unc_path, language=None)
            st.caption(
                "Windows will request the BNL password. The password is handled by Windows/"
                "SSHFS-Win and is never entered into pyScattViz."
            )
            st.markdown("Equivalent PowerShell command:")
            st.code(
                f"net use {drive_letter} '{unc_path}' /persistent:yes",
                language="powershell",
            )

    if st.button("Save remote-to-mounted path mapping", type="primary"):
        try:
            mappings = add_path_mapping(
                st.session_state["pyscattviz_path_mappings"],
                mount_remote,
                mounted_folder,
            )
            config_file = save_path_mappings(mappings)
        except (OSError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.session_state["pyscattviz_path_mappings"] = mappings
            translated, _mapping = translate_remote_path(mount_remote, mappings)
            st.success(f"Saved mapping: {mount_remote} → {translated}")
            st.caption(f"Saved locally in {config_file}; no credentials are stored.")
            if Path(translated).is_dir():
                st.success("The mounted folder is available now.")
            else:
                st.warning(
                    "The mapping is saved, but the mounted folder is not available yet. "
                    "Complete the Windows drive mapping or connect the VPN."
                )

    mappings = st.session_state["pyscattviz_path_mappings"]
    if mappings:
        st.markdown("**Saved path mappings**")
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

    with st.expander("macOS / Linux SSHFS command"):
        st.code(
            "mkdir -p ~/NSLS_II_Link/smi_remote\n"
            "sshfs USERNAME@sftp.nsls2.bnl.gov:/nsls2/data/smi/proposals "
            "~/NSLS_II_Link/smi_remote",
            language="bash",
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
