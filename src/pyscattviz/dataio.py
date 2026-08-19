"""Read the data files a user hands pyScattViz, whatever shape they arrive in.

The scattering explorers know the CMS/SMI reduction layout exactly. This module
covers the other half of the problem: a collaborator gives me a plain list of
full paths — circular averages from one beamline, a two-column ``.dat`` from a
lab instrument, an ``.npz`` from a colleague's script, a detector ``.tif`` — and
expects a plot.

Everything is read from a normal filesystem path, with Python object pickles
disabled for NumPy archives, and nothing is loaded until the file is actually
selected for plotting.
"""

from __future__ import annotations

import re
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

__all__ = [
    "CURVE_SUFFIXES",
    "IMAGE_SUFFIXES",
    "ARRAY_SUFFIXES",
    "DataReadError",
    "common_prefix_suffix",
    "curve_columns",
    "guess_kind",
    "integrate_curve",
    "read_arrays",
    "read_curve",
    "read_image",
    "read_table",
    "short_label",
    "stack_curves",
]

CURVE_SUFFIXES = (".csv", ".txt", ".dat", ".chi", ".xy")
ARRAY_SUFFIXES = (".npz", ".npy")
IMAGE_SUFFIXES = (".tif", ".tiff", ".png", ".jpg", ".jpeg")

# Column names the beamline reductions use for q and I(q), in preference order.
_Q_NAMES = ("q_ca", "q", "qval", "q_a-1", "q(a-1)", "qr", "twotheta", "2theta", "x")
_I_NAMES = ("iq_ca", "iq", "i", "intensity", "int", "i(q)", "counts", "y")

_DELIMITERS = (",", "\t", ";", "|")

# Words that make a commented line credible as a column header rather than a
# free-text note. A comment such as "# q  I  sigma" is a header; "# sample B"
# is not, and letting it through would rename the columns to nonsense.
_AXIS_WORDS = (
    "q",
    "qr",
    "qx",
    "qy",
    "qz",
    "i",
    "iq",
    "int",
    "intensity",
    "counts",
    "cts",
    "sigma",
    "sig",
    "err",
    "error",
    "std",
    "esd",
    "x",
    "y",
    "z",
    "theta",
    "twotheta",
    "tth",
    "2theta",
    "chi",
    "phi",
    "psi",
    "angle",
    "d",
    "dspacing",
    "r",
    "t",
    "time",
    "frame",
    "index",
    "wavelength",
    "energy",
    "temperature",
    "temp",
    "pressure",
    "azimuth",
    "radius",
    "pixel",
    "channel",
)
_TOKEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.^()\[\]/%+*-]*$")


class DataReadError(ValueError):
    """Raised when a file cannot be read as a curve, table, image, or array."""


# NumPy renamed ``trapz`` to ``trapezoid`` in 2.0 and deprecated the old spelling.
# Users install whatever NumPy their environment already has, so accept both.
_TRAPEZOID = getattr(np, "trapezoid", None) or np.trapz


def integrate_curve(y, x) -> float:
    """Return the trapezoidal integral of a curve, on any supported NumPy."""

    return float(_TRAPEZOID(np.asarray(y, dtype=float), np.asarray(x, dtype=float)))


def guess_kind(path: str | Path) -> str:
    """Classify a path as ``"curve"``, ``"array"``, ``"image"``, or ``"other"``."""

    suffix = Path(path).suffix.lower()
    if suffix in CURVE_SUFFIXES:
        return "curve"
    if suffix in ARRAY_SUFFIXES:
        return "array"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    return "other"


def _is_number(token: str) -> bool:
    try:
        float(token)
    except ValueError:
        return False
    return True


def _split(line: str, delimiter: str | None) -> list[str]:
    if delimiter is None:
        return line.split()
    return [field.strip() for field in line.split(delimiter)]


def _looks_like_axis_names(names: Sequence[str]) -> bool:
    """True when every token of a commented line reads like a column name."""

    for name in names:
        token = str(name).strip()
        if not _TOKEN.match(token):
            return False
        core = re.split(r"[^A-Za-z0-9]", token.lower(), maxsplit=1)[0]
        if not core or core not in _AXIS_WORDS:
            return False
    return True


