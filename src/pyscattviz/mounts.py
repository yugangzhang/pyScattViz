"""NSLS-II proposal paths and cross-platform SFTP mount commands."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

SFTP_HOST = "sftp.nsls2.bnl.gov"
SFTP_HOST_KEY_FINGERPRINT = "SHA256:OxSNZKjRbOQ2QTl7Gc1tVf6d6F2AN39w6Dw7yjUCahE"
MOUNTAIN_DUCK_URL = "https://mountainduck.io/"

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


def suggested_mount_folder(beamline: str, proposal: str) -> Path:
    """Return a proposal-specific local mount-point suggestion."""

    match = _PROPOSAL.fullmatch(proposal.strip())
    suffix = f"pass-{match.group(1)}" if match else "pass-xxxxxx"
    return Path.home() / "NSLS_II_Link" / f"{beamline.strip().lower()}-{suffix}"


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
