"""Small, cross-platform filesystem browser for local and mounted data."""

from __future__ import annotations

import os
import shlex
from datetime import datetime
from pathlib import Path

from pyscattviz.data_sources import translate_remote_path


def human_size(size: int) -> str:
    """Format a byte count for the folder browser."""

    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if value < 1024 or unit == "PiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PiB"


def resolve_browser_path(value: str, cwd: str | Path) -> Path:
    """Resolve an absolute or cwd-relative path without requiring it to exist."""

    text = value.strip() or "."
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = Path(cwd) / candidate
    return candidate.resolve(strict=False)


def list_directory(path: str | Path, limit: int = 500) -> tuple[list[dict], bool]:
    """Return a bounded, directories-first listing suitable for a dataframe."""

    folder = Path(path)
    rows = []
    with os.scandir(folder) as entries:
        for entry in entries:
            try:
                is_dir = entry.is_dir()
                stat = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            rows.append(
                {
                    "name": entry.name + (os.sep if is_dir else ""),
                    "type": "folder" if is_dir else "file",
                    "size": "—" if is_dir else human_size(stat.st_size),
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "path": str(Path(entry.path).resolve(strict=False)),
                    "is_dir": is_dir,
                }
            )
            if len(rows) > limit:
                break
    rows.sort(key=lambda row: (not row["is_dir"], row["name"].casefold()))
    truncated = len(rows) > limit
    return rows[:limit], truncated


def directory_size(path: str | Path, max_files: int = 5_000) -> tuple[int, int, bool]:
    """Calculate a bounded recursive size, avoiding an unlimited network scan."""

    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"Path is not available: {target}")
    if target.is_file():
        return target.stat().st_size, 1, False

    total = 0
    files = 0
    for root, _directories, names in os.walk(target):
        for name in names:
            if files >= max_files:
                return total, files, True
            try:
                total += (Path(root) / name).stat().st_size
                files += 1
            except OSError:
                continue
    return total, files, False


def _split_command(command: str, windows: bool | None = None) -> list[str]:
    """Split a command while preserving Windows backslashes and removing quotes."""

    use_windows_rules = os.name == "nt" if windows is None else windows
    parts = shlex.split(command, posix=not use_windows_rules)
    if use_windows_rules:
        parts = [
            part[1:-1] if len(part) >= 2 and part[0] == part[-1] and part[0] in {'"', "'"} else part
            for part in parts
        ]
    return parts


def run_browser_command(command: str, cwd: str | Path, path_mappings=()) -> dict:
    """Run one safe browser command without invoking a system shell.

    Supported commands intentionally mirror the read-only shell operations
    useful for finding reduction data: ``pwd``, ``ls [path]``, ``cd <path>``,
    and ``du [path]``.
    """

    current = Path(cwd).expanduser().resolve(strict=False)
    try:
        parts = _split_command(command)
    except ValueError as exc:
        return {"cwd": str(current), "output": "", "rows": [], "error": str(exc)}
    if not parts:
        return {
            "cwd": str(current),
            "output": "",
            "rows": [],
            "error": "Enter pwd, ls [path], cd <path>, or du [path].",
        }

    operation, *arguments = parts
    if operation not in {"pwd", "ls", "cd", "du"}:
        return {
            "cwd": str(current),
            "output": "",
            "rows": [],
            "error": f"Unsupported command: {operation}. Use pwd, ls, cd, or du.",
        }
    if operation == "pwd":
        if arguments:
            error = "pwd does not take a path."
        else:
            return {"cwd": str(current), "output": str(current), "rows": [], "error": None}
    elif len(arguments) > 1:
        error = f"{operation} accepts one path; quote paths that contain spaces."
    else:
        requested_path = arguments[0] if arguments else "."
        mapped_path, _mapping = translate_remote_path(requested_path, path_mappings)
        target = resolve_browser_path(mapped_path, current)
        try:
            if operation == "cd":
                if not target.is_dir():
                    raise NotADirectoryError(f"Not an available folder: {target}")
                rows, truncated = list_directory(target)
                suffix = " (first 500 entries)" if truncated else ""
                return {
                    "cwd": str(target),
                    "output": f"{target}{suffix}",
                    "rows": rows,
                    "error": None,
                }
            if operation == "ls":
                if not target.is_dir():
                    raise NotADirectoryError(f"Not an available folder: {target}")
                rows, truncated = list_directory(target)
                suffix = " (first 500 entries)" if truncated else ""
                return {
                    "cwd": str(current),
                    "output": f"{target}{suffix}",
                    "rows": rows,
                    "error": None,
                }
            size, files, truncated = directory_size(target)
            suffix = f"; partial result, stopped after {files:,} files" if truncated else ""
            return {
                "cwd": str(current),
                "output": f"{human_size(size)}  {target}  ({files:,} files{suffix})",
                "rows": [],
                "error": None,
            }
        except OSError as exc:
            error = str(exc)

    return {"cwd": str(current), "output": "", "rows": [], "error": error}