def _sniff_layout(path: Path, max_probe: int = 400) -> tuple[str | None, int, list[str] | None]:
    """Return ``(delimiter, skiprows, header_names)`` for a text table.

    Beamline one-dimensional files are wildly inconsistent: Fit2D ``.chi`` has
    four free-text header lines, CMS circular averages have a comma header,
    other tools write bare whitespace columns with a ``#`` comment block. The
    probe finds the first line that parses as at least two numbers and treats a
    non-numeric line directly above it as the column header.
    """

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            lines = [handle.readline() for _ in range(max_probe)]
    except OSError as exc:
        raise DataReadError(f"Could not open {path.name}: {exc}") from exc

    lines = [line.rstrip("\r\n") for line in lines if line]
    if not lines:
        raise DataReadError(f"{path.name} is empty.")

    best: tuple[str | None, int, list[str] | None] | None = None
    for delimiter in (*_DELIMITERS, None):
        for index, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", ";", "!")):
                continue
            fields = _split(stripped, delimiter)
            if len(fields) < 2 or not all(_is_number(field) for field in fields if field != ""):
                continue
            header: list[str] | None = None
            for previous in range(index - 1, -1, -1):
                raw = lines[previous].strip()
                if not raw:
                    continue
                is_comment = raw.startswith(("#", ";", "!"))
                candidate = raw.lstrip("#;!").strip()
                names = _split(candidate, delimiter)
                usable = len(names) == len(fields) and not all(_is_number(name) for name in names)
                if usable and (not is_comment or _looks_like_axis_names(names)):
                    header = [name.strip() or f"column_{i}" for i, name in enumerate(names)]
                break
            layout = (delimiter, index, header)
            if best is None or len(fields) > len(_split(lines[best[1]].strip(), best[0])):
                best = layout
            break
    if best is None:
        raise DataReadError(f"{path.name} has no numeric data columns.")
    return best


