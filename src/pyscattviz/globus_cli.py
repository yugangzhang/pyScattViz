"""Read-only Globus CLI integration using the user's existing CLI login."""

from __future__ import annotations

import json
import os
import posixpath
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath

from pyscattviz.browser import human_size

NSLS2_COLLECTION_ID = "819379a8-47db-439d-a5ba-a2387b79add9"


class GlobusCLIError(RuntimeError):
    """A user-facing Globus CLI failure."""


def find_globus_cli() -> str | None:
    """Find the Globus executable installed beside Python or on PATH."""

    executable_name = "globus.exe" if os.name == "nt" else "globus"
    beside_python = Path(sys.executable).with_name(executable_name)
    if beside_python.is_file():
        return str(beside_python)
    return shutil.which(executable_name)


def _run_globus(arguments, executable=None, timeout=60) -> str:
    command = executable or find_globus_cli()
    if not command:
        raise GlobusCLIError(
            "Globus CLI is not installed in this Python environment. Reinstall "
            "pyScattViz, then run globus login from the same .venv."
        )
    try:
        completed = subprocess.run(
            [command, *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GlobusCLIError(f"Could not run Globus CLI: {exc}") from exc
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise GlobusCLIError(detail or f"Globus CLI exited with code {completed.returncode}.")
    return completed.stdout


def globus_identity(executable=None) -> str:
    """Return the username from the current Globus CLI login."""

    output = _run_globus(["whoami", "--format", "json"], executable=executable)
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise GlobusCLIError("Globus whoami returned invalid JSON.") from exc
    if isinstance(payload, dict):
        for key in ("preferred_username", "username", "identity", "email", "name", "sub"):
            if payload.get(key):
                return str(payload[key])
    if isinstance(payload, str) and payload:
        return payload
    raise GlobusCLIError("Globus login information did not contain a username.")


def normalize_globus_path(path: str) -> str:
    """Normalize an absolute collection path without permitting parent traversal."""

    value = path.strip().replace("\\", "/")
    if not value.startswith("/"):
        raise GlobusCLIError("Globus path must start with /nsls2/.")
    parts = PurePosixPath(value).parts
    if ".." in parts:
        raise GlobusCLIError("Globus path cannot contain '..'.")
    normalized = "/" + "/".join(parts[1:]) if len(parts) > 1 else "/"
    return normalized.rstrip("/") or "/"


def list_globus_directory(path: str, collection_id=NSLS2_COLLECTION_ID, executable=None):
    """List one NSLS2 collection folder through an authenticated Globus CLI."""

    normalized = normalize_globus_path(path)
    output = _run_globus(
        [
            "ls",
            f"{collection_id}:{normalized}",
            "--format",
            "json",
            "--orderby",
            "type:ASC",
            "--orderby",
            "name:ASC",
        ],
        executable=executable,
    )
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise GlobusCLIError("Globus directory listing returned invalid JSON.") from exc
    entries = payload.get("DATA", []) if isinstance(payload, dict) else []
    rows = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("name"):
            continue
        entry_type = str(entry.get("type") or entry.get("DATA_TYPE") or "file").lower()
        is_dir = entry_type in {"dir", "directory"}
        name = str(entry["name"])
        size = entry.get("size")
        rows.append(
            {
                "name": name + ("/" if is_dir and not name.endswith("/") else ""),
                "type": "folder" if is_dir else "file",
                "size": "—" if is_dir or not isinstance(size, int) else human_size(size),
                "modified": str(entry.get("last_modified") or ""),
                "path": posixpath.join(normalized.rstrip("/"), name),
                "is_dir": is_dir,
            }
        )
    rows.sort(key=lambda row: (not row["is_dir"], row["name"].casefold()))
    return rows
