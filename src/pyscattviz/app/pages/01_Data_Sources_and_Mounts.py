"""Make NSLS-II proposal data — or a local disk — visible to pyScattViz.

pyScattViz reads ordinary filesystem paths. This page covers every free way I
know of to produce one: mounting the proposal over SFTP, copying a subset onto
the local disk, or simply pointing at data that is already there. It generates
the exact command for the selected platform and method, validates the result,
and stores the remote-to-local mapping.

The BNL password and the Duo response are entered in a terminal or in the mount
client itself. This page never asks for them and never stores them.
"""

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
    CYBERDUCK_URL,
    DEFAULT_RCLONE_REMOTE,
    FILEZILLA_URL,
    MACFUSE_URL,
    RAIDRIVE_URL,
    RAIDRIVE_WINGET_ID,
    RCLONE_URL,
    SFTP_HOST,
    SFTP_HOST_KEY_FINGERPRINT,
    WINFSP_URL,
    gvfs_hint,
    make_mount_folder_command,
    method_by_label,
    method_labels,
    mount_remote_path,
    rclone_config_command,
    rclone_copy_command,
    rclone_install_command,
    rclone_mount_command,
    rclone_unmount_command,
    sftp_download_command,
    sftp_test_command,
    sshfs_mount_command,
    suggested_mount_folder,
    unmount_command,
)

st.set_page_config(page_title="Data Sources & Mounts", page_icon="🗂️", layout="wide")
st.title("🗂️ Data Sources & Mounts")
st.caption(
    "Mount the proposal, copy a subset, or use a local disk — then register the "
    "folder so every other page can read it."
)

st.session_state.setdefault("pyscattviz_path_mappings", load_path_mappings())

scope_key = prepare_persistent_widget(st.session_state, "pyscattviz_mount_scope", "Proposal")
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
beamline_key = prepare_persistent_widget(st.session_state, "pyscattviz_mount_beamline", "SMI")
beamline = top1.selectbox(
    "Beamline",
    ["SMI", "CMS"],
    key=beamline_key,
    on_change=store_persistent_widget,
    args=(st.session_state, "pyscattviz_mount_beamline"),
)
cycle_key = prepare_persistent_widget(st.session_state, "pyscattviz_mount_cycle", "2026-2")
cycle = top2.text_input(
    "Cycle",
    key=cycle_key,
    on_change=store_persistent_widget,
    args=(st.session_state, "pyscattviz_mount_cycle"),
    placeholder="2026-2",
)
proposal_key = prepare_persistent_widget(st.session_state, "pyscattviz_mount_proposal", "")
proposal = top3.text_input(
    "Six-digit proposal",
    key=proposal_key,
    on_change=store_persistent_widget,
    args=(st.session_state, "pyscattviz_mount_proposal"),
    placeholder="319371",
)
username_key = prepare_persistent_widget(st.session_state, "pyscattviz_mount_username", "")
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
    st.markdown("**Remote folder to mount or copy**")
    st.code(remote_root, language=None)

mount_tab, folders_tab, help_tab = st.tabs(
    ["Set up access", "Mounted / local folders", "Which method should I use?"]
)