def read_table(path: str | Path, max_rows: int | None = None) -> pd.DataFrame:
    """Read a delimited text file into a numeric DataFrame.

    Comment blocks, missing headers, and comma/tab/semicolon/whitespace
    delimiters are all handled. Columns that hold no numbers are dropped.
    """

    target = Path(path).expanduser()
    delimiter, skiprows, header = _sniff_layout(target)
    separator = r"\s+" if delimiter is None else re.escape(delimiter)
    try:
        table = pd.read_csv(
            target,
            sep=separator,
            engine="python",
            skiprows=skiprows,
            header=None,
            names=header,
            nrows=max_rows,
            comment="#",
            skip_blank_lines=True,
        )
    except (OSError, UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
        raise DataReadError(f"Could not read {target.name} as a table: {exc}") from exc

    if header is None:
        table.columns = [f"column_{index}" for index in range(table.shape[1])]
    numeric = table.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
    if numeric.empty or numeric.shape[1] < 1:
        raise DataReadError(f"{target.name} contains no numeric columns.")
    return numeric


def read_arrays(path: str | Path) -> dict[str, np.ndarray]:
    """Read an NPY/NPZ archive into named arrays, with pickles disabled."""

    target = Path(path).expanduser()
    try:
        if target.suffix.lower() == ".npy":
            return {target.stem: np.asarray(np.load(target, allow_pickle=False))}
        with np.load(target, allow_pickle=False) as archive:
            return {name: np.asarray(archive[name]) for name in archive.files}
    # A truncated npz raises EOFError and a non-archive raises BadZipFile;
    # neither is an OSError, and both turn up in interrupted reductions.
    except (OSError, ValueError, KeyError, EOFError, zipfile.BadZipFile) as exc:
        raise DataReadError(f"Could not read arrays from {target.name}: {exc}") from exc


def read_image(path: str | Path) -> np.ndarray:
    """Read a detector or QC image as a two-dimensional float array."""

    from PIL import Image

    target = Path(path).expanduser()
    try:
        with Image.open(target) as image:
            array = np.asarray(image, dtype=float)
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise DataReadError(f"Could not read {target.name} as an image: {exc}") from exc
    if array.ndim == 3:
        array = array[..., :3].mean(axis=2)
    if array.ndim != 2:
        raise DataReadError(f"{target.name} is not a two-dimensional image.")
    return array


def curve_columns(path: str | Path) -> list[str]:
    """Return the numeric column names available in a one-dimensional file."""

    target = Path(path).expanduser()
    if target.suffix.lower() in ARRAY_SUFFIXES:
        arrays = read_arrays(target)
        return [name for name, value in arrays.items() if np.ndim(value) == 1]
    return list(read_table(target, max_rows=5).columns)


def _pick(names: Sequence[str], preferred: Sequence[str], fallback_index: int) -> str:
    lowered = {str(name).strip().lower(): name for name in names}
    for candidate in preferred:
        if candidate in lowered:
            return lowered[candidate]
    return names[min(fallback_index, len(names) - 1)]


def _curve_from_arrays(target: Path, x_column: str | None, y_column: str | None):
    arrays = read_arrays(target)
    one_d = {name: value for name, value in arrays.items() if np.ndim(value) == 1}
    if len(one_d) < 2:
        raise DataReadError(f"{target.name} does not contain two one-dimensional arrays to plot.")
    names = list(one_d)
    x_name = x_column if x_column in one_d else _pick(names, _Q_NAMES, 0)
    remaining = [name for name in names if name != x_name] or names
    y_name = y_column if y_column in one_d else _pick(remaining, _I_NAMES, 0)
    x_values = np.asarray(one_d[x_name], dtype=float)
    y_values = np.asarray(one_d[y_name], dtype=float)
    if x_values.shape != y_values.shape:
        length = min(x_values.size, y_values.size)
        x_values, y_values = x_values[:length], y_values[:length]
    return x_values, y_values, x_name, y_name, names


def read_curve(
    path: str | Path,
    x_column: str | None = None,
    y_column: str | None = None,
) -> dict:
    """Read one x/y curve from a text table or a NumPy archive.

    When ``x_column``/``y_column`` are omitted, the reduction conventions are
    tried first (``q_ca``/``iq_ca``, ``q``/``I``); otherwise the first two
    numeric columns are used. Non-finite points are removed.

    Returns a dictionary with ``x``, ``y``, ``x_name``, ``y_name``,
    ``columns``, ``path``, and ``label``.
    """

    target = Path(path).expanduser()
    if target.suffix.lower() in ARRAY_SUFFIXES:
        x_values, y_values, x_name, y_name, names = _curve_from_arrays(target, x_column, y_column)
    else:
        table = read_table(target)
        names = list(table.columns)
        if table.shape[1] < 2:
            raise DataReadError(f"{target.name} has only one numeric column.")
        x_name = x_column if x_column in names else _pick(names, _Q_NAMES, 0)
        remaining = [name for name in names if name != x_name] or names
        y_name = y_column if y_column in names else _pick(remaining, _I_NAMES, 0)
        x_values = table[x_name].to_numpy(dtype=float)
        y_values = table[y_name].to_numpy(dtype=float)

    keep = np.isfinite(x_values) & np.isfinite(y_values)
    x_values, y_values = x_values[keep], y_values[keep]
    if not x_values.size:
        raise DataReadError(f"{target.name} has no finite data points.")
    order = np.argsort(x_values, kind="stable")
    return {
        "x": x_values[order],
        "y": y_values[order],
        "x_name": str(x_name),
        "y_name": str(y_name),
        "columns": [str(name) for name in names],
        "path": str(target),
        "label": target.stem,
    }


def common_prefix_suffix(names: Sequence[str]) -> tuple[str, str]:
    """Return the shared leading and trailing text of a list of names.

    Beamline stems share long boilerplate. Trimming it turns a legend of
    identical 90-character names into something readable.
    """

    values = [str(name) for name in names if str(name)]
    if len(values) < 2:
        return "", ""
    prefix = values[0]
    for value in values[1:]:
        while prefix and not value.startswith(prefix):
            prefix = prefix[:-1]
    suffix = values[0]
    for value in values[1:]:
        while suffix and not value.endswith(suffix):
            suffix = suffix[1:]
    # Never trim so far that a name disappears entirely.
    if any(len(prefix) + len(suffix) >= len(value) for value in values):
        return "", ""
    return prefix, suffix


def short_label(name: str, prefix: str = "", suffix: str = "", max_length: int = 48) -> str:
    """Trim shared boilerplate from a legend entry and cap its length."""

    text = str(name)
    if prefix and text.startswith(prefix):
        text = text[len(prefix) :]
    if suffix and text.endswith(suffix):
        text = text[: len(text) - len(suffix)]
    text = text.strip("_- .") or str(name)
    if len(text) <= max_length:
        return text
    left = max_length // 2
    right = max_length - left - 1
    return f"{text[:left]}…{text[-right:]}"


def stack_curves(
    curves: Iterable[dict],
    points: int = 600,
    x_min: float | None = None,
    x_max: float | None = None,
    log_x: bool = False,
) -> tuple[np.ndarray, list[str], np.ndarray]:
    """Interpolate several curves onto one x grid for a waterfall/heat map.

    Returns ``(x_grid, labels, matrix)`` where ``matrix`` has one row per curve.
    Points outside a curve's own range become NaN rather than being
    extrapolated, so a shorter measurement never invents intensity.
    """

    items = [curve for curve in curves if curve is not None and curve["x"].size]
    if not items:
        raise DataReadError("No curves with finite points were provided.")

    lo = x_min if x_min is not None else min(float(np.nanmin(item["x"])) for item in items)
    hi = x_max if x_max is not None else max(float(np.nanmax(item["x"])) for item in items)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        raise DataReadError("The curves do not share a usable x range.")
    if log_x and lo > 0:
        grid = np.logspace(np.log10(lo), np.log10(hi), int(points))
    else:
        grid = np.linspace(lo, hi, int(points))

    rows = np.full((len(items), grid.size), np.nan, dtype=float)
    for index, item in enumerate(items):
        x_values, y_values = item["x"], item["y"]
        inside = (grid >= x_values.min()) & (grid <= x_values.max())
        rows[index, inside] = np.interp(grid[inside], x_values, y_values)
    labels = [str(item.get("label") or Path(item["path"]).stem) for item in items]
    return grid, labels, rows
