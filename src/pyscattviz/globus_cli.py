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
TRANSFER_ALL_SCOPE = "urn:globus:auth:scope:transfer.api.globus.org:all"


class GlobusCLIError(RuntimeError):
    """A user-facing Globus CLI failure."""


class GlobusConsentRequired(GlobusCLIError):
    """The user must grant the NSLS2 collection data-access consent."""

    def __init__(self, message: str, required_scopes=()):
        super().__init__(message)
        self.required_scopes = tuple(dict.fromkeys(required_scopes))


def collection_data_access_scope(collection_id: str) -> str:
    """Return the Globus Auth data-access scope for a collection UUID."""

    return f"https://auth.globus.org/scopes/{collection_id}/data_access"


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
        try:
            error_payload = json.loads(detail)
        except json.JSONDecodeError:
            error_payload = None
        if isinstance(error_payload, dict) and error_payload.get("code") == "ConsentRequired":
            scopes = list(error_payload.get("required_scopes") or [])
            authorization = error_payload.get("authorization_parameters") or {}
            scopes.extend(authorization.get("required_scopes") or [])
            if "data_access" in str(error_payload.get("message", "")):
                for argument in arguments:
                    if ":/" in argument:
                        collection_id = argument.split(":", 1)[0]
                        scopes.append(collection_data_access_scope(collection_id))
                        break
            raise GlobusConsentRequired(
                "The NSLS2 collection requires one-time Globus data-access consent.",
                scopes,
            )
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


def find_current_nsls2_collection(executable=None) -> str:
    """Discover the current non-retired NSLS2 collection through the CLI."""

    output = _run_globus(
        ["endpoint", "search", "NSLS2", "--limit", "25", "--format", "json"],
        executable=executable,
    )
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise GlobusCLIError("Globus collection search returned invalid JSON.") from exc
    entries = payload.get("DATA", []) if isinstance(payload, dict) else []
    candidates = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("id"):
            continue
        searchable = " ".join(str(value) for value in entry.values()).lower()
        display_name = str(entry.get("display_name") or entry.get("canonical_name") or "")
        if "nsls2" not in display_name.lower() or "retired" in searchable:
            continue
        score = 0
        if display_name.strip().lower() == "nsls2":
            score += 10
        if "globus.nsls2.bnl.gov" in searchable:
            score += 20
        if str(entry["id"]) == NSLS2_COLLECTION_ID:
            score += 5
        candidates.append((score, str(entry["id"])))
    if not candidates:
        raise GlobusCLIError("No current, non-retired NSLS2 collection was found.")
    candidates.sort(reverse=True)
    return candidates[0][1]


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
