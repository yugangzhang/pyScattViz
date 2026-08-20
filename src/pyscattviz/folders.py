"""Remember the data folders you have opened, in a file you can read.

Every session used to start from nothing: mount the drive, find the proposal,
paste the long path again. The folder list lived in Streamlit's session state,
so it died with the browser tab.

This keeps it in ``~/.pyscattviz/data_folders.md`` instead — deliberately
markdown rather than JSON, because a list of folders is something you want to
read, tidy up, annotate, and paste into an email. Open it in any editor and it
makes sense; edit it by hand and pyScattViz picks the change up next time it
starts.

The file lives in the per-user configuration folder, never inside a repository,
so a path to an embargoed proposal cannot be committed by accident.

The format is one markdown list item per folder, under a ``## Pinned`` or
``## Recent`` heading::

    - `/mnt/data32/.../maxs/analysis` — PVDF on MXene <!-- used 2026-08-19 -->

Pinned folders are offered first and are never aged out; recent ones fall off
the end after :data:`MAX_RECENT`. Parsing is deliberately forgiving: the
backticks, the note, and the date are all optional, so a line typed by hand as
``- /some/folder`` is read correctly.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

__all__ = [
    "FolderEntry",
    "MAX_RECENT",
    "folder_paths",
    "folders_file",
    "forget_folder",
    "load_folder_entries",
    "remember_folder",
    "render_markdown",
    "save_folder_entries",
    "set_note",
    "set_pinned",
]

MAX_RECENT = 30

# Up to three spaces of indent is still a list item; four or more makes it an
# indented code block, which is how the example line in the header stays an
# example instead of being read back as a folder.
_BULLET = re.compile(r"^ {0,3}[-*]\s+(.*)$")
_HEADING = re.compile(r"^\s*#{1,6}\s+(.*)$")
_BACKTICKED = re.compile(r"^`([^`]+)`\s*(.*)$")
_USED = re.compile(r"<!--\s*used\s+([0-9]{4}-[0-9]{2}-[0-9]{2})\s*-->")
_COMMENT = re.compile(r"<!--.*?-->")
# An em dash, an en dash, or a plain double hyphen may separate path from note.
_NOTE_SPLIT = re.compile(r"\s+(?:—|–|--)\s+")

_HEADER = """# pyScattViz — data folders

Folders you have opened, most recent first. pyScattViz rewrites this file when
you open a folder and reads it when it starts, so the folder you used last is
already in the box next time.

Edit it by hand whenever you like — one folder per line:

    - `/path/to/folder` — a note of your own

