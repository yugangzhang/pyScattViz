"""NSLS-II proposal paths and official Globus entry points."""

from __future__ import annotations

import re
from pathlib import Path, PureWindowsPath
from urllib.parse import urlencode

GLOBUS_FILE_MANAGER = "https://app.globus.org/file-manager"
NSLS2_GLOBUS_GUIDE = "https://wiki-nsls2.bnl.gov/MX/index.php?title=Globus"
BNL_GLOBUS_GUIDE = "https://www.bnl.gov/cryo-em/userguide/files/globus-access.pdf"

_CYCLE = re.compile(r"^20\d{2}-[1-3]$")
_PROPOSAL = re.compile(r"^(?:pass-)?(\d{6})$", re.IGNORECASE)


def proposal_path(beamline: str, cycle: str, proposal: str) -> str:
    """Build the collection path for an SMI or CMS six-digit proposal."""

    beamline_key = beamline.strip().lower()
    if beamline_key not in {"cms", "smi"}:
        raise ValueError("beamline must be CMS or SMI")
    if not _CYCLE.fullmatch(cycle.strip()):
        raise ValueError("cycle must look like 2026-2")
    match = _PROPOSAL.fullmatch(proposal.strip())
    if not match:
        raise ValueError("proposal must contain exactly six digits")
    return f"/nsls2/data/{beamline_key}/proposals/{cycle.strip()}/pass-{match.group(1)}"


def default_cache(proposal: str) -> Path:
    """Return a cross-platform local cache suggestion without creating it."""

    match = _PROPOSAL.fullmatch(proposal.strip())
    suffix = f"pass-{match.group(1)}" if match else "pass-xxxxxx"
    return Path.home() / "pyScattViz-data" / suffix


def globus_file_manager_url(remote_path: str) -> str:
    """Build a File Manager link that carries the collection path to Globus."""

    return f"{GLOBUS_FILE_MANAGER}?{urlencode({'origin_path': remote_path})}"


def local_path_to_globus_path(path: str | Path) -> str:
    """Suggest the absolute path syntax used by Globus Connect Personal."""

    value = str(path)
    windows_path = PureWindowsPath(value)
    if windows_path.drive:
        drive = windows_path.drive.rstrip(":")
        relative_parts = windows_path.parts[1:]
        return "/" + "/".join((drive, *relative_parts))
    return Path(value).expanduser().as_posix()
