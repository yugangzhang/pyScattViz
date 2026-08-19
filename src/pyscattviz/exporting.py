"""Save figures, tables, and arrays to a user-chosen folder on the local disk.

pyScattViz runs on the user's own computer, so a browser download is the long
way round: the application can write directly to whatever folder the user names.
This module owns that side of the work.

Two conventions keep a review session tidy:

* one **output root**, remembered between sessions in
  ``~/.pyscattviz/settings.json``; and
* one **subfolder per tab**, so a figure saved from the GIWAXS Explorer lands in
  ``<output root>/GIWAXS_Explorer/`` and never gets mixed up with the
  Publication Plot output.

Nothing here imports Streamlit, so the same functions work from a notebook::

    from pyscattviz.exporting import resolve_output_dir, save_matplotlib_figure

    folder = resolve_output_dir("~/pyScattViz_Output", "GIWAXS_Explorer", create=True)
    save_matplotlib_figure(fig, folder, "sample_A_cir_avg", fmt="png", dpi=300)
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

__all__ = [
    "ARRAY_FORMATS",
    "ExportError",
    "MATPLOTLIB_FORMATS",
    "PLOTLY_FORMATS",
    "TABLE_FORMATS",
    "default_output_root",
    "load_settings",
    "resolve_output_dir",
    "safe_component",
    "save_arrays",
    "save_matplotlib_figure",
    "save_plotly_figure",
    "save_settings",
    "save_table",
    "save_text",
    "settings_file",
    "timestamp_suffix",
    "unique_path",
]

MATPLOTLIB_FORMATS = ("png", "svg", "pdf", "eps", "tif")
PLOTLY_FORMATS = ("png", "svg", "pdf", "html", "json")
TABLE_FORMATS = ("csv", "txt")
ARRAY_FORMATS = ("npz", "npy")

_UNSAFE = re.compile(r"[^A-Za-z0-9._\- ]+")
_COLLAPSE = re.compile(r"[\s_]+")

DEFAULT_OUTPUT_DIRNAME = "pyScattViz_Output"

_KALEIDO_HELP = (
    "Saving a static Plotly image needs the free kaleido package. Install it with "
    "`python -m pip install kaleido`, then run `plotly_get_chrome` once if the "
    "computer has no Chrome or Chromium. HTML export always works without it."
)


class ExportError(RuntimeError):
    """Raised when a figure, table, or array could not be written to disk."""


def config_dir() -> Path:
    """Return the per-user pyScattViz configuration folder."""

    override = os.environ.get("PYSCATTVIZ_CONFIG_DIR")
    return Path(override).expanduser() if override else Path.home() / ".pyscattviz"


def settings_file() -> Path:
    """Return the JSON file holding user preferences such as the output root."""

    return config_dir() / "settings.json"


def default_output_root() -> Path:
    """Return the folder new installations save into.

    ``PYSCATTVIZ_OUTPUT_DIR`` overrides it, which is convenient when a user
    keeps figures on an external disk.
    """

    override = os.environ.get("PYSCATTVIZ_OUTPUT_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / DEFAULT_OUTPUT_DIRNAME


def load_settings() -> dict:
    """Load user preferences, returning defaults for a missing or bad file."""

    defaults = {
        "output_root": str(default_output_root()),
        "output_subfolder_per_tab": True,
        "output_date_subfolder": False,
        "output_overwrite": False,
    }
    try:
        payload = json.loads(settings_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    if not isinstance(payload, dict):
        return defaults
    merged = dict(defaults)
    for key, value in payload.items():
        if key in defaults and isinstance(value, type(defaults[key])):
            merged[key] = value
    return merged


def save_settings(settings: dict) -> Path:
    """Persist user preferences atomically and return the settings file path."""

    merged = load_settings()
    for key, value in settings.items():
        merged[key] = value
    target = settings_file()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def safe_component(name: str, fallback: str = "pyscattviz") -> str:
    """Turn a tab title or frame stem into a safe file/folder name component.

    Emoji, path separators, and other characters Windows rejects are removed;
    runs of whitespace become single underscores.
    """

    cleaned = _UNSAFE.sub(" ", str(name))
    cleaned = _COLLAPSE.sub("_", cleaned).strip("._- ")
    # Windows reserves these device names regardless of extension.
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    if not cleaned or cleaned.upper() in reserved:
        return fallback
    return cleaned[:120]


def timestamp_suffix(moment: datetime | None = None) -> str:
    """Return a sortable ``YYYYmmdd_HHMMSS`` stamp for filenames."""

    return (moment or datetime.now()).strftime("%Y%m%d_%H%M%S")


def resolve_output_dir(
    base: str | Path,
    *parts: str,
    create: bool = False,
    date_subfolder: bool = False,
) -> Path:
    """Build ``base/<part>/<part>/...`` from sanitized components.

    ``parts`` are usually a tab name and an optional sample or dataset name.
    Every component is sanitized, so a tab title such as ``"🧭 GIWAXS Explorer"``
    becomes the folder ``GIWAXS_Explorer``. Empty components are skipped.

    Set ``create`` to make the folder, and ``date_subfolder`` to append today's
    date, which keeps repeated sessions on the same sample separated.
    """

    root = Path(str(base).strip() or default_output_root()).expanduser()
    components = [safe_component(part) for part in parts if str(part).strip()]
    if date_subfolder:
        components.append(datetime.now().strftime("%Y-%m-%d"))
    target = root.joinpath(*components) if components else root
    if create:
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ExportError(f"Could not create the output folder {target}: {exc}") from exc
    return target


def unique_path(path: str | Path) -> Path:
    """Return ``path`` or the first free ``name_001.ext`` variant beside it."""

    candidate = Path(path)
    if not candidate.exists():
        return candidate
    stem, suffix, parent = candidate.stem, candidate.suffix, candidate.parent
    for index in range(1, 1000):
        alternative = parent / f"{stem}_{index:03d}{suffix}"
        if not alternative.exists():
            return alternative
    return parent / f"{stem}_{timestamp_suffix()}{suffix}"


def _target(directory: str | Path, name: str, fmt: str, overwrite: bool) -> Path:
    folder = Path(str(directory)).expanduser()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ExportError(f"Could not create the output folder {folder}: {exc}") from exc
    extension = fmt.lower().lstrip(".")
    # Beamline stems are full of decimal points — ``th0.1000deg`` — so the name
    # is sanitized whole rather than run through Path().stem, which would cut it
    # at the first dot. Only a duplicate extension is removed.
    stem = safe_component(str(name))
    if stem.lower().endswith("." + extension):
        stem = stem[: -(len(extension) + 1)].rstrip("._- ") or stem
    candidate = folder / f"{stem}.{extension}"
    return candidate if overwrite else unique_path(candidate)


def save_matplotlib_figure(
    figure,
    directory: str | Path,
    name: str,
    fmt: str = "png",
    dpi: int = 300,
    overwrite: bool = False,
    transparent: bool = False,
) -> Path:
    """Write a matplotlib figure into ``directory`` and return the file path."""

    fmt = fmt.lower().lstrip(".")
    if fmt not in MATPLOTLIB_FORMATS:
        raise ExportError(f"{fmt} is not a supported matplotlib format.")
    target = _target(directory, name, fmt, overwrite)
    try:
        figure.savefig(
            target,
            format=fmt,
            dpi=int(dpi),
            bbox_inches="tight",
            transparent=bool(transparent),
        )
    except (OSError, ValueError) as exc:
        raise ExportError(f"Could not save {target}: {exc}") from exc
    return target


def save_plotly_figure(
    figure,
    directory: str | Path,
    name: str,
    fmt: str = "png",
    scale: float = 2.0,
    width: int | None = None,
    height: int | None = None,
    overwrite: bool = False,
) -> Path:
    """Write an interactive Plotly figure into ``directory``.

    ``html`` always works and stays interactive. ``png``, ``svg``, and ``pdf``
    need the free ``kaleido`` package; when it is missing the error explains how
    to install it rather than failing silently.
    """

    fmt = fmt.lower().lstrip(".")
    if fmt not in PLOTLY_FORMATS:
        raise ExportError(f"{fmt} is not a supported Plotly format.")
    target = _target(directory, name, fmt, overwrite)
    try:
        if fmt == "html":
            figure.write_html(str(target), include_plotlyjs="cdn")
        elif fmt == "json":
            target.write_text(figure.to_json(), encoding="utf-8")
        else:
            figure.write_image(
                str(target),
                format=fmt,
                scale=float(scale),
                width=width,
                height=height,
            )
    except ImportError as exc:
        raise ExportError(_KALEIDO_HELP) from exc
    except (OSError, ValueError, RuntimeError) as exc:
        message = str(exc)
        lowered = message.lower()
        if "kaleido" in lowered:
            raise ExportError(_KALEIDO_HELP) from exc
        if "chrome" in lowered or "chromium" in lowered:
            raise ExportError(
                "kaleido renders a static image with a Chromium browser and could not "
                "find one. Run `plotly_get_chrome` once in the same environment, or "
                f"save as HTML instead. Original message: {message}"
            ) from exc
        raise ExportError(f"Could not save {target}: {message}") from exc
    return target


def save_table(
    table,
    directory: str | Path,
    name: str,
    fmt: str = "csv",
    overwrite: bool = False,
) -> Path:
    """Write a pandas DataFrame as CSV or whitespace-aligned text."""

    fmt = fmt.lower().lstrip(".")
    if fmt not in TABLE_FORMATS:
        raise ExportError(f"{fmt} is not a supported table format.")
    target = _target(directory, name, fmt, overwrite)
    try:
        if fmt == "csv":
            table.to_csv(target, index=False)
        else:
            table.to_csv(target, index=False, sep="\t")
    except (OSError, ValueError) as exc:
        raise ExportError(f"Could not save {target}: {exc}") from exc
    return target


def save_arrays(
    arrays,
    directory: str | Path,
    name: str,
    fmt: str = "npz",
    overwrite: bool = False,
) -> Path:
    """Write one array (``npy``) or a dictionary of named arrays (``npz``)."""

    import numpy as np

    fmt = fmt.lower().lstrip(".")
    if fmt not in ARRAY_FORMATS:
        raise ExportError(f"{fmt} is not a supported array format.")
    target = _target(directory, name, fmt, overwrite)
    try:
        if fmt == "npy":
            payload = arrays
            if isinstance(arrays, dict):
                if len(arrays) != 1:
                    raise ExportError("npy holds a single array; choose npz instead.")
                payload = next(iter(arrays.values()))
            np.save(target, np.asarray(payload), allow_pickle=False)
        else:
            bundle = arrays if isinstance(arrays, dict) else {"array": arrays}
            np.savez_compressed(
                target, **{str(key): np.asarray(value) for key, value in bundle.items()}
            )
    except (OSError, ValueError, TypeError) as exc:
        raise ExportError(f"Could not save {target}: {exc}") from exc
    return target


def save_text(
    text: str,
    directory: str | Path,
    name: str,
    fmt: str = "txt",
    overwrite: bool = False,
) -> Path:
    """Write a plain-text file, such as a selected-filename list."""

    target = _target(directory, name, fmt, overwrite)
    try:
        target.write_text(str(text), encoding="utf-8")
    except OSError as exc:
        raise ExportError(f"Could not save {target}: {exc}") from exc
    return target