Anything under **Pinned** is offered first and is never dropped; everything
under **Recent** ages out after {max_recent} entries. This file is yours: it
lives in your pyScattViz configuration folder, never inside a repository, so a
path to an embargoed proposal cannot be committed by accident.
"""


@dataclass(frozen=True)
class FolderEntry:
    """One remembered data folder."""

    path: str
    note: str = ""
    last_used: str = ""
    pinned: bool = False

    @property
    def exists(self) -> bool:
        """Is the folder reachable right now? A dropped mount is not."""

        try:
            return Path(self.path).expanduser().is_dir()
        except OSError:
            return False


def folders_file() -> Path:
    """Return the markdown file holding the remembered folders."""

    from pyscattviz.exporting import config_dir

    return config_dir() / "data_folders.md"


def normalize(path: str | Path) -> str:
    """Normalize a folder path for comparison, without resolving symlinks.

    Resolving is wrong here: a mount point is often a symlink, and following it
    would make the remembered path unrecognizable next to what the user typed.
    """

    text = str(path).strip()
    if not text:
        return ""
    text = os.path.expanduser(text)
    # Trailing separators only; keep a bare "/" intact.
    while len(text) > 1 and text.endswith(("/", "\\")):
        text = text[:-1]
    return text


def _parse_line(line: str, pinned: bool) -> FolderEntry | None:
    match = _BULLET.match(line)
    if not match:
        return None
    body = match.group(1).strip()
    if not body:
        return None

    used = ""
    date_match = _USED.search(body)
    if date_match:
        used = date_match.group(1)
    body = _COMMENT.sub("", body).strip()

    backticked = _BACKTICKED.match(body)
    if backticked:
        path, rest = backticked.group(1), backticked.group(2)
    else:
        parts = _NOTE_SPLIT.split(body, maxsplit=1)
        path, rest = parts[0], (parts[1] if len(parts) > 1 else "")

    note = _NOTE_SPLIT.sub("", rest, count=1).strip() if rest else ""
    note = note.lstrip("—–-").strip()
    path = normalize(path.strip().strip("`"))
    if not path:
        return None
    return FolderEntry(path=path, note=note, last_used=used, pinned=pinned)


def parse_markdown(text: str) -> list[FolderEntry]:
    """Read folder entries out of the markdown, pinned ones first."""

    pinned_now = False
    seen: dict[str, FolderEntry] = {}
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            title = heading.group(1).strip().lower()
            if title.startswith("pin"):
                pinned_now = True
            elif title.startswith("recent"):
                pinned_now = False
            continue
        entry = _parse_line(line, pinned_now)
        if entry is None or entry.path in seen:
            continue
        seen[entry.path] = entry
    entries = list(seen.values())
    return [item for item in entries if item.pinned] + [item for item in entries if not item.pinned]


def _render_entry(entry: FolderEntry) -> str:
    line = f"- `{entry.path}`"
    if entry.note:
        line += f" — {entry.note}"
    if entry.last_used:
        line += f" <!-- used {entry.last_used} -->"
    return line


def render_markdown(entries) -> str:
    """Render the whole file, so what is written is what will be read back."""

    pinned = [item for item in entries if item.pinned]
    recent = [item for item in entries if not item.pinned][:MAX_RECENT]

    lines = [_HEADER.format(max_recent=MAX_RECENT), "## Pinned", ""]
    lines.extend(_render_entry(item) for item in pinned)
    if not pinned:
        lines.append("_Nothing pinned yet._")
    lines.extend(["", "## Recent", ""])
    lines.extend(_render_entry(item) for item in recent)
    if not recent:
        lines.append("_Nothing here yet._")
    return "\n".join(lines) + "\n"


def load_folder_entries() -> list[FolderEntry]:
    """Load the remembered folders, or an empty list if there is no file yet."""

    try:
        text = folders_file().read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return parse_markdown(text)


def save_folder_entries(entries) -> Path | None:
    """Write the folder list, and only when it would actually change.

    ``remember_folder`` runs on every rerun of every page, so an unconditional
    write would touch the disk several times a second while somebody scrolls a
    frame list. Comparing the rendered text first makes that free.
    """

    path = folders_file()
    text = render_markdown(list(entries))
    try:
        if path.exists() and path.read_text(encoding="utf-8") == text:
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError:
        # A read-only home directory must not take the application down; the
        # folder list is a convenience, not the data.
        return None
    return path


def remember_folder(
    folder: str,
    *,
    note: str | None = None,
    today: str | None = None,
    entries=None,
) -> list[FolderEntry]:
    """Move ``folder`` to the front of the list and stamp today's date.

    An existing note is kept unless a new one is given, and a pinned folder
    stays pinned. Returns the new list; the caller decides whether to save it.
    """

    path = normalize(folder)
    if not path:
        return list(entries if entries is not None else load_folder_entries())

    current = list(entries if entries is not None else load_folder_entries())
    stamp = today or date.today().isoformat()

    existing = next((item for item in current if item.path == path), None)
    updated = FolderEntry(
        path=path,
        note=note if note is not None else (existing.note if existing else ""),
        last_used=stamp,
        pinned=existing.pinned if existing else False,
    )
    rest = [item for item in current if item.path != path]
    if updated.pinned:
        # A pinned folder keeps its place in the pinned block rather than
        # jumping to the top of the recents.
        return [updated] + rest
    pinned = [item for item in rest if item.pinned]
    unpinned = [item for item in rest if not item.pinned]
    return pinned + [updated] + unpinned[: MAX_RECENT - 1]


def forget_folder(folder: str, entries=None) -> list[FolderEntry]:
    """Drop one folder from the list."""

    path = normalize(folder)
    current = list(entries if entries is not None else load_folder_entries())
    return [item for item in current if item.path != path]


def set_pinned(folder: str, pinned: bool = True, entries=None) -> list[FolderEntry]:
    """Pin or unpin a folder, so it is offered first and never ages out."""

    path = normalize(folder)
    current = list(entries if entries is not None else load_folder_entries())
    changed = [replace(item, pinned=pinned) if item.path == path else item for item in current]
    if not any(item.path == path for item in changed) and path:
        changed.insert(0, FolderEntry(path=path, pinned=pinned))
    return [item for item in changed if item.pinned] + [item for item in changed if not item.pinned]


def set_note(folder: str, note: str, entries=None) -> list[FolderEntry]:
    """Attach a note to a folder, which is what makes the file worth reading."""

    path = normalize(folder)
    current = list(entries if entries is not None else load_folder_entries())
    return [replace(item, note=note.strip()) if item.path == path else item for item in current]


def folder_paths(entries=None, available_only: bool = False) -> list[str]:
    """Return just the paths, pinned first, optionally only reachable ones."""

    current = list(entries if entries is not None else load_folder_entries())
    if available_only:
        current = [item for item in current if item.exists]
    return [item.path for item in current]
