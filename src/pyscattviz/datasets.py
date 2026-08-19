"""Named, reusable lists of the folders and files a user wants to review.

A *dataset collection* is nothing more than an ordered list of full paths plus
a short note. I keep them in ``~/.pyscattviz/collections/`` so a collaborator
can rebuild yesterday's selection in one click instead of retyping filters, and
so a selection can be mailed to me as a small JSON file when something looks
wrong. No credentials and no data are stored — only paths.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from pyscattviz.data_sources import translate_remote_path

__all__ = [
    "collection_file",
    "collections_dir",
    "delete_collection",
    "list_collections",
    "load_collection",
    "normalize_paths",
    "safe_collection_name",
    "save_collection",
]

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def config_dir() -> Path:
    """Return the per-user pyScattViz configuration folder."""

    override = os.environ.get("PYSCATTVIZ_CONFIG_DIR")
    return Path(override).expanduser() if override else Path.home() / ".pyscattviz"


def collections_dir(config_root: str | Path | None = None) -> Path:
    """Return the folder holding saved dataset collections."""

    base = Path(config_root).expanduser() if config_root else config_dir()
    return base / "collections"


def safe_collection_name(name: str) -> str:
    """Turn a user-entered collection name into a safe file stem."""

    cleaned = _UNSAFE.sub("_", str(name).strip()).strip("._-")
    if not cleaned:
        raise ValueError("Collection name must contain at least one letter or digit.")
    return cleaned[:80]


def collection_file(name: str, config_root: str | Path | None = None) -> Path:
    """Return the JSON file backing one named collection."""

    return collections_dir(config_root) / f"{safe_collection_name(name)}.json"


def normalize_paths(paths: Iterable[str | Path], mappings: Iterable[dict] = ()) -> list[str]:
    """Expand, translate, and de-duplicate a list of paths while keeping order.

    A pasted ``/nsls2/...`` path is translated through the registered mount
    mappings, so a path copied from a beamline email works directly.
    """

    mapping_list = list(mappings)
    result: list[str] = []
    for value in paths:
        text = str(value).strip().strip('"').strip("'")
        if not text or text.startswith("#"):
            continue
        translated, _mapping = translate_remote_path(text, mapping_list)
        candidate = str(Path(translated).expanduser())
        if candidate not in result:
            result.append(candidate)
    return result


def save_collection(
    name: str,
    paths: Iterable[str | Path],
    note: str = "",
    config_root: str | Path | None = None,
) -> Path:
    """Write a named collection atomically and return its file path."""

    target = collection_file(name, config_root)
    payload = {
        "name": str(name).strip(),
        "note": str(note).strip(),
        "saved": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "paths": [str(item) for item in paths],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def load_collection(name: str, config_root: str | Path | None = None) -> dict:
    """Read one named collection; a malformed file raises ``ValueError``."""

    target = collection_file(name, config_root)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Collection {name!r} is not available.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Collection {name!r} is not valid JSON.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("paths"), list):
        raise ValueError(f"Collection {name!r} does not contain a path list.")
    return {
        "name": str(payload.get("name") or name),
        "note": str(payload.get("note") or ""),
        "saved": str(payload.get("saved") or ""),
        "paths": [str(item) for item in payload["paths"]],
        "file": str(target),
    }


def list_collections(config_root: str | Path | None = None) -> list[dict]:
    """Return every readable collection, most recently saved first."""

    folder = collections_dir(config_root)
    summaries: list[dict] = []
    try:
        files = sorted(folder.glob("*.json"))
    except OSError:
        return summaries
    for item in files:
        try:
            payload = load_collection(item.stem, config_root)
        except ValueError:
            continue
        payload["count"] = len(payload["paths"])
        summaries.append(payload)
    summaries.sort(key=lambda entry: entry["saved"], reverse=True)
    return summaries


def delete_collection(name: str, config_root: str | Path | None = None) -> bool:
    """Remove a named collection; return False when it was already gone."""

    target = collection_file(name, config_root)
    try:
        target.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise ValueError(f"Could not remove {target}: {exc}") from exc
    return True
