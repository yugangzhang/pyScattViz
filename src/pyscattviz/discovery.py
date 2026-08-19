"""Folder and file discovery with AND / OR / EXCLUDE term lists.

This module reproduces the selection logic I have used for years in my
``pyScatt`` ``ls_dir`` helper and extends it to whole directory trees, so a
collaborator can point pyScattViz at a proposal root and ask for something like
"every folder whose path contains ``microbeam`` and either ``giwaxs`` or
``gisaxs``, but never ``AgBH``".

Three term lists drive every query:

``and_list``
    Every term must match.
``or_list``
    At least one term must match.
``no_list``
    No term may match.

A term is a plain substring unless it contains a shell wildcard (``*``, ``?``,
``[``), in which case it is matched against the whole name. Matching ignores
case by default because beamline filenames mix conventions freely.

The module is deliberately free of Streamlit and of any global state so it can
be used from notebooks and scripts::

    from pyscattviz.discovery import find_folders, ls_dir

    ls_dir("/nsls2/data/smi/.../giwaxs/cir_avg", and_list=["Kim"], no_list=["AgBH"])
    find_folders(["/mnt/proposal"], and_list=["Results"], or_list=["giwaxs", "gisaxs"])
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path

from pyscattviz.filters import term_matches

__all__ = [
    "DATA_EXTENSIONS",
    "PRODUCT_FOLDERS",
    "classify_folder",
    "describe_paths",
    "filter_names",
    "find_files",
    "find_folders",
    "ls_dir",
    "matches_terms",
    "parse_terms",
]

# Reduction product folders written by the CMS/SMI auto-reduction. A folder
# holding any of these is worth offering directly to a scattering explorer.
PRODUCT_FOLDERS = ("cir_avg", "q_image", "qphi", "qc", "stitched")

# File extensions the viewer can actually open, grouped by how they are used.
DATA_EXTENSIONS = {
    "curve": (".csv", ".txt", ".dat", ".chi", ".xy"),
    "array": (".npz", ".npy"),
    "image": (".tif", ".tiff", ".png", ".jpg", ".jpeg"),
}

# Directories that never contain user data and are expensive to walk.
_SKIP_DIRS = {
    ".git",
    ".ipynb_checkpoints",
    "__pycache__",
    ".cache",
    ".Trash",
    "$RECYCLE.BIN",
    "System Volume Information",
    "node_modules",
    ".venv",
}


def parse_terms(text: str | Iterable[str] | None) -> tuple[str, ...]:
    """Split a user-entered term list on commas, semicolons, and newlines.

    Quotes are stripped so ``"sample one", sample_two`` yields two terms, and
    a line starting with ``#`` is treated as a comment. Order is preserved and
    duplicates are removed.
    """

    if text is None:
        return ()
    chunks = [text] if isinstance(text, str) else list(text)
    terms: list[str] = []
    for chunk in chunks:
        normalized = str(chunk).replace(",", "\n").replace(";", "\n")
        for line in normalized.splitlines():
            item = line.strip().strip('"').strip("'").strip()
            if item and not item.startswith("#"):
                terms.append(item)
    return tuple(dict.fromkeys(terms))


def matches_terms(
    value: str,
    and_list: Sequence[str] = (),
    or_list: Sequence[str] = (),
    no_list: Sequence[str] = (),
    case_sensitive: bool = False,
) -> bool:
    """Apply the AND / OR / EXCLUDE term lists to one name.

    An empty list imposes no condition, so ``matches_terms(name)`` is True.
    """

    for term in and_list:
        if not term_matches(term, value, case_sensitive):
            return False
    if or_list and not any(term_matches(term, value, case_sensitive) for term in or_list):
        return False
    for term in no_list:
        if term_matches(term, value, case_sensitive):
            return False
    return True


def filter_names(
    names: Iterable[str],
    and_list: Sequence[str] = (),
    or_list: Sequence[str] = (),
    no_list: Sequence[str] = (),
    case_sensitive: bool = False,
) -> list[str]:
    """Filter a list of names with the AND / OR / EXCLUDE term lists."""

    return [
        name for name in names if matches_terms(name, and_list, or_list, no_list, case_sensitive)
    ]


def ls_dir(
    in_dir: str | Path,
    and_list: Sequence[str] = (),
    or_list: Sequence[str] = (),
    no_list: Sequence[str] = (),
    kind: str = "all",
    case_sensitive: bool = False,
    full_path: bool = False,
) -> list[str]:
    """List the direct entries of one folder, filtered by the term lists.

    Parameters
    ----------
    in_dir
        Folder to list. It must already exist on this computer, either on a
        local disk or through a mount.
    and_list, or_list, no_list
        Term lists as described in the module docstring.
    kind
        ``"all"``, ``"file"``, or ``"folder"``.
    case_sensitive
        Match with case sensitivity. Off by default.
    full_path
        Return absolute paths instead of bare names.

    Returns
    -------
    list of str
        Sorted matching entries.
    """

    if kind not in {"all", "file", "folder"}:
        raise ValueError("kind must be all, file, or folder")
    folder = Path(in_dir).expanduser()
    results: list[str] = []
    with os.scandir(folder) as entries:
        for entry in entries:
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue
            if kind == "file" and is_dir:
                continue
            if kind == "folder" and not is_dir:
                continue
            if not matches_terms(entry.name, and_list, or_list, no_list, case_sensitive):
                continue
            results.append(str(Path(entry.path).resolve(strict=False)) if full_path else entry.name)
    return sorted(results, key=str.casefold)


def classify_folder(path: str | Path) -> dict:
    """Describe what a folder holds without opening any array.

    Returns the reduction products present directly below ``path``, whether
    ``path`` is itself a product folder, and a bounded count of the data files
    it contains.
    """

    folder = Path(path).expanduser()
    products: list[str] = []
    subfolders = 0
    data_files = 0
    every_extension = tuple(suffix for group in DATA_EXTENSIONS.values() for suffix in group)
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                try:
                    if entry.is_dir():
                        subfolders += 1
                        if entry.name in PRODUCT_FOLDERS:
                            products.append(entry.name)
                    elif entry.name.lower().endswith(every_extension):
                        data_files += 1
                except OSError:
                    continue
    except OSError:
        return {
            "products": (),
            "is_product_folder": False,
            "data_files": 0,
            "subfolders": 0,
            "available": False,
        }
    ordered = tuple(name for name in PRODUCT_FOLDERS if name in products)
    return {
        "products": ordered,
        "is_product_folder": folder.name in PRODUCT_FOLDERS,
        "data_files": data_files,
        "subfolders": subfolders,
        "available": True,
    }


def _walk(
    root: Path,
    max_depth: int,
    skip_hidden: bool,
    follow_symlinks: bool,
    max_visited: int,
):
    """Yield ``(path, depth, is_dir)`` breadth-first with a bounded budget.

    Breadth-first ordering matters over a network mount: the folders a user
    actually wants are usually near the top, so a truncated search still
    returns useful results.
    """

    queue = [(root, 0)]
    visited = 0
    while queue:
        folder, depth = queue.pop(0)
        try:
            with os.scandir(folder) as entries:
                children = list(entries)
        except OSError:
            continue
        children.sort(key=lambda item: item.name.casefold())
        for entry in children:
            visited += 1
            if visited > max_visited:
                return
            name = entry.name
            if skip_hidden and (name.startswith(".") or name in _SKIP_DIRS):
                continue
            try:
                is_dir = entry.is_dir(follow_symlinks=follow_symlinks)
            except OSError:
                continue
            yield Path(entry.path), depth + 1, is_dir
            if is_dir and depth + 1 < max_depth:
                queue.append((Path(entry.path), depth + 1))


def _roots(roots: str | Path | Iterable[str | Path]) -> list[Path]:
    values = [roots] if isinstance(roots, (str, Path)) else list(roots)
    resolved: list[Path] = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        candidate = Path(text).expanduser()
        if candidate.is_dir():
            resolved.append(candidate.resolve(strict=False))
    unique: list[Path] = []
    for item in resolved:
        if item not in unique:
            unique.append(item)
    return unique


def find_folders(
    roots: str | Path | Iterable[str | Path],
    and_list: Sequence[str] = (),
    or_list: Sequence[str] = (),
    no_list: Sequence[str] = (),
    *,
    match_on: str = "name",
    max_depth: int = 4,
    max_results: int = 1_000,
    max_visited: int = 200_000,
    products_only: bool = False,
    describe_products: bool = True,
    case_sensitive: bool = False,
    skip_hidden: bool = True,
    follow_symlinks: bool = False,
) -> tuple[list[dict], bool]:
    """Search one or more roots for folders matching the term lists.

    Parameters
    ----------
    roots
        One path, or several. Unavailable roots are skipped silently so a
        disconnected mount does not abort the search.
    match_on
        ``"name"`` matches the folder name only; ``"path"`` matches the whole
        absolute path, which is what makes ``Results AND giwaxs`` work.
    max_depth
        How many levels below each root to descend. Keep this small on a
        network mount.
    max_results
        Stop after this many matches. The second return value reports whether
        the search was cut short.
    max_visited
        Hard ceiling on directory entries inspected below each root, so a
        mistyped filter over ``/nsls2/data`` cannot run forever.
    products_only
        Keep only folders that directly contain a reduction product folder
        (``cir_avg``, ``q_image``, ``qphi``, ``qc``, ``stitched``) or are one.
    describe_products
        Report which products and how many data files each match holds. This
        costs one extra directory listing per match, which is free locally and
        noticeable over SFTP; turn it off for a fast first pass. It is forced on
        when ``products_only`` is requested, since that filter needs it.

    Returns
    -------
    (rows, truncated)
        ``rows`` are dictionaries suitable for a dataframe, each with
        ``name``, ``path``, ``parent``, ``root``, ``depth``, ``products``,
        ``data_files``, and ``modified``.
    """

    if match_on not in {"name", "path"}:
        raise ValueError("match_on must be name or path")
    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")

    rows: list[dict] = []
    truncated = False
    for root in _roots(roots):
        for path, depth, is_dir in _walk(
            root, max_depth, skip_hidden, follow_symlinks, max_visited
        ):
            if not is_dir:
                continue
            subject = str(path) if match_on == "path" else path.name
            if not matches_terms(subject, and_list, or_list, no_list, case_sensitive):
                continue
            summary = None
            if describe_products or products_only:
                summary = classify_folder(path)
                if products_only and not (summary["products"] or summary["is_product_folder"]):
                    continue
            if len(rows) >= max_results:
                truncated = True
                break
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                modified = "—"
            rows.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "parent": str(path.parent),
                    "root": str(root),
                    "depth": depth,
                    "products": ", ".join(summary["products"]) or "—" if summary else "—",
                    "data_files": summary["data_files"] if summary else None,
                    "modified": modified,
                }
            )
        if truncated:
            break
    rows.sort(key=lambda row: row["path"].casefold())
    return rows, truncated


def find_files(
    roots: str | Path | Iterable[str | Path],
    and_list: Sequence[str] = (),
    or_list: Sequence[str] = (),
    no_list: Sequence[str] = (),
    *,
    extensions: Sequence[str] = (),
    match_on: str = "name",
    max_depth: int = 4,
    max_results: int = 5_000,
    max_visited: int = 200_000,
    case_sensitive: bool = False,
    skip_hidden: bool = True,
    follow_symlinks: bool = False,
) -> tuple[list[dict], bool]:
    """Search one or more roots for data files matching the term lists.

    ``extensions`` is an optional allow-list such as ``(".csv", ".npz")``; an
    empty value accepts every extension pyScattViz can open. Only names and
    directory entries are inspected — no file contents are read.
    """

    if match_on not in {"name", "path"}:
        raise ValueError("match_on must be name or path")
    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")

    allowed = tuple(
        suffix.lower() if suffix.startswith(".") else "." + suffix.lower() for suffix in extensions
    )
    if not allowed:
        allowed = tuple(suffix for group in DATA_EXTENSIONS.values() for suffix in group)

    rows: list[dict] = []
    truncated = False
    for root in _roots(roots):
        for path, depth, is_dir in _walk(
            root, max_depth, skip_hidden, follow_symlinks, max_visited
        ):
            if is_dir:
                continue
            if path.suffix.lower() not in allowed:
                continue
            subject = str(path) if match_on == "path" else path.name
            if not matches_terms(subject, and_list, or_list, no_list, case_sensitive):
                continue
            if len(rows) >= max_results:
                truncated = True
                break
            try:
                stat = path.stat()
                size = stat.st_size
                modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                size, modified = 0, "—"
            rows.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "parent": str(path.parent),
                    "root": str(root),
                    "depth": depth,
                    "suffix": path.suffix.lower(),
                    "size": size,
                    "modified": modified,
                }
            )
        if truncated:
            break
    rows.sort(key=lambda row: row["path"].casefold())
    return rows, truncated


def describe_paths(paths: Iterable[str | Path]) -> list[dict]:
    """Report availability and kind for a pasted or saved list of full paths."""

    described: list[dict] = []
    for value in paths:
        text = str(value).strip()
        if not text:
            continue
        candidate = Path(text).expanduser()
        try:
            is_dir = candidate.is_dir()
            is_file = candidate.is_file()
        except OSError:
            is_dir = is_file = False
        kind = "folder" if is_dir else ("file" if is_file else "missing")
        entry = {
            "path": str(candidate),
            "name": candidate.name or str(candidate),
            "kind": kind,
            "available": is_dir or is_file,
            "products": "—",
        }
        if is_dir:
            summary = classify_folder(candidate)
            entry["products"] = ", ".join(summary["products"]) or "—"
        described.append(entry)
    return described
