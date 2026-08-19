"""A small read-only shell for finding data and building named file lists.

Scientists already know ``ls``, ``cd`` and ``cat``, and clicking through a
mounted proposal is slower than typing. This gives them the familiar verbs
without ever handing anything to a system shell: each command is parsed here and
implemented with :mod:`pathlib`, so there is no way to spell ``rm``.

The second job is building a **selection** — an ordered list of full paths that
survives as the dataset basket, so a list assembled here shows up in Quick Plot,
in Publication Plot, and in the explorers::

    cd Z:/projects/myproject/Results/giwaxs/cir_avg
    ls *UV_2*
    select *UV_20* *UV_30*
    unselect *AgBH*
    save uv_series

``select`` takes several patterns and unions them, which is how you ask for two
samples at once; ``unselect`` removes matches. A saved list is the same named
collection Data Selection reads, stored under ``~/.pyscattviz/collections/``.

Everything is bounded: listings, recursive searches, and ``cat`` all stop at a
limit rather than pulling a whole mounted folder across the network.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path

from pyscattviz.browser import (
    _split_command,
    directory_size,
    human_size,
    list_directory,
    resolve_browser_path,
)
from pyscattviz.data_sources import translate_remote_path
from pyscattviz.datasets import list_collections, load_collection, save_collection

__all__ = ["COMMAND_HELP", "ShellResult", "run_shell_command"]

# Bounds. A mounted proposal folder can hold a million names; every command that
# could walk one has to stop somewhere and say that it did.
MAX_LIST = 500
MAX_FIND = 2_000
MAX_SELECT = 20_000
CAT_MAX_LINES = 200
CAT_MAX_BYTES = 256 * 1024
FIND_MAX_DEPTH = 8

COMMAND_HELP = """Supported commands (all read-only)

  pwd                     show the current folder
  ls [pattern]            list the folder, or the names matching a pattern
  cd <path>               change folder ( cd .. goes up )
  find <pattern>          search below the current folder, e.g. find *UV_2*
  du [path]               bounded size estimate
  cat <file> [-n N]       show the first N lines of a text file (default 40)
  head <file> [-n N]      same as cat
  tail <file> [-n N]      show the last N lines
  wc <pattern>            count matching files, and lines in a text file

Building a list, which every plotting tab can then read

  select <pattern> ...    add matching files; several patterns are OR-ed
  unselect <pattern> ...  remove matching files from the list
  list                    show the current list
  clear                   empty the list
  save <name>             save the list under a name
  load <name>             replace the list with a saved one
  lists                   show the saved lists
  help                    this message

