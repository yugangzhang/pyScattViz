"""NSLS-II proposal paths and cross-platform SFTP mount commands.

pyScattViz reads ordinary filesystem paths, so the only question a user has to
answer is how the proposal folder becomes an ordinary path on their computer.
There are three honest answers, and this module generates the exact commands
for all of them:

1. **Mount it.** RaiDrive on Windows (verified here with BNL password and Duo),
   SSHFS on Linux and macOS, or rclone on any of the three. The bytes of an
   opened frame cross the network; the proposal is never copied whole.
2. **Copy a subset.** An ``sftp -r`` or ``rclone copy`` of one result folder
   onto the local disk, which is the fastest option for a small dataset or a
   flight with no network.
3. **Use data already on the disk.** Nothing to configure — point pyScattViz at
   the folder.

Every mount client asks for the BNL password and the Duo response itself. The
GUI generates the command and validates the result; it never receives a
credential.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

SFTP_HOST = "sftp.nsls2.bnl.gov"
SFTP_HOST_KEY_FINGERPRINT = "SHA256:OxSNZKjRbOQ2QTl7Gc1tVf6d6F2AN39w6Dw7yjUCahE"
RAIDRIVE_URL = "https://www.raidrive.com/"
RAIDRIVE_WINGET_ID = "OpenBoxLab.RaiDrive"
RCLONE_URL = "https://rclone.org/downloads/"
RCLONE_WINGET_ID = "Rclone.Rclone"
WINFSP_URL = "https://winfsp.dev/rel/"
WINFSP_WINGET_ID = "WinFsp.WinFsp"
MACFUSE_URL = "https://macfuse.github.io/"
CYBERDUCK_URL = "https://cyberduck.io/"
FILEZILLA_URL = "https://filezilla-project.org/"
DEFAULT_RCLONE_REMOTE = "nsls2"

PLATFORMS = ("Windows", "macOS", "Linux")

_CYCLE = re.compile(r"^20\d{2}-[1-3]$")
_PROPOSAL = re.compile(r"^(?:pass-)?(\d{6})$", re.IGNORECASE)
_REMOTE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")


def proposal_path(beamline: str, cycle: str, proposal: str) -> str:
    """Build the SFTP path for an SMI or CMS six-digit proposal."""

    beamline_key = beamline.strip().lower()
    if beamline_key not in {"cms", "smi"}:
        raise ValueError("beamline must be CMS or SMI")
    if not _CYCLE.fullmatch(cycle.strip()):
        raise ValueError("cycle must look like 2026-2")
    match = _PROPOSAL.fullmatch(proposal.strip())
    if not match:
        raise ValueError("proposal must contain exactly six digits")
    return f"/nsls2/data/{beamline_key}/proposals/{cycle.strip()}/pass-{match.group(1)}"


def mount_remote_path(
    scope: str,
    beamline: str,
    cycle: str = "",
    proposal: str = "",
    custom_path: str = "",
) -> str:
    """Build a validated remote root for one of the supported mount scopes."""

    beamline_key = beamline.strip().lower()
    if beamline_key not in {"cms", "smi"}:
        raise ValueError("beamline must be CMS or SMI")
    if scope == "Proposal":
        return proposal_path(beamline, cycle, proposal)
    if scope == "Beamline proposals":
        return f"/nsls2/data/{beamline_key}/proposals"
    if scope == "NSLS-II data":
        return "/nsls2/data"
    if scope == "Custom":
        value = custom_path.strip().replace("\\", "/").rstrip("/")
        if not value.startswith("/nsls2/data"):
            raise ValueError("custom path must start with /nsls2/data")
        if ".." in value.split("/"):
            raise ValueError("custom path cannot contain '..'")
        return value or "/nsls2/data"
    raise ValueError("unknown mount scope")


def suggested_mount_folder(
    beamline: str,
    proposal: str,
    scope: str = "Proposal",
    custom_path: str = "",
) -> Path:
    """Return a readable local mount-point suggestion for the selected scope."""

    match = _PROPOSAL.fullmatch(proposal.strip())
    suffix = f"pass-{match.group(1)}" if match else "pass-xxxxxx"
    beamline_key = beamline.strip().lower()
    if scope == "Beamline proposals":
        suffix = f"{beamline_key}-proposals"
    elif scope == "NSLS-II data":
        suffix = "nsls2-data"
    elif scope == "Custom":
        suffix = Path(custom_path.rstrip("/")).name or "nsls2-data"
    else:
        suffix = f"{beamline_key}-{suffix}"
    return Path.home() / "NSLS_II_Link" / suffix


def sftp_test_command(username: str) -> str:
    """Return the cross-platform OpenSSH connectivity test command."""

    return f"sftp {username.strip()}@{SFTP_HOST}"


def posix_quote(value: str) -> str:
    """Quote a POSIX path while leaving a leading ``~/`` shell-expandable."""

    text = str(value)
    if text.startswith("~/"):
        return "~/" + shlex.quote(text[2:])
    if text == "~":
        return text
    return shlex.quote(text)


def sshfs_mount_command(username: str, remote_root: str, local_root: str) -> str:
    """Return a POSIX SSHFS command that prompts for BNL password and Duo."""

    source = f"{username.strip()}@{SFTP_HOST}:{remote_root.rstrip('/')}/"
    options = "follow_symlinks,reconnect,ServerAliveInterval=15,ServerAliveCountMax=3"
    return f"sshfs -o {options} {shlex.quote(source)} {posix_quote(local_root)}"


def make_mount_folder_command(local_root: str) -> str:
    """Return the POSIX command that creates the local mount point."""

    return f"mkdir -p {posix_quote(local_root)}"


def unmount_command(local_root: str, platform_name: str) -> str:
    """Return a Linux or macOS unmount command."""

    quoted = shlex.quote(local_root)
    if platform_name.lower() == "linux":
        return f"fusermount3 -u {quoted} || fusermount -u {quoted}"
    if platform_name.lower() in {"macos", "darwin", "mac"}:
        return f"umount {quoted}"
    raise ValueError("unmount command is available only for Linux and macOS")


# ---------------------------------------------------------------------------
# rclone: the one free client that mounts the same way on all three platforms
# ---------------------------------------------------------------------------
def _normalize_platform(platform_name: str) -> str:
    key = platform_name.strip().lower()
    if key.startswith("win"):
        return "Windows"
    if key in {"macos", "mac", "darwin", "osx"}:
        return "macOS"
    if key == "linux":
        return "Linux"
    raise ValueError("platform must be Windows, macOS, or Linux")


def _quote_for(platform_name: str, value: str) -> str:
    """Quote a path for PowerShell or a POSIX shell."""

    if _normalize_platform(platform_name) == "Windows":
        return f'"{value}"' if " " in value else value
    return posix_quote(value)


def validate_remote_name(remote_name: str) -> str:
    """Validate the short name an rclone remote is stored under."""

    value = remote_name.strip()
    if not _REMOTE_NAME.fullmatch(value):
        raise ValueError(
            "rclone remote name must start with a letter and use only letters, "
            "digits, hyphens, and underscores"
        )
    return value


def rclone_install_command(platform_name: str) -> str:
    """Return the install command for rclone and its FUSE driver."""

    platform = _normalize_platform(platform_name)
    if platform == "Windows":
        return (
            f"winget install --exact --id {WINFSP_WINGET_ID}\n"
            f"winget install --exact --id {RCLONE_WINGET_ID}"
        )
    if platform == "macOS":
        return "brew install --cask macfuse\nbrew install rclone"
    return (
        "sudo apt update && sudo apt install rclone fuse3\n"
        "# Fedora/RHEL alternative:\n"
        "sudo dnf install rclone fuse3"
    )


def rclone_config_command(remote_name: str, username: str) -> str:
    """Return the one-line rclone command that defines the NSLS-II remote.

    ``ask_password`` keeps the BNL password out of the rclone configuration
    file; rclone prompts for it, and for the Duo challenge, at mount time.
    """

    name = validate_remote_name(remote_name)
    user = username.strip()
    if not user:
        raise ValueError("BNL username is required")
    return (
        f"rclone config create {name} sftp host {SFTP_HOST} user {user} port 22 ask_password true"
    )


def rclone_mount_command(
    remote_name: str,
    remote_root: str,
    local_root: str,
    platform_name: str,
    read_only: bool = True,
) -> str:
    """Return the rclone command that mounts the remote root as a local path.

    The VFS cache keeps a re-read frame local, which matters when a user drags
    a colour-scale slider over a 4k detector image on a slow link.
    """

    name = validate_remote_name(remote_name)
    platform = _normalize_platform(platform_name)
    remote = remote_root.strip().rstrip("/") or "/"
    options = [
        "--vfs-cache-mode full",
        "--dir-cache-time 60s",
        "--attr-timeout 60s",
    ]
    if read_only:
        options.insert(0, "--read-only")
    if platform == "Windows":
        options.append("--network-mode")
    else:
        options.append("--daemon")
    target = _quote_for(platform, local_root.strip())
    return f"rclone mount {name}:{remote} {target} " + " ".join(options)


def rclone_unmount_command(local_root: str, platform_name: str) -> str:
    """Return the command that releases an rclone mount."""

    platform = _normalize_platform(platform_name)
    if platform == "Windows":
        return "# Press Ctrl+C in the PowerShell window running rclone mount."
    return unmount_command(local_root, platform)


def rclone_copy_command(
    remote_name: str,
    remote_root: str,
    local_root: str,
    platform_name: str,
    include: str = "",
) -> str:
    """Return an rclone command that copies a subset onto the local disk.

    ``include`` is an optional filename pattern such as ``*sampleA*`` so a user can
    take one sample's products instead of a whole result folder.
    """

    name = validate_remote_name(remote_name)
    platform = _normalize_platform(platform_name)
    remote = remote_root.strip().rstrip("/") or "/"
    target = _quote_for(platform, local_root.strip())
    command = f"rclone copy {name}:{remote} {target} --progress"
    pattern = include.strip()
    if pattern:
        command += f" --include {_quote_for(platform, pattern)}"
    return command


# ---------------------------------------------------------------------------
# No mount at all: copy the interesting folder onto the local disk
# ---------------------------------------------------------------------------
def sftp_download_command(
    username: str,
    remote_root: str,
    local_root: str,
    platform_name: str,
) -> str:
    """Return an OpenSSH ``sftp -r`` command that copies a folder locally.

    OpenSSH ships with Windows 10/11, macOS, and every Linux distribution I
    have used, so this is the one route that needs nothing installed. It is the
    right answer for a single result folder or for working offline.
    """

    platform = _normalize_platform(platform_name)
    user = username.strip()
    if not user:
        raise ValueError("BNL username is required")
    remote = remote_root.strip().rstrip("/")
    target = local_root.strip()
    quoted_target = _quote_for(platform, target)
    if platform == "Windows":
        create = f"New-Item -ItemType Directory -Force -Path {quoted_target}"
    else:
        create = make_mount_folder_command(target)
    return f"{create}\nsftp -r {user}@{SFTP_HOST}:{remote} {quoted_target}"


def gvfs_hint(username: str) -> str:
    """Return the GNOME Files address and the path a GVFS mount appears at.

    Ubuntu and Fedora desktops can mount SFTP with no installation at all:
    Files → Other Locations → Connect to Server. The mount then shows up under
    ``/run/user/<uid>/gvfs/`` as a normal folder, which is all pyScattViz needs.
    """

    user = username.strip() or "USERNAME"
    return (
        f"sftp://{user}@{SFTP_HOST}/\n"
        f"# then register: /run/user/$(id -u)/gvfs/sftp:host={SFTP_HOST},user={user}"
    )


# ---------------------------------------------------------------------------
# Method registry used by the Data Sources & Mounts page and the README
# ---------------------------------------------------------------------------
_METHODS = (
    {
        "key": "raidrive",
        "label": "RaiDrive (mount a drive letter)",
        "platforms": ("Windows",),
        "kind": "mount",
        "verified": True,
        "summary": (
            "Free SFTP client that gives the proposal a Windows drive letter. "
            "Verified here with the BNL password and Duo Push."
        ),
    },
    {
        "key": "sshfs",
        "label": "SSHFS (mount a folder)",
        "platforms": ("Linux", "macOS"),
        "kind": "mount",
        "verified": False,
        "summary": (
            "The standard FUSE mount. Linux installs it from the distribution "
            "repository; macOS needs macFUSE plus the sshfs-mac formula."
        ),
    },
    {
        "key": "rclone",
        "label": "rclone (mount, all three platforms)",
        "platforms": ("Windows", "macOS", "Linux"),
        "kind": "mount",
        "verified": False,
        "summary": (
            "One free, open-source client with the same commands everywhere. "
            "Needs WinFsp on Windows or macFUSE on macOS."
        ),
    },
    {
        "key": "gvfs",
        "label": "GNOME Files → Connect to Server",
        "platforms": ("Linux",),
        "kind": "mount",
        "verified": False,
        "summary": (
            "Nothing to install on an Ubuntu or Fedora desktop. The mount "
            "appears under /run/user/<uid>/gvfs/ as an ordinary folder."
        ),
    },
    {
        "key": "download",
        "label": "Copy a subset to the local disk",
        "platforms": ("Windows", "macOS", "Linux"),
        "kind": "copy",
        "verified": True,
        "summary": (
            "sftp -r or rclone copy pulls one result folder onto the local "
            "disk. Best for a small dataset, a slow link, or working offline."
        ),
    },
    {
        "key": "local",
        "label": "Data already on this computer",
        "platforms": ("Windows", "macOS", "Linux"),
        "kind": "local",
        "verified": True,
        "summary": (
            "A local disk, a USB drive, or a laboratory network share. Register "
            "the folder and start reviewing."
        ),
    },
)


def mount_methods(platform_name: str) -> tuple[dict, ...]:
    """Return the routes available on one platform, best-supported first."""

    platform = _normalize_platform(platform_name)
    return tuple(method for method in _METHODS if platform in method["platforms"])


def method_labels(platform_name: str) -> tuple[str, ...]:
    """Return the selectable method labels for one platform."""

    return tuple(method["label"] for method in mount_methods(platform_name))


def method_by_label(platform_name: str, label: str) -> dict:
    """Look one method up by its display label."""

    for method in mount_methods(platform_name):
        if method["label"] == label:
            return method
    raise ValueError(f"unknown mount method: {label}")
