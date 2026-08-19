"""Persistent mappings from NSLS-II paths to local or mounted folders."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path, PurePosixPath, PureWindowsPath

_WINDOWS_ROOT = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")


def default_mapping_file() -> Path:
    """Return the per-user path-mapping file (which contains no credentials)."""

    config_root = os.environ.get("PYSCATTVIZ_CONFIG_DIR")
    folder = Path(config_root).expanduser() if config_root else Path.home() / ".pyscattviz"
    return folder / "path_mappings.json"


def normalize_remote_root(remote_root: str) -> str:
    """Normalize and validate an absolute POSIX-style remote path."""

    value = remote_root.strip().replace("\\", "/")
    if not value.startswith("/"):
        raise ValueError("Remote folder must start with / (for example /nsls2/data/...).")
    parts = PurePosixPath(value).parts
    if ".." in parts:
        raise ValueError("Remote folder cannot contain '..'.")
    return "/" + "/".join(parts[1:]) if len(parts) > 1 else "/"


def normalize_mapping(remote_root: str, local_root: str) -> dict:
    """Create a validated mapping record without touching the filesystem."""

    remote = normalize_remote_root(remote_root)
    local = local_root.strip()
    if not local:
        raise ValueError("Mounted/local folder is required.")
    return {"remote_root": remote, "local_root": local}


def add_path_mapping(mappings, remote_root: str, local_root: str) -> list[dict]:
    """Add or replace a remote-root mapping."""

    new_mapping = normalize_mapping(remote_root, local_root)
    result = [item for item in mappings if item.get("remote_root") != new_mapping["remote_root"]]
    result.append(new_mapping)
    return sorted(result, key=lambda item: item["remote_root"])


def load_path_mappings(config_file=None) -> list[dict]:
    """Load valid mappings, ignoring a missing or malformed configuration."""

    path = Path(config_file) if config_file else default_mapping_file()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    mappings = []
    if not isinstance(payload, list):
        return mappings
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            mappings = add_path_mapping(
                mappings, item.get("remote_root", ""), item.get("local_root", "")
            )
        except (AttributeError, ValueError):
            continue
    return mappings


def save_path_mappings(mappings, config_file=None) -> Path:
    """Persist mappings atomically; only paths, never passwords, are written."""

    path = Path(config_file) if config_file else default_mapping_file()
    validated = []
    for item in mappings:
        validated = add_path_mapping(validated, item["remote_root"], item["local_root"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(validated, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def translate_remote_path(remote_path: str, mappings) -> tuple[str, dict | None]:
    """Translate a pasted remote path through the longest matching mount root."""

    try:
        normalized = normalize_remote_root(remote_path)
    except ValueError:
        return remote_path, None

    candidates = sorted(mappings, key=lambda item: len(item.get("remote_root", "")), reverse=True)
    for item in candidates:
        try:
            remote_root = normalize_remote_root(item["remote_root"])
            local_root = item["local_root"].strip()
        except (KeyError, AttributeError, ValueError):
            continue
        if normalized != remote_root and not normalized.startswith(remote_root.rstrip("/") + "/"):
            continue
        relative = normalized[len(remote_root) :].lstrip("/")
        relative_parts = PurePosixPath(relative).parts if relative else ()
        if _WINDOWS_ROOT.match(local_root):
            translated = str(PureWindowsPath(local_root).joinpath(*relative_parts))
        else:
            translated = str(Path(local_root).expanduser().joinpath(*relative_parts))
        return translated, {"remote_root": remote_root, "local_root": local_root}
    return remote_path, None
