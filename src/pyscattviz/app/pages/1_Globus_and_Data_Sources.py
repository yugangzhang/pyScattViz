"""Primary NSLS-II Globus workflow and local-folder registration."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from pyscattviz.globus import (
    BNL_GLOBUS_GUIDE,
    GLOBUS_FILE_MANAGER,
    NSLS2_GLOBUS_GUIDE,
    default_cache,
    proposal_path,
)

st.set_page_config(page_title="Globus & Data Sources", page_icon="🌐", layout="wide")
st.title("🌐 Globus & Data Sources")
st.caption("Transfer from the NSLS2 collection, then review the local destination folder.")

globus_tab, local_tab = st.tabs(["Globus transfer (recommended)", "Local folders"])

with globus_tab:
    st.markdown(
        """
I recommend Globus for proposal data because it provides resumable,
checksum-verified transfers on Windows, macOS, and Linux.

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
    if st.button("Save as active local folder", type="primary", disabled=not destination):
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

    st.warning(
        "The NSLS2 collection is remote storage, not a local disk path. "
        "Complete the Globus transfer before selecting the destination in a viewer."
    )

with local_tab:
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
