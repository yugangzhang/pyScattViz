"""Cached file collection and loading for the free-form plotting pages.

The scattering explorers know exactly where their products live. Quick Plot
does not: it is handed a basket of full paths that may be folders, files, or a
mixture, and has to turn that into something plottable without reading more
than it must. These helpers do that, with Streamlit caching keyed on the file's
modification time so a re-reduced file is picked up rather than served stale.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import streamlit as st

from pyscattviz.dataio import (
    ARRAY_SUFFIXES,
    CURVE_SUFFIXES,
    IMAGE_SUFFIXES,
    read_arrays,
    read_curve,
    read_image,
    read_table,
)
from pyscattviz.discovery import find_files, matches_terms

__all__ = [
    "cached_arrays",
    "cached_curve",
    "cached_image",
    "cached_table",
    "collect_files",
    "file_signature",
]


def file_signature(path: str | Path) -> tuple[str, float, int]:
    """Return a cache key that changes when the file itself changes."""

    target = Path(path)
    try:
        stat = target.stat()
    except OSError:
        return (str(target), 0.0, -1)
    return (str(target), stat.st_mtime, stat.st_size)


@st.cache_data(show_spinner=False, max_entries=512)
def cached_curve(path: str, x_column: str | None, y_column: str | None, _signature):
    """Read one x/y curve, re-reading only when the file changes."""

    return read_curve(path, x_column, y_column)


@st.cache_data(show_spinner=False, max_entries=64)
def cached_image(path: str, _signature):
    """Read one detector or QC image as a 2D float array."""

    return read_image(path)


@st.cache_data(show_spinner=False, max_entries=64)
def cached_arrays(path: str, _signature):
    """Read an NPY/NPZ archive into named arrays."""

    return read_arrays(path)


@st.cache_data(show_spinner=False, max_entries=128)
def cached_table(path: str, _signature):
    """Read a delimited text file into a numeric table."""

    return read_table(path)


def collect_files(
    paths: Iterable[str | Path],
    *,
    extensions: Sequence[str] = (),
    and_list: Sequence[str] = (),
    or_list: Sequence[str] = (),
    no_list: Sequence[str] = (),
    max_depth: int = 3,
    max_files: int = 5_000,
) -> tuple[list[str], bool]:
    """Expand a mixed basket of folders and files into a plottable file list.

    Files given directly are kept if they pass the term lists and the extension
    allow-list; folders are searched to ``max_depth``. Order follows the basket,
    then the sorted search result of each folder, so a user's own ordering
    survives.
    """

    allowed = tuple(
        suffix.lower() if suffix.startswith(".") else "." + suffix.lower()
        for suffix in extensions
    )
    if not allowed:
        allowed = (*CURVE_SUFFIXES, *ARRAY_SUFFIXES, *IMAGE_SUFFIXES)

    collected: list[str] = []
    truncated = False
    for value in paths:
        if len(collected) >= max_files:
            truncated = True
            break
        candidate = Path(str(value)).expanduser()
        try:
            is_dir = candidate.is_dir()
            is_file = candidate.is_file()
        except OSError:
            continue
        if is_file:
            if candidate.suffix.lower() not in allowed:
                continue
            if not matches_terms(candidate.name, and_list, or_list, no_list):
                continue
            text = str(candidate)
            if text not in collected:
                collected.append(text)
        elif is_dir:
            rows, folder_truncated = find_files(
                candidate,
                and_list,
                or_list,
                no_list,
                extensions=allowed,
                max_depth=max_depth,
                max_results=max_files - len(collected),
            )
            truncated = truncated or folder_truncated
            for row in rows:
                if row["path"] not in collected:
                    collected.append(row["path"])
    return collected[:max_files], truncated or len(collected) > max_files