# ---------------------------------------------------------------------------
# Set up access
# ---------------------------------------------------------------------------
with mount_tab:
    st.info(
        "BNL password and Duo prompts require an interactive terminal or a desktop "
        "SFTP client. pyScattViz does not request, receive, or store those "
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
    platform_columns = st.columns([1, 2])
    platform_name = platform_columns[0].selectbox(
        "Instructions for",
        ["Windows", "Linux", "macOS"],
        key=platform_key,
        on_change=store_persistent_widget,
        args=(st.session_state, "pyscattviz_mount_platform"),
    )
    labels = method_labels(platform_name)
    method_state = f"pyscattviz_mount_method_{platform_name.lower()}"
    method_key = prepare_persistent_widget(st.session_state, method_state, labels[0])
    if st.session_state.get(method_key) not in labels:
        st.session_state[method_key] = labels[0]
    method_label = platform_columns[1].selectbox(
        "Access method",
        labels,
        key=method_key,
        on_change=store_persistent_widget,
        args=(st.session_state, method_state),
    )
    method = method_by_label(platform_name, method_label)
    st.caption(method["summary"])

    remote_name = DEFAULT_RCLONE_REMOTE
    suggested_local = str(suggested_mount_folder(beamline, proposal, scope, custom_path))

    # -- RaiDrive ----------------------------------------------------------
    if method["key"] == "raidrive":
        st.subheader("Windows: RaiDrive SFTP mount")
        st.success(
            "RaiDrive has been verified against the NSLS-II SFTP server with the BNL "
            "password, Duo Push, and a mounted Windows drive such as Z:."
        )
        st.markdown(
            "Install the free RaiDrive edition from PowerShell, or download it from "
            "the official site. pyScattViz needs read access only."
        )
        st.code(f"winget install --exact --id {RAIDRIVE_WINGET_ID}", language="powershell")
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
            "possible and do not rename, move, or delete proposal data during review."
        )

    # -- SSHFS -------------------------------------------------------------
    elif method["key"] == "sshfs":
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
                "approval of the system extension under Privacy & Security, and may "
                "ask for a restart."
            )
            st.code(
                "brew install --cask macfuse\nbrew install gromgit/fuse/sshfs-mac",
                language="bash",
            )
            st.link_button("macFUSE", MACFUSE_URL)

    # -- rclone ------------------------------------------------------------
    elif method["key"] == "rclone":
        st.subheader(f"{platform_name}: rclone mount")
        st.markdown(
            "rclone is free and open source and behaves the same on Windows, macOS, "
            "and Linux, so it is the method to use when a group needs one set of "
            "instructions. It needs a FUSE driver: WinFsp on Windows, macFUSE on macOS."
        )
        st.code(
            rclone_install_command(platform_name),
            language="powershell" if platform_name == "Windows" else "bash",
        )
        link_columns = st.columns(2)
        link_columns[0].link_button("rclone downloads", RCLONE_URL)
        if platform_name == "Windows":
            link_columns[1].link_button("WinFsp", WINFSP_URL)
        elif platform_name == "macOS":
            link_columns[1].link_button("macFUSE", MACFUSE_URL)

        remote_name = st.text_input(
            "rclone remote name",
            value=DEFAULT_RCLONE_REMOTE,
            key="pyscattviz_rclone_remote",
            help="A short label rclone stores the connection under. Configure it once.",
        )
        if username:
            st.markdown("**1. Configure the connection (once)**")
            try:
                st.code(
                    rclone_config_command(remote_name, username),
                    language="powershell" if platform_name == "Windows" else "bash",
                )
            except ValueError as exc:
                st.error(str(exc))
            st.caption(
                "`ask_password true` keeps the BNL password out of the rclone "
                "configuration file — rclone prompts for it, and for the Duo "
                "challenge, at mount time."
            )
        else:
            st.caption("Enter the BNL username above to generate the configuration command.")
        st.info(
            "I have not yet confirmed the BNL Duo prompt through rclone myself. If "
            "rclone stops without asking for the Duo option, use RaiDrive on Windows "
            "or SSHFS on macOS/Linux, both of which are known to work."
        )

    # -- GVFS --------------------------------------------------------------
    elif method["key"] == "gvfs":
        st.subheader("Linux desktop: Connect to Server")
        st.markdown(
            """
Nothing to install on a GNOME desktop such as Ubuntu or Fedora:

1. Open **Files**.
2. Select **Other Locations** at the bottom of the sidebar.
3. Enter the address below in **Connect to Server** and select **Connect**.
4. Enter the BNL password, choose the Duo option, and approve the push.

The mount then appears as an ordinary folder under `/run/user/<uid>/gvfs/`,
which is exactly what pyScattViz needs. Copy that path into the box below.
"""
        )
        st.code(gvfs_hint(username), language="bash")
        st.caption("A GVFS mount is convenient but slower than SSHFS for large image folders.")
        if username:
            suggested_local = (
                f"/run/user/{os.getuid() if hasattr(os, 'getuid') else 1000}"
                f"/gvfs/sftp:host={SFTP_HOST},user={username.strip()}"
            )

    # -- Download ----------------------------------------------------------
    elif method["key"] == "download":
        st.subheader("Copy one result folder onto the local disk")
        st.markdown(
            "No mount, no driver, nothing to install: OpenSSH ships with Windows 10/11, "
            "macOS, and every Linux distribution. This is the right answer for a single "
            "result folder, a slow link, or working on a plane."
        )
        suggested_local = str(
            Path.home()
            / "pyScattViz_Data"
            / (Path(remote_root.rstrip("/")).name if remote_root else "nsls2")
        )

    # -- Local -------------------------------------------------------------
    else:
        st.subheader("Data already on this computer")
        st.markdown(
            "A local disk, an external drive, or a laboratory network share needs no "
            "setup at all. Enter the folder below and register it; every other page "
            "will find it."
        )
        suggested_local = str(Path.home())

    # -- The local path, shared by every method ---------------------------
    is_local_only = method["kind"] == "local"
    mount_path_name = f"pyscattviz_local_path_{platform_name.lower()}_{method['key']}"
    suggestion_key = f"{mount_path_name}__suggested"
    previous_suggestion = st.session_state.get(suggestion_key)
    if (
        mount_path_name not in st.session_state
        or st.session_state[mount_path_name] == previous_suggestion
    ):
        st.session_state[mount_path_name] = suggested_local
    st.session_state[suggestion_key] = suggested_local
    mount_path_key = prepare_persistent_widget(st.session_state, mount_path_name, suggested_local)
    local_label = {
        "mount": "Mounted path on this computer",
        "copy": "Local folder to copy into",
        "local": "Folder on this computer",
    }[method["kind"]]
    local_mount = st.text_input(
        local_label,
        key=mount_path_key,
        on_change=store_persistent_widget,
        args=(st.session_state, mount_path_name),
        placeholder=(
            "Z:\\" if platform_name == "Windows" else str(Path.home() / "NSLS_II_Link" / "smi")
        ),
    )

    # -- Generated commands -----------------------------------------------
    shell = "powershell" if platform_name == "Windows" else "bash"
    if method["key"] == "sshfs" and remote_root and username and local_mount:
        st.markdown("**Run in a terminal**")
        st.code(
            make_mount_folder_command(local_mount)
            + "\n"
            + sshfs_mount_command(username, remote_root, local_mount),
            language="bash",
        )
        st.caption(
            "Paste both lines into a terminal. On the first connection verify the host "
            "fingerprint below, then enter the BNL password, choose Duo option 1, and "
            "approve the push."
        )
        st.code(SFTP_HOST_KEY_FINGERPRINT, language=None)
        st.markdown("**Unmount later**")
        st.code(unmount_command(local_mount, platform_name), language="bash")
    elif method["key"] == "rclone" and remote_root and local_mount:
        st.markdown("**2. Mount it**")
        try:
            st.code(
                (
                    ""
                    if platform_name == "Windows"
                    else make_mount_folder_command(local_mount) + "\n"
                )
                + rclone_mount_command(remote_name, remote_root, local_mount, platform_name),
                language=shell,
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.caption(
                "On Windows use a free drive letter such as `Z:`; on macOS and Linux use "
                "an empty folder. `--read-only` protects proposal data during review."
            )
            st.markdown("**Release the mount**")
            st.code(rclone_unmount_command(local_mount, platform_name), language=shell)
            st.markdown("**Or copy a subset instead of mounting**")
            include = st.text_input(
                "Only files matching (optional)",
                value="",
                key="pyscattviz_rclone_include",
                placeholder="*Kim*",
            )
            st.code(
                rclone_copy_command(remote_name, remote_root, local_mount, platform_name, include),
                language=shell,
            )
    elif method["key"] == "download" and remote_root and username and local_mount:
        st.markdown("**Run in a terminal**")
        st.code(
            sftp_download_command(username, remote_root, local_mount, platform_name),
            language=shell,
        )
        st.caption(
            "Enter the BNL password, choose Duo option 1, and approve the push. Narrow "
            "the remote folder above to one result folder — copying a whole proposal is "
            "rarely what anyone wants."
        )
        st.code(SFTP_HOST_KEY_FINGERPRINT, language=None)
        st.markdown("**Graphical alternatives**")
        graphical = st.columns(2)
        graphical[0].link_button("FileZilla (free, all platforms)", FILEZILLA_URL)
        graphical[1].link_button("Cyberduck (free, Windows/macOS)", CYBERDUCK_URL)
        st.caption(
            "Both connect to `sftp.nsls2.bnl.gov` with the BNL username, ask for the "
            "password and Duo, and let a folder be dragged to the local disk."
        )
    elif method["kind"] == "mount" and (not remote_root or not username):
        st.caption("Enter the proposal and BNL username to generate the exact command.")

    # -- Test and register -------------------------------------------------
    st.divider()
    test_left, save_right = st.columns(2)
    test_requested = test_left.button(
        "Test this folder", disabled=not local_mount, use_container_width=True
    )
    save_requested = save_right.button(
        "Register folder for the other pages",
        type="primary",
        disabled=not local_mount or (not remote_root and not is_local_only),
        use_container_width=True,
    )
    expanded_mount = Path(local_mount).expanduser() if local_mount else None
    mount_available = bool(expanded_mount and expanded_mount.is_dir())
    if test_requested:
        if mount_available:
            entries = 0
            try:
                with os.scandir(expanded_mount) as scan:
                    for _index, _entry in zip(range(50), scan):
                        entries += 1
            except OSError as exc:
                st.warning(f"The folder exists but could not be listed: {exc}")
            else:
                st.success(
                    f"Folder is available: {expanded_mount} "
                    f"({entries}{'+' if entries >= 50 else ''} entries)"
                )
        else:
            st.error(
                "That folder is not available yet. Complete the mount or the copy "
                "first, then test again."
            )
    if save_requested:
        if not mount_available:
            st.error("Nothing was registered because the folder is unavailable.")
        else:
            resolved = str(expanded_mount.resolve(strict=False))
            if remote_root and not is_local_only:
                mappings = add_path_mapping(
                    st.session_state["pyscattviz_path_mappings"], remote_root, resolved
                )
                try:
                    save_path_mappings(mappings)
                except OSError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["pyscattviz_path_mappings"] = mappings
                    st.success(f"Registered `{remote_root}` → `{resolved}`.")
            st.session_state["pyscattviz_file_root"] = resolved
            st.session_state["pyscattviz_active_root"] = resolved
            roots = st.session_state.setdefault("pyscattviz_roots", [])
            if resolved not in roots:
                roots.append(resolved)
            st.success(
                f"`{resolved}` is now the active folder. Open **Data Selection** to "
                "filter it, or **File Selection** to browse it."
            )

# ---------------------------------------------------------------------------
# Mounted / local folders
# ---------------------------------------------------------------------------
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
            r"Z:\projects\sample\Results\giwaxs" if os.name == "nt" else "/path/to/Results/giwaxs"
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

# ---------------------------------------------------------------------------
# Guidance
# ---------------------------------------------------------------------------
with help_tab:
    st.markdown(
        """
### Mount, or copy?

**Mount** when the dataset is large or you do not yet know which frames matter.
The operating system fetches the bytes of a frame only when pyScattViz opens it,
so a 2 TB proposal costs nothing until a file is read. Browsing a folder with
tens of thousands of names is slower than on a local disk, which is why the
selection pages read names only.

**Copy** when the interesting folder is small, the link is slow, or you want to
work offline. A single `Results/giwaxs` folder is usually a few hundred MB.

**Neither** if the data are already on the computer — register the folder and
start.

### Which client on which platform

| Platform | Mount | Status |
|---|---|---|
| Windows | RaiDrive | Verified here with BNL password and Duo Push |
| Windows | rclone + WinFsp | Free and open source; Duo behaviour not yet confirmed |
| macOS | SSHFS + macFUSE | Standard route; macFUSE needs a security approval |
| macOS | rclone + macFUSE | Same commands as Windows and Linux |
| Linux | SSHFS | Standard route, fastest of the three |
| Linux | Files → Connect to Server | Nothing to install; slower for large folders |
| Any | `sftp -r`, FileZilla, Cyberduck | Copies a subset; no driver needed |

RaiDrive is Windows-only, so macOS and Linux users should not look for it. SSHFS
is the equivalent there, and rclone is the one client that behaves identically on
all three.

### What pyScattViz stores

Only path mappings, in `~/.pyscattviz/path_mappings.json`, plus the saved dataset
collections and output preferences. No password, Duo response, token, or private
key is ever written by this application.

### If something is wrong

- `Permission denied` — the BNL password or Duo failed, or the account is not
  authorized for that proposal.
- `Connection timed out` — the BNL VPN or a network route is needed.
- A mount that worked earlier but now looks empty — unmount and reconnect; a
  network interruption leaves a stale FUSE mount behind.
- Never unmount while a frame is loading.
"""
    )

st.caption(
    f"SFTP host: {SFTP_HOST}. Mounted files are read on demand by the operating system; "
    "pyScattViz opens array contents only for the selected frame."
)
