"""NSLS-II proposal paths and cross-platform SFTP mount commands."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

SFTP_HOST = "sftp.nsls2.bnl.gov"
SFTP_HOST_KEY_FINGERPRINT = "SHA256:OxSNZKjRbOQ2QTl7Gc1tVf6d6F2AN39w6Dw7yjUCahE"
RAIDRIVE_URL = "https://www.raidrive.com/"
RAIDRIVE_WINGET_ID = "OpenBoxLab.RaiDrive"

_CYCLE = re.compile(r"^20\d{2}-[1-3]$")
_PROPOSAL = re.compile(r"^(?:pass-)?(\d{6})$", re.IGNORECASE)


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


def sshfs_mount_command(username: str, remote_root: str, local_root: str) -> str:
    """Return a POSIX SSHFS command that prompts for BNL password and Duo."""

    source = f"{username.strip()}@{SFTP_HOST}:{remote_root.rstrip('/')}/"
    options = "follow_symlinks,reconnect,ServerAliveInterval=15,ServerAliveCountMax=3"
    return f"sshfs -o {options} {shlex.quote(source)} {shlex.quote(local_root)}"


def make_mount_folder_command(local_root: str) -> str:
    """Return the POSIX command that creates the local mount point."""

    return f"mkdir -p {shlex.quote(local_root)}"


def unmount_command(local_root: str, platform_name: str) -> str:
    """Return a Linux or macOS unmount command."""

    quoted = shlex.quote(local_root)
    if platform_name.lower() == "linux":
        return f"fusermount3 -u {quoted} || fusermount -u {quoted}"
    if platform_name.lower() in {"macos", "darwin", "mac"}:
        return f"umount {quoted}"
    raise ValueError("unmount command is available only for Linux and macOS")