Patterns are shell globs: * matches anything, ? matches one character.
"""


@dataclass
class ShellResult:
    """What one command did."""

    cwd: str
    output: str = ""
    rows: list = field(default_factory=list)
    error: str | None = None
    selection: tuple[str, ...] = ()
    selection_changed: bool = False


def _is_text(path: Path, probe: int = 2048) -> bool:
    try:
        with path.open("rb") as handle:
            return b"\0" not in handle.read(probe)
    except OSError:
        return False


def _match_names(folder: Path, patterns, *, files_only: bool = True, limit: int = MAX_LIST):
    """Return direct children of ``folder`` matching any glob pattern."""

    hits: list[Path] = []
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                try:
                    if files_only and not entry.is_file():
                        continue
                except OSError:
                    continue
                if patterns and not any(
                    fnmatch.fnmatch(entry.name, pattern) for pattern in patterns
                ):
                    continue
                hits.append(Path(entry.path))
                if len(hits) >= limit:
                    break
    except OSError:
        return []
    return sorted(hits, key=lambda item: item.name.casefold())


def _find(folder: Path, patterns, limit: int = MAX_FIND) -> tuple[list[Path], bool]:
    """Search below ``folder`` for files matching any pattern, breadth-first."""

    hits: list[Path] = []
    queue = [(folder, 0)]
    while queue:
        current, depth = queue.pop(0)
        try:
            with os.scandir(current) as entries:
                children = sorted(entries, key=lambda item: item.name.casefold())
        except OSError:
            continue
        for entry in children:
            try:
                if entry.is_dir():
                    if depth + 1 < FIND_MAX_DEPTH and not entry.name.startswith("."):
                        queue.append((Path(entry.path), depth + 1))
                    continue
            except OSError:
                continue
            if not patterns or any(fnmatch.fnmatch(entry.name, p) for p in patterns):
                hits.append(Path(entry.path))
                if len(hits) >= limit:
                    return hits, True
    return hits, False


def _selection_rows(selection) -> list[dict]:
    rows = []
    for item in selection:
        path = Path(item)
        try:
            size = human_size(path.stat().st_size) if path.is_file() else "—"
            available = True
        except OSError:
            size, available = "—", False
        rows.append(
            {
                "name": path.name,
                "size": size,
                "folder": str(path.parent),
                "available": available,
                "path": str(path),
            }
        )
    return rows


def run_shell_command(
    command: str,
    cwd: str | Path,
    *,
    selection=(),
    path_mappings=(),
    config_root=None,
) -> ShellResult:
    """Run one command and return what it produced.

    ``selection`` is the current list of full paths; the returned result carries
    the list the command leaves behind, and sets ``selection_changed`` when it
    differs so the caller knows to persist it.
    """

    current = Path(cwd).expanduser().resolve(strict=False)
    selection = tuple(selection)
    try:
        parts = _split_command(command)
    except ValueError as exc:
        return ShellResult(str(current), error=str(exc), selection=selection)
    if not parts:
        return ShellResult(str(current), error="Type a command, or `help`.", selection=selection)

    verb, *arguments = parts
    verb = verb.lower()

    def ok(**kwargs) -> ShellResult:
        kwargs.setdefault("selection", selection)
        return ShellResult(str(current), **kwargs)

    def fail(message: str) -> ShellResult:
        return ShellResult(str(current), error=message, selection=selection)

    def resolve(value: str) -> Path:
        mapped, _mapping = translate_remote_path(value, path_mappings)
        return resolve_browser_path(mapped, current)

    # -- navigation --------------------------------------------------------
    if verb == "help":
        return ok(output=COMMAND_HELP)

    if verb == "pwd":
        return ok(output=str(current))

    if verb == "cd":
        if not arguments:
            return fail("cd needs a folder, for example `cd cir_avg` or `cd ..`.")
        target = resolve(arguments[0])
        if not target.is_dir():
            return fail(f"Not an available folder: {target}")
        rows, truncated = list_directory(target)
        suffix = f" (first {MAX_LIST} entries)" if truncated else ""
        return ShellResult(str(target), output=f"{target}{suffix}", rows=rows, selection=selection)

    if verb in {"ls", "dir"}:
        patterns = [item for item in arguments if any(c in item for c in "*?[")]
        plain = [item for item in arguments if item not in patterns]
        target = resolve(plain[0]) if plain else current
        if not target.is_dir():
            return fail(f"Not an available folder: {target}")
        if patterns:
            hits = _match_names(target, patterns, files_only=False)
            rows = [
                {
                    "name": item.name,
                    "size": human_size(item.stat().st_size) if item.is_file() else "—",
                    "type": "file" if item.is_file() else "folder",
                    "path": str(item),
                }
                for item in hits
            ]
            return ok(output=f"{len(rows)} match(es) in {target}", rows=rows)
        rows, truncated = list_directory(target)
        suffix = f" (first {MAX_LIST} entries)" if truncated else ""
        return ok(output=f"{target}{suffix}", rows=rows)

    if verb == "du":
        target = resolve(arguments[0]) if arguments else current
        try:
            size, files, truncated = directory_size(target)
        except OSError as exc:
            return fail(str(exc))
        note = f"; stopped after {files:,} files" if truncated else ""
        return ok(output=f"{human_size(size)}  {target}  ({files:,} files{note})")

    if verb == "find":
        if not arguments:
            return fail("find needs a pattern, for example `find *UV_2*`.")
        hits, truncated = _find(current, arguments)
        rows = [{"name": item.name, "folder": str(item.parent), "path": str(item)} for item in hits]
        note = f" (stopped at {MAX_FIND})" if truncated else ""
        return ok(output=f"{len(rows)} match(es) below {current}{note}", rows=rows)

    # -- reading a file ----------------------------------------------------
    if verb in {"cat", "head", "tail"}:
        if not arguments:
            return fail(f"{verb} needs a file name.")
        count = CAT_MAX_LINES if verb == "cat" else 40
        names = list(arguments)
        if "-n" in names:
            index = names.index("-n")
            try:
                count = max(1, min(CAT_MAX_LINES, int(names[index + 1])))
            except (IndexError, ValueError):
                return fail("-n needs a number, for example `cat file.csv -n 20`.")
            del names[index : index + 2]
        if not names:
            return fail(f"{verb} needs a file name.")
        target = resolve(names[0])
        if not target.is_file():
            return fail(f"Not an available file: {target}")
        if not _is_text(target):
            return fail(f"{target.name} is not a text file.")
        try:
            with target.open("r", encoding="utf-8", errors="replace") as handle:
                lines = handle.read(CAT_MAX_BYTES).splitlines()
        except OSError as exc:
            return fail(str(exc))
        shown = lines[-count:] if verb == "tail" else lines[:count]
        header = f"{target}  ({len(lines)} line(s) read)"
        return ok(output=header + "\n" + "\n".join(shown))

    if verb == "wc":
        if not arguments:
            return fail("wc needs a file or a pattern.")
        patterns = [item for item in arguments if any(c in item for c in "*?[")]
        if patterns:
            hits = _match_names(current, patterns)
            return ok(output=f"{len(hits)} file(s) match {' '.join(patterns)} in {current}")
        target = resolve(arguments[0])
        if not target.is_file():
            return fail(f"Not an available file: {target}")
        if not _is_text(target):
            return fail(f"{target.name} is not a text file.")
        try:
            with target.open("r", encoding="utf-8", errors="replace") as handle:
                total = sum(1 for _ in handle)
        except OSError as exc:
            return fail(str(exc))
        return ok(output=f"{total:,} lines  {target}")

    # -- building the list -------------------------------------------------
    if verb == "select":
        patterns = arguments or ["*"]
        hits = _match_names(current, patterns, limit=MAX_SELECT)
        added = [str(item) for item in hits if str(item) not in selection]
        updated = (*selection, *added)
        return ShellResult(
            str(current),
            output=f"Added {len(added)} file(s); the list now holds {len(updated)}.",
            rows=_selection_rows(added),
            selection=updated,
            selection_changed=bool(added),
        )

    if verb == "unselect":
        if not arguments:
            return fail("unselect needs a pattern, for example `unselect *AgBH*`.")
        kept = [
            item
            for item in selection
            if not any(fnmatch.fnmatch(Path(item).name, p) for p in arguments)
        ]
        removed = len(selection) - len(kept)
        return ShellResult(
            str(current),
            output=f"Removed {removed} file(s); the list now holds {len(kept)}.",
            selection=tuple(kept),
            selection_changed=bool(removed),
        )

    if verb == "list":
        if not selection:
            return ok(output="The list is empty. Use `select <pattern>` to fill it.")
        return ok(output=f"{len(selection)} file(s) in the list", rows=_selection_rows(selection))

    if verb == "clear":
        return ShellResult(
            str(current),
            output="The list is now empty.",
            selection=(),
            selection_changed=bool(selection),
        )

    if verb == "save":
        if not arguments:
            return fail("save needs a name, for example `save uv_series`.")
        if not selection:
            return fail("The list is empty, so there is nothing to save.")
        try:
            written = save_collection(arguments[0], selection, config_root=config_root)
        except (ValueError, OSError) as exc:
            return fail(str(exc))
        return ok(output=f"Saved {len(selection)} path(s) as `{arguments[0]}` → {written}")

    if verb == "load":
        if not arguments:
            return fail("load needs a name. Use `lists` to see what is saved.")
        try:
            payload = load_collection(arguments[0], config_root=config_root)
        except ValueError as exc:
            return fail(str(exc))
        loaded = tuple(payload["paths"])
        return ShellResult(
            str(current),
            output=f"Loaded `{payload['name']}` — {len(loaded)} path(s).",
            rows=_selection_rows(loaded),
            selection=loaded,
            selection_changed=loaded != selection,
        )

    if verb == "lists":
        saved = list_collections(config_root)
        if not saved:
            return ok(output="No saved lists yet. Build one and use `save <name>`.")
        rows = [
            {"name": item["name"], "paths": item["count"], "saved": item["saved"]} for item in saved
        ]
        return ok(output=f"{len(rows)} saved list(s)", rows=rows)

    return fail(f"Unsupported command: {verb}. Type `help` to see what is available.")
