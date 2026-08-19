"""Shared engine for the scattering data-visualisation templates.

The GIWAXS/GISAXS explorer and the transmission SAXS/WAXS explorer both browse
a CMS auto-reduction ``analysis/`` folder and render the same building blocks
(2D raw · 2D q-image · q–φ map · circular average, plus line-cuts). This module
holds the geometry-independent pieces so each page is just a thin layout on top:

* frame indexing / filename parsing (``index_frames``, ``stem_of``, ``parse_meta``)
* loaders (``load_raw``, ``load_qimg``, ``load_qphi``, ``load_cir``)
* q-image resolution for the qx–qz vs qr–qz view (``resolve_qimage``)
* array helpers (``apply_mask``, ``log_scale``, ``downsample``, ``band_profile``)
* a heatmap-panel builder (``heatmap_fig``) and 1-D curve styling helpers

Functions that used to reference page-level globals (colormap, log toggle,
panel height) now take them as explicit arguments so both pages can share them.
"""

from __future__ import annotations

import fnmatch
import os
import re
import warnings
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pyscattviz.dataio import DataReadError
from pyscattviz.filters import compile_filter, parse_filename_list

# Max pixels to keep for a heatmap; larger images are stride-decimated.
RAW_MAX_PIXELS = 500_000

# Colour shown for NaN / no-data pixels (heatmap gaps let the plot bg show).
NODATA_BG = "#101010"

# 2D colormaps offered by the templates (all valid Plotly colorscales).
CMAPS = [
    "Turbo",
    "Viridis",
    "Inferno",
    "Magma",
    "Plasma",
    "Cividis",
    "Jet",
    "Hot",
    "Rainbow",
    "Portland",
    "Electric",
    "Blackbody",
    "Thermal",
    "Ice",
    "Spectral",
]

# Reduction products are deliberately described as data, not as a fixed page
# layout.  The explorer can therefore show a new reduction folder (for
# example ``qc``) without making every page assume that every other product is
# present too.
SCATTERING_PRODUCTS = {
    "stitched": {
        "label": "Raw / stitched image",
        "patterns": ("*.tif", "*.tiff", "*.png", "*.jpg", "*.jpeg"),
    },
    "qc": {
        "label": "QC image",
        "patterns": ("*.png", "*.jpg", "*.jpeg", "*.tif", "*.tiff"),
    },
    "q_image": {
        "label": "q-image",
        "patterns": ("*.npz",),
    },
    "qphi": {
        "label": "q–φ map",
        "patterns": ("*.npz",),
    },
    "cir_avg": {
        "label": "Circular average I(q)",
        "patterns": ("*.csv",),
    },
}

SCATTERING_PANEL_ORDER = tuple(SCATTERING_PRODUCTS)

# ---------------------------------------------------------------------------
# Template registry — maps a data-type folder (saxs/waxs/maxs) to the viz
# template best suited to it. A CMS proposal's experiments/<sample>/ folder
# typically holds saxs/, waxs/, and/or maxs/ subfolders; ``maxs`` is grazing-
# incidence (GIWAXS/GISAXS) while ``saxs``/``waxs`` are transmission geometry.
# Pages use this to suggest/route the right template; ``raw_subdir`` tells
# index_frames where the 2D raw image lives relative to analysis/.
# ---------------------------------------------------------------------------
TEMPLATES = {
    "maxs": {
        "label": "GIWAXS / GISAXS Explorer",
        "geometry": "grazing-incidence",
        "raw_subdir": "stitched",  # analysis/stitched/<name>.tiff
        "page": "GIWAXS_Explorer",
    },
    "saxs": {
        "label": "Transmission SAXS Explorer",
        "geometry": "transmission",
        "raw_subdir": "../raw",  # sibling raw/<name>.tiff
        "page": "TSAXS_Explorer",
    },
    "waxs": {
        "label": "Transmission WAXS Explorer",
        "geometry": "transmission",
        "raw_subdir": "../raw",
        "page": "TSAXS_Explorer",
    },
}


def detect_datatype(path: str):
    """Best-effort guess of the data-type key (saxs/waxs/maxs) from a path.

    Looks for a ``saxs``/``waxs``/``maxs`` component anywhere in the path (the
    CMS layout is ``experiments/<sample>/<type>/analysis``). Returns the key or
    None if none is recognised.
    """
    parts = [p.lower() for p in Path(path).parts]
    for key in ("maxs", "waxs", "saxs"):  # maxs first: it's the most specific
        if key in parts:
            return key
    return None


def detect_beamline(path: str):
    """Best-effort guess of the beamline from a path: ``"cms"``, ``"smi"``, or None.

    Detector geometry differs enough between the two that the sensible starting
    q window does too — a CMS GIWAXS q-image reaches about 3 A^-1 where SMI
    reaches 7 — so the explorers use it to pick their defaults.
    """

    for part in (item.lower() for item in Path(path).parts):
        for key in ("cms", "smi"):
            # Match a path component that *is* the beamline, or begins with it
            # ("cms_remote", "smi-proposals"), not an arbitrary substring.
            if part == key or part.startswith((key + "_", key + "-", key + " ")):
                return key
    return None


def data_extent(z, x=None, y=None, min_fraction: float = 0.0):
    """Return the box that actually contains data: ``(x0, x1, y0, y1)``.

    A remeshed q-image is mostly empty — the detector only covers part of the
    qx–qz plane, and everything outside it is NaN. Framing the plot on the axis
    limits therefore shows a small picture surrounded by blank, which is exactly
    what SMI GISAXS looks like at the moment. Framing it on the rows and columns
    that hold finite values instead puts the data on screen.

    ``min_fraction`` ignores rows and columns holding less than that fraction of
    finite pixels, so a few stray hot pixels far from the detector do not drag
    the view back out. Returns None when nothing is finite.
    """

    array = np.asarray(z, dtype=float)
    if array.ndim != 2 or not array.size:
        return None
    finite = np.isfinite(array)
    if not finite.any():
        return None

    columns = finite.mean(axis=0) > min_fraction
    rows = finite.mean(axis=1) > min_fraction
    if not columns.any() or not rows.any():
        columns, rows = finite.any(axis=0), finite.any(axis=1)
        if not columns.any() or not rows.any():
            return None

    x_axis = np.arange(array.shape[1]) if x is None else np.asarray(x, dtype=float)
    y_axis = np.arange(array.shape[0]) if y is None else np.asarray(y, dtype=float)
    if x_axis.size != array.shape[1] or y_axis.size != array.shape[0]:
        return None

    used_x, used_y = x_axis[columns], y_axis[rows]
    return (
        float(np.nanmin(used_x)),
        float(np.nanmax(used_x)),
        float(np.nanmin(used_y)),
        float(np.nanmax(used_y)),
    )


@st.cache_data(show_spinner=False, ttl=30)
def _product_file_count(folder: Path, patterns, limit: int = 100_000):
    """Count direct product files without retaining every path in memory."""

    count = 0
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                try:
                    if entry.is_file() and any(
                        fnmatch.fnmatch(entry.name.lower(), pattern.lower()) for pattern in patterns
                    ):
                        count += 1
                        if count >= limit:
                            return count
                except OSError:
                    continue
    except OSError:
        return 0
    return count


def discover_scattering_products(path: str):
    """Discover reduction products below a user-supplied data path.

    Parameters
    ----------
    path : str
        Either the product root (for example ``.../Results/giwaxs``) or one
        product folder (for example ``.../giwaxs/q_image``).

    Returns
    -------
    tuple
        ``(root, products, focused_product)``. ``root`` is the normalized
        product root. ``products`` is a list of dictionaries containing
        ``key``, ``label``, ``folder``, ``count``, and ``patterns``. When the
        input itself is a recognized product folder, only that product is
        returned and ``focused_product`` contains its key.

    The function is intentionally UI-free so it can also be used by a future
    public/local package and tested without a Streamlit runtime.
    """
    candidate = Path(path).expanduser()
    if candidate.is_file():
        candidate = candidate.parent
    candidate = candidate.resolve(strict=False)
    focused = candidate.name if candidate.name in SCATTERING_PRODUCTS else None
    root = candidate.parent if focused else candidate

    products = []
    for key in SCATTERING_PANEL_ORDER:
        if focused and key != focused:
            continue
        folder = root / key
        if not folder.is_dir():
            continue
        spec = SCATTERING_PRODUCTS[key]
        products.append(
            {
                "key": key,
                "label": spec["label"],
                "folder": str(folder),
                "count": _product_file_count(folder, spec["patterns"]),
                "patterns": spec["patterns"],
            }
        )
    return str(root), products, focused


# Products that start unchecked. The QC image is the reduction's own diagnostic
# picture; it is worth a look when something is wrong, but it is not what anyone
# is reviewing, and rendering it slows every frame change on a mounted folder.
UNCHECKED_BY_DEFAULT = ("qc",)


def scattering_product_selector(key: str, path: str):
    """Render the shared scattering-product chooser in a sidebar.

    The returned product keys are the panels the caller should render. Every
    product starts selected except those in :data:`UNCHECKED_BY_DEFAULT`; users
    can tick or untick any panel before the frame is loaded. A path ending in a
    known product folder focuses the chooser on that product, which makes
    pasting ``.../q_image`` useful for a quick count/inspection.
    """
    root, products, focused = discover_scattering_products(path)
    if not path or not Path(path).expanduser().is_dir():
        return root, products, []

    if focused:
        st.caption(f"Focused product: **{focused}**")
    if not products:
        st.warning("No recognized scattering product folders were found here.")
        return root, products, []

    # A new path should start with all products selected; otherwise Streamlit
    # would reuse the previous root's checkbox state (for example a previously
    # hidden qphi panel) even though the user pasted a different dataset.
    path_state_key = f"{key}_path_last"
    normalized_input = str(Path(path).expanduser().resolve(strict=False))
    if st.session_state.get(path_state_key) != normalized_input:
        for product in products:
            st.session_state.pop(f"{key}_{product['key']}", None)
        st.session_state[path_state_key] = normalized_input

    st.markdown("**Products to display**")
    selected = []
    columns = st.columns(min(3, len(products)))
    for i, product in enumerate(products):
        with columns[i % len(columns)]:
            checked = st.checkbox(
                f"{product['label']} ({product['count']:,})",
                value=product["key"] not in UNCHECKED_BY_DEFAULT,
                key=f"{key}_{product['key']}",
                help=product["folder"],
            )
        if checked:
            selected.append(product["key"])

    return root, products, selected


_TS_RE = re.compile(r"(\d{4})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})")
_TH_RE = re.compile(r"_th(-?\d+\.\d+)_")
_SCAN_RE = re.compile(r"_(\d{6,})_\d{6}_")
_WELL_RE = re.compile(r"_([A-H]\d{1,2})_(?=\d{4}_\d{2}_\d{2})")

# CMS QC layout tags that sit between the ``qc_`` prefix and the frame name.
_QC_LAYOUT_RE = re.compile(r"^(?:\d+panel_)?(?:autoelevate_)?", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Filename ↔ frame indexing
# ---------------------------------------------------------------------------
def stem_of(fname: str) -> str:
    """Shared ``<name>`` stem: strip known prefixes / extensions from a name.

    Handles the mixed conventions used by the auto-reduction, e.g.
    ``stitched/<name>.tiff``, ``q_image/qimg_<name>.tiff.npz`` and
    ``cir_avg/Cir_Avg_<name>.tiff.csv`` all reduce to the same ``<name>``.

    CMS writes several QC layouts for one frame — ``qc_<name>``,
    ``qc_1panel_<name>`` … ``qc_4panel_autoelevate_<name>``. Those layout tags
    are part of the QC filename, not of the frame, so they are stripped too;
    otherwise each variant becomes its own frame with no other product attached.
    """
    s = Path(fname).name
    for pref in ("Cir_Avg_", "qphi_", "qimg_", "qc_"):
        if s.startswith(pref):
            s = s[len(pref) :]
            if pref == "qc_":
                s = _QC_LAYOUT_RE.sub("", s, count=1)
    # Peel trailing extensions repeatedly (e.g. ".tiff.npz" → ".tiff" → "").
    # ``tif`` covers SMI, whose products are named ``<name>.tif.{csv,npz}``.
    while True:
        new = re.sub(r"\.(npz|csv|png|tiff|tif)$", "", s)
        if new == s:
            return s
        s = new


def parse_meta(stem: str) -> dict:
    ts = None
    m = _TS_RE.search(stem)
    if m:
        try:
            ts = datetime(*[int(x) for x in m.groups()])
        except ValueError:
            ts = None
    th = None
    m = _TH_RE.search(stem)
    if m:
        th = float(m.group(1))
    scan = None
    m = _SCAN_RE.search(stem)
    if m:
        scan = int(m.group(1))
    well = None
    m = _WELL_RE.search(stem)
    if m:
        well = m.group(1)
    # Leading "_" happens on SMI (e.g. "_AgBH_x00.00_..."); skip it so the
    # calibration filter still catches those frames.
    is_cal = bool(re.match(r"_*(AgBH|DirBeam|Empty|glassy|GC)", stem, re.I))
    return dict(timestamp=ts, th=th, scan=scan, well=well, is_calibration=is_cal)


def _iter_product_files(folder: Path, patterns):
    """Yield matching direct children while holding at most one entry."""

    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                try:
                    if entry.is_file() and any(
                        fnmatch.fnmatch(entry.name.lower(), pattern.lower()) for pattern in patterns
                    ):
                        yield entry.name, entry.path
                except OSError:
                    continue
    except OSError:
        return


@st.cache_data(show_spinner=False)
def index_frames(
    analysis_dir: str,
    raw_subdir: str = "stitched",
    product_keys=None,
    query: str = "",
    filename_list=(),
    max_frames: int = 5_000,
) -> pd.DataFrame:
    """Lazily index matching reduced frames under a result folder.

    ``raw_subdir`` locates the 2D raw image relative to ``analysis_dir``:

    * ``"stitched"`` (GIWAXS): ``analysis/stitched/<name>.tiff``.
    * ``"../raw"`` (transmission SAXS/WAXS): the sibling ``raw/`` folder, whose
      files carry no reduction prefix.

    ``product_keys`` limits indexing to selected products. ``query`` supports
    boolean AND/OR/NOT expressions and wildcards. ``filename_list`` accepts
    exact product filenames or canonical frame stems. Only names are inspected
    during indexing; array contents remain unopened until a frame is rendered.
    At most ``max_frames`` unique stems are retained.

    DataFrame attributes record ``scanned_entries`` and ``truncated`` so the UI
    can explain a capped result set.
    """
    if max_frames < 1:
        raise ValueError("max_frames must be at least 1")
    max_frames = min(int(max_frames), 50_000)
    predicate = compile_filter(query)
    exact_stems = {stem_of(item) for item in parse_filename_list(filename_list) if item}

    base = Path(analysis_dir)
    raw_dir = (base / raw_subdir).resolve()
    dirs = {
        # SMI writes raw frames as ``.tif``, CMS as ``.tiff`` — accept both.
        "raw": (raw_dir, ("*.tiff", "*.tif")),
        "qc": (base / "qc", ("*.png", "*.jpg", "*.jpeg", "*.tiff", "*.tif")),
        "qimg": (base / "q_image", ("*.npz",)),
        "qphi": (base / "qphi", ("*.npz",)),
        "cir": (base / "cir_avg", ("*.csv",)),
    }
    if product_keys is not None:
        selected = set(product_keys)
        dirs = {
            name: value
            for name, value in dirs.items()
            if name == "raw"
            and "stitched" in selected
            or name == "qc"
            and "qc" in selected
            or name == "qimg"
            and "q_image" in selected
            or name == "qphi"
            and "qphi" in selected
            or name == "cir"
            and "cir_avg" in selected
        }
    maps = {key: {} for key in ("raw", "qc", "qimg", "qphi", "cir")}
    selected_stems: set[str] = set()
    scanned_entries = 0
    truncated = False

    # q-space products are the most useful drivers for a reduced-data review;
    # the remaining passes fill in paths for those same canonical stems.
    scan_order = ("qimg", "qphi", "cir", "qc", "raw")
    for key in scan_order:
        if key not in dirs:
            continue
        folder, patterns = dirs[key]
        for name, path in _iter_product_files(folder, patterns):
            scanned_entries += 1
            stem = stem_of(name)
            already_selected = stem in selected_stems
            exact_match = not exact_stems or stem in exact_stems
            query_match = predicate(name) or predicate(stem)
            can_add = len(selected_stems) < max_frames
            if exact_match and query_match and (already_selected or can_add):
                selected_stems.add(stem)
                existing = maps[key].get(stem)
                # Several CMS QC layouts share one stem. Directory order is
                # arbitrary, so pick deterministically: the shortest filename is
                # the plain ``qc_<name>`` rather than ``qc_4panel_<name>``.
                if existing is None or len(name) < len(Path(existing).name):
                    maps[key][stem] = path
            elif exact_match and query_match and not already_selected:
                truncated = True

            # An explicit list normally contains only a small number of names;
            # stop this directory as soon as all requested stems are resolved.
            if exact_stems and exact_stems.issubset(maps[key]):
                break

    stems = sorted(selected_stems)
    rows = []
    for s in stems:
        meta = parse_meta(s)
        rows.append(
            dict(
                stem=s,
                label=s,
                raw=maps["raw"].get(s),
                qimg=maps["qimg"].get(s),
                qc=maps["qc"].get(s),
                qphi=maps["qphi"].get(s),
                cir=maps["cir"].get(s),
                has_raw=s in maps["raw"],
                has_qimg=s in maps["qimg"],
                has_qc=s in maps["qc"],
                has_qphi=s in maps["qphi"],
                has_cir=s in maps["cir"],
                **meta,
            )
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(
            by=[c for c in ("timestamp", "th", "stem") if c in df], na_position="last"
        ).reset_index(drop=True)
    df.attrs["scanned_entries"] = scanned_entries
    df.attrs["truncated"] = truncated
    df.attrs["max_frames"] = max_frames
    return df


# ---------------------------------------------------------------------------
# Loaders
#
# A real proposal folder always contains a few files that cannot be read: a
# reduction that was interrupted mid-write, a zero-byte CSV, an npz truncated by
# a dropped mount. Every loader below turns that into one catchable
# ``DataReadError`` so a single bad frame reports itself instead of taking the
# whole page down.
# ---------------------------------------------------------------------------
_READ_FAILURES = (
    OSError,  # includes PIL's UnidentifiedImageError and a vanished mount
    ValueError,  # includes pandas EmptyDataError and ParserError
    KeyError,
    IndexError,  # a CSV with fewer columns than the fallback expects
    EOFError,  # a truncated npz
    zipfile.BadZipFile,  # an npz that is not a zip at all
)


def _read_error(path: str, exc: Exception) -> DataReadError:
    return DataReadError(f"{Path(path).name} could not be read: {exc}")


@st.cache_data(show_spinner=False)
def load_raw(fpath: str):
    from PIL import Image

    try:
        with Image.open(fpath) as image:
            return np.asarray(image).astype(float)
    except (*_READ_FAILURES, Image.DecompressionBombError) as exc:
        raise _read_error(fpath, exc) from exc


@st.cache_data(show_spinner=False)
def load_qimg(fpath: str):
    """Return every array in the q_image npz as a plain dict.

    Known keys: ``qimg (nz, nx)``, ``qx (nx,)``, ``qz (nz,)``,
    ``qimg_mask (nz, nx)``. Optional keys enable the qr–qz view:

    * a 2D remesh ``qrimg`` / ``qr_image`` / ``qr_img`` (+ ``qr (nx,)``), or
    * a 1D ``qr (nx,)`` axis reused with ``qimg`` as an alternative x-axis.
    """
    try:
        with np.load(fpath) as archive:
            return {name: archive[name] for name in archive.files}
    except _READ_FAILURES as exc:
        raise _read_error(fpath, exc) from exc


# Candidate npz keys holding a 2D qr–qz remeshed image.
_QR_IMG_KEYS = ("qrimg", "qr_image", "qr_img", "qimg_qr")


def qimage_has_qr(data: dict) -> bool:
    """True if the q_image npz carries a usable qr–qz representation."""
    if data is None:
        return False
    qimg = data.get("qimg")
    for zk in _QR_IMG_KEYS:
        if data.get(zk) is not None and data.get("qr") is not None:
            return True
    qr = data.get("qr")
    return (
        qr is not None
        and qimg is not None
        and np.ndim(qr) == 1
        and qimg.ndim == 2
        and len(qr) == qimg.shape[1]
    )


def resolve_qimage(data: dict, mode: str):
    """Resolve the q-image arrays for ``mode`` ('qx' or 'qr').

    Returns ``(z, x, y, mask, xlabel)``. Falls back to the qx–qz view when the
    qr representation is unavailable, so selecting qr before the npz gains the
    key degrades gracefully.
    """
    qz = data.get("qz")
    mask = data.get("qimg_mask")
    if mode == "qr":
        for zk in _QR_IMG_KEYS:  # dedicated 2D qr image
            z = data.get(zk)
            if z is not None and data.get("qr") is not None:
                m = data.get(zk + "_mask")
                m = (
                    m
                    if m is not None
                    else (mask if getattr(mask, "shape", None) == z.shape else None)
                )
                return z, data.get("qr"), qz, m, "qr (Å⁻¹)"
        qr, qimg = data.get("qr"), data.get("qimg")  # 1D qr axis reusing qimg
        if (
            qr is not None
            and qimg is not None
            and np.ndim(qr) == 1
            and qimg.ndim == 2
            and len(qr) == qimg.shape[1]
        ):
            return qimg, qr, qz, mask, "qr (Å⁻¹)"
    return data.get("qimg"), data.get("qx"), qz, mask, "qx (Å⁻¹)"


@st.cache_data(show_spinner=False)
def load_qphi(fpath: str):
    try:
        with np.load(fpath) as archive:
            return tuple(
                archive[name] if name in archive.files else None
                for name in ("q", "phi", "qphi", "qphi_mask")
            )
    except _READ_FAILURES as exc:
        raise _read_error(fpath, exc) from exc


@st.cache_data(show_spinner=False)
def load_cir(fpath: str):
    try:
        df = pd.read_csv(fpath)
        cols = {c.lower(): c for c in df.columns}
        qcol = cols.get("q_ca") or cols.get("q") or df.columns[-2]
        icol = cols.get("iq_ca") or cols.get("intensity") or df.columns[-1]
        return df[qcol].to_numpy(float), df[icol].to_numpy(float)
    except _READ_FAILURES as exc:
        raise _read_error(fpath, exc) from exc


# ---------------------------------------------------------------------------
# Array helpers
# ---------------------------------------------------------------------------
def apply_mask(z, mask):
    """Return a float copy with no-data entries set to NaN.

    The auto-reduction marks the remeshed support (beamstop, detector gaps,
    off-detector pixels) two ways, and we honour both:

    * A matching boolean mask is interpreted from its overlap with positive
      intensity pixels. Current CMS/SMI q-image files use ``True`` for valid
      remeshed pixels, while some older products use ``True`` for no-data.
      Inferring the orientation prevents a valid q-image from being blanked.
    * Remeshed / caked maps store no-data as literal ``0`` (and any non-finite
      value), so non-positive pixels are blanked as well.

    Blanking (rather than clipping to a floor) lets the panels render gaps as
    dark "no data" and lets line-cut ``nanmean`` ignore them.
    """
    z = np.asarray(z, float).copy()
    if mask is not None and getattr(mask, "shape", None) == z.shape:
        mask = np.asarray(mask, dtype=bool)
        positive = np.isfinite(z) & (z > 0)
        # The convention with more positive pixels is the data-support
        # convention. In the current reduction, qimg_mask is True almost
        # exactly where qimg is positive.
        true_support = np.count_nonzero(mask & positive)
        false_support = np.count_nonzero(~mask & positive)
        if true_support >= false_support:
            z[~mask] = np.nan  # mask True == valid data
        else:
            z[mask] = np.nan  # mask True == no data
    z[~np.isfinite(z)] = np.nan
    z[z <= 0] = np.nan  # 0 == no data in remeshed maps
    return z


def log_scale(z):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.log10(np.clip(z, 1e-6, None))


def downsample(z, x, y, max_pixels=RAW_MAX_PIXELS):
    """Stride-decimate a 2D array (+ optional axes) to <= max_pixels."""
    ny, nx = z.shape
    step = max(1, int(np.ceil(np.sqrt(ny * nx / max_pixels))))
    if step == 1:
        return z, x, y
    z = z[::step, ::step]
    if x is not None:
        x = np.asarray(x)[::step]
    if y is not None:
        y = np.asarray(y)[::step]
    return z, x, y


def parse_centers(text: str):
    out = []
    for tok in re.split(r"[,\s]+", text.strip()):
        if not tok:
            continue
        try:
            out.append(float(tok))
        except ValueError:
            pass
    return out


def band_profile(z, coord_along, coord_band, center, width, mask=None):
    """Average ``z`` over a band ``center ± width/2`` along ``coord_band``.

    ``z`` is 2D with axis-0 varying ``coord0`` and axis-1 varying ``coord1``.
    Here ``coord_band`` selects which axis defines the integration band and
    ``coord_along`` is the axis the resulting 1-D profile runs along.

    Returns ``(x, y)`` where ``x = coord_along`` and ``y`` is the band mean, or
    ``None`` when the band is empty. The band axis is inferred from length.
    """
    zc = apply_mask(z, mask)
    lo, hi = center - width / 2.0, center + width / 2.0
    band = (coord_band >= lo) & (coord_band <= hi)
    if not band.any():
        return None
    with warnings.catch_warnings():  # all-NaN columns → nan, not a scary warning
        warnings.simplefilter("ignore", category=RuntimeWarning)
        if len(coord_band) == zc.shape[0]:  # band runs down the rows → mean over rows
            prof = np.nanmean(zc[band, :], axis=0)
        else:  # band runs across the cols → mean over cols
            prof = np.nanmean(zc[:, band], axis=1)
    return np.asarray(coord_along, float), prof


def axrange(lo, hi, is_log):
    """Optional [min,max] range → Plotly range (log-transformed if needed)."""
    if lo is None and hi is None:
        return None
    if is_log:
        lo = np.log10(lo) if lo and lo > 0 else None
        hi = np.log10(hi) if hi and hi > 0 else None
    return [lo, hi] if lo is not None and hi is not None else None


def color_limits(z, vmin_I, vmax_I, logI):
    """Map optional intensity limits into display (log) space; auto = 1/99.5 pct."""
    finite = z[np.isfinite(z)]
    if vmin_I is None or vmax_I is None:
        if finite.size:
            p_lo, p_hi = np.nanpercentile(finite, [1.0, 99.5])
        else:
            p_lo, p_hi = None, None
        vmin_I = p_lo if vmin_I is None else vmin_I
        vmax_I = p_hi if vmax_I is None else vmax_I
    if vmin_I is None or vmax_I is None:
        return None, None
    if logI:
        lo = float(np.log10(max(vmin_I, 1e-6)))
        hi = float(np.log10(max(vmax_I, 1e-6)))
        return lo, hi
    return float(vmin_I), float(vmax_I)


def heatmap_fig(
    title,
    z,
    x,
    y,
    xlab,
    ylab,
    *,
    cmap="Turbo",
    logI=True,
    height=380,
    xlog=False,
    shapes=None,
    y_reverse=False,
    vmin_I=None,
    vmax_I=None,
    x_range=None,
    y_range=None,
    aspect=None,
):
    """Build a heatmap panel.

    ``aspect`` locks the y-axis to the x-axis in data units: ``"equal"`` → 1:1,
    or a float → y:x ratio; ``None`` leaves it free. ``constrain="domain"``
    keeps the requested x/y ranges when an aspect is set (the Plotly default
    would widen the data range and override the user's limits).
    """
    zz = log_scale(z) if logI else z
    zmin, zmax = color_limits(z, vmin_I, vmax_I, logI)
    fig = go.Figure(
        go.Heatmap(
            z=zz,
            x=x,
            y=y,
            colorscale=cmap,
            zmin=zmin,
            zmax=zmax,
            colorbar=dict(title="log I" if logI else "I"),
            hovertemplate=f"{xlab}=%{{x:.4g}}<br>{ylab}=%{{y:.4g}}<br>I=%{{z:.3g}}<extra></extra>",
        )
    )
    # Plotly wants a log axis's range in log10 units. Passing raw q here drew
    # the q–φ panel at 10^0.001 … 10^0.5, i.e. 1 … 3 A^-1, which is past the end
    # of any SAXS dataset — so the panel came out blank on every log-q geometry
    # (transmission SAXS and GISAXS) while GIWAXS, which is linear in q, looked
    # fine. `axrange` has always done this correctly for the 1-D panels.
    xr = axrange(x_range[0], x_range[1], xlog) if x_range and None not in x_range else None
    fig.update_xaxes(title_text=xlab, type="log" if xlog else "linear", range=xr)
    if y_range and None not in y_range:
        yr = list(y_range)
        if y_reverse:
            yr = yr[::-1]
        fig.update_yaxes(title_text=ylab, range=yr)
    else:
        fig.update_yaxes(title_text=ylab, autorange="reversed" if y_reverse else True)
    if aspect is not None and not xlog:
        ratio = 1.0 if aspect == "equal" else float(aspect)
        fig.update_xaxes(constrain="domain")
        fig.update_yaxes(scaleanchor="x", scaleratio=ratio, constrain="domain")
    if shapes:
        for sh in shapes:
            fig.add_shape(**sh)
    fig.update_layout(
        title=title,
        height=height,
        template="plotly_white",
        plot_bgcolor=NODATA_BG,
        margin=dict(l=55, r=10, t=40, b=45),
    )
    return fig


# ---------------------------------------------------------------------------
# One frame, one product → a figure. Used by the batch exporter, which has to
# rebuild a panel for a frame that is not the one on screen.
# ---------------------------------------------------------------------------
# Panels the batch exporter can rebuild. Line-cut band overlays are deliberately
# left out: they belong to the frame the user is inspecting, not to a contact
# sheet of a hundred frames.
BATCH_PANELS = {
    "stitched": "Raw / stitched image",
    "qc": "QC image",
    "q_image": "q-image",
    "qphi": "q–φ map",
    "cir_avg": "Circular average I(q)",
}


def _product_path(row, key: str):
    """Return a frame's product path, treating both None and NaN as missing."""

    value = row.get(key)
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value)
    return text or None


def _flat_image(path, flip: bool):
    """Load a raw or QC image as a 2D float array with no-data blanked."""

    z = np.asarray(load_raw(path), dtype=float)
    if z.ndim == 3:  # QC PNGs can be RGB/RGBA
        z = z[..., :3].mean(axis=2)
    z = z.copy()
    z[~np.isfinite(z)] = np.nan
    z[z <= 0] = np.nan
    return np.flipud(z) if flip else z


def _span(values):
    """Return the finite (min, max) of an axis, or None when there is none."""

    if values is None:
        return None
    array = np.asarray(values, dtype=float).ravel()
    array = array[np.isfinite(array)]
    if not array.size:
        return None
    return float(array.min()), float(array.max())


def frame_axis_ranges(row, b_mode: str = "qx") -> dict:
    """Measure the axis ranges one frame's own products actually cover.

    Returns any of ``qx``/``qr``, ``qz``, ``qphi_q``, ``phi``, ``cir_q``,
    ``cir_I`` that could be read, each as a ``(min, max)`` pair. For the 2D products this is
    the box that actually holds data rather than the full axis extent, because a
    remeshed image covers only part of the plane and framing it on the axes
    leaves the picture stranded in a field of blank.

    The reduction's q coverage depends on the detector, its distance, and the
    photon energy, so no fixed number is right for long. Measuring the frame is:
    a CMS GISAXS q-image runs qz from about -0.25 to 0.14, an SMI GIWAXS q–φ map
    runs q out to 7 Å⁻¹, and φ runs -179 to +179 rather than 0 to 180. Loaders
    are cached, so this costs nothing beyond what the panels read anyway.
    """

    ranges: dict[str, tuple[float, float]] = {}

    path = _product_path(row, "qimg")
    if path:
        try:
            z, x, y, mask, _label = resolve_qimage(load_qimg(path), b_mode)
        except DataReadError:
            z = x = y = mask = None
        horizontal, vertical = _span(x), _span(y)
        # A remeshed q-image only covers part of the qx–qz plane; the rest is
        # NaN. Prefer the box that actually holds data, or the view is mostly
        # blank — which is what SMI GISAXS looks like on the full axes.
        if z is not None:
            box = data_extent(apply_mask(z, mask), x, y)
            if box:
                horizontal, vertical = (box[0], box[1]), (box[2], box[3])
        if horizontal:
            ranges["qr" if b_mode == "qr" else "qx"] = horizontal
        if vertical:
            ranges["qz"] = vertical

    path = _product_path(row, "qphi")
    if path:
        try:
            q_values, phi_values, caked, mask = load_qphi(path)
        except DataReadError:
            q_values = phi_values = caked = mask = None
        q_span, phi_span = _span(q_values), _span(phi_values)
        if caked is not None:
            usable = mask if getattr(mask, "shape", None) == getattr(caked, "shape", None) else None
            box = data_extent(apply_mask(caked, usable), q_values, phi_values)
            if box:
                q_span, phi_span = (box[0], box[1]), (box[2], box[3])
        if q_span:
            ranges["qphi_q"] = q_span
        if phi_span:
            ranges["phi"] = phi_span

    path = _product_path(row, "cir")
    if path:
        try:
            q_values, intensity = load_cir(path)
        except DataReadError:
            q_values = intensity = None
        if q_values is not None and intensity is not None:
            # Only where there is signal. A CMS SAXS file runs to q = 0.31 but
            # the intensity has fallen from 1600 to 0.01 by q = 0.25, and it
            # starts at 0.0056 rather than the 0.001 a fixed window assumed —
            # so a fixed range wastes most of the panel on empty decades.
            usable = np.isfinite(q_values) & np.isfinite(intensity) & (intensity > 0)
            if usable.any():
                ranges["cir_q"] = (
                    float(np.nanmin(q_values[usable])),
                    float(np.nanmax(q_values[usable])),
                )
                positive = intensity[usable]
                low, high = np.nanpercentile(positive, [0.5, 99.9])
                if np.isfinite(low) and np.isfinite(high) and high > low > 0:
                    ranges["cir_I"] = (float(low), float(high))
        elif _span(q_values):
            ranges["cir_q"] = _span(q_values)

    return ranges


def frame_panel_figure(
    row,
    panel: str,
    *,
    cmap: str = "Turbo",
    logI: bool = True,
    height: int = 380,
    b_mode: str = "qx",
    aspect=None,
    flip_raw: bool = True,
    logq: bool = False,
    logiq: bool = True,
    x_range=None,
    y_range=None,
    vmin_I=None,
    vmax_I=None,
    title: str | None = None,
):
    """Rebuild one product panel for one indexed frame.

    ``row`` is a row of the :func:`index_frames` table. Returns
    ``(figure, table, arrays)`` — ``table`` and ``arrays`` are ``None`` where
    they do not apply — or ``None`` when this frame has no such product.

    The interactive explorers keep their own panel code because they also draw
    line-cut bands and per-curve styling. This function exists so a batch export
    can produce the same picture for a frame that is not on screen.
    """

    if panel not in BATCH_PANELS:
        raise ValueError(f"unknown panel: {panel}")

    heat = dict(
        cmap=cmap,
        logI=logI,
        height=height,
        aspect=aspect,
        x_range=x_range,
        y_range=y_range,
        vmin_I=vmin_I,
        vmax_I=vmax_I,
    )

    if panel in {"stitched", "qc"}:
        path = _product_path(row, "raw" if panel == "stitched" else "qc")
        if path is None:
            return None
        z = _flat_image(path, flip=flip_raw and panel == "stitched")
        z, px_x, px_y = downsample(z, np.arange(z.shape[1]), np.arange(z.shape[0]))
        figure = heatmap_fig(
            title or BATCH_PANELS[panel], z, px_x, px_y, "x (px)", "y (px)", **heat
        )
        return figure, None, {"image": z}

    if panel == "q_image":
        path = _product_path(row, "qimg")
        if path is None:
            return None
        data = load_qimg(path)
        qimg, qx, qz, mask, xlabel = resolve_qimage(data, b_mode)
        if qimg is None:
            return None
        z = apply_mask(qimg, mask)
        z, xx, yy = downsample(z, qx, qz)
        figure = heatmap_fig(title or BATCH_PANELS[panel], z, xx, yy, xlabel, "qz (Å⁻¹)", **heat)
        arrays = {"qimg": z, b_mode: np.asarray(xx), "qz": np.asarray(yy)}
        return figure, None, arrays

    if panel == "qphi":
        path = _product_path(row, "qphi")
        if path is None:
            return None
        q, phi, qphi, mask = load_qphi(path)
        if qphi is None:
            return None
        mask = mask if getattr(mask, "shape", None) == getattr(qphi, "shape", None) else None
        z = apply_mask(qphi, mask)
        figure = heatmap_fig(
            title or BATCH_PANELS[panel],
            z,
            q,
            phi,
            "q (Å⁻¹)",
            "φ (deg)",
            xlog=logq,
            **heat,
        )
        return figure, None, {"qphi": z, "q": np.asarray(q), "phi": np.asarray(phi)}

    path = _product_path(row, "cir")
    if path is None:
        return None
    q_values, intensity = load_cir(path)
    figure = go.Figure(
        go.Scatter(
            x=q_values,
            y=intensity,
            name="I(q)",
            mode="lines",
            line=dict(width=2.0, color="crimson"),
            hovertemplate="q=%{x:.4f}<br>I=%{y:.3g}<extra></extra>",
        )
    )
    figure.update_xaxes(title_text="q (Å⁻¹)", range=axrange(*(x_range or (None, None)), logq))
    figure.update_yaxes(title_text="I(q)", range=axrange(*(y_range or (None, None)), logiq))
    style_1d_axes(figure, logq, logiq)
    figure.update_layout(
        title=title or BATCH_PANELS[panel],
        height=height,
        template="plotly_white",
        margin=dict(l=60, r=15, t=40, b=45),
    )
    return figure, pd.DataFrame({"q": q_values, "I": intensity}), None


# ---------------------------------------------------------------------------
# 1-D curve styling (CSV-plotter parity for the circular-average + line-cuts)
# ---------------------------------------------------------------------------
LINE_COLORS = {
    "Auto": None,
    "Blue": "#1f77b4",
    "Orange": "#ff7f0e",
    "Green": "#2ca02c",
    "Red": "#d62728",
    "Purple": "#9467bd",
    "Brown": "#8c564b",
    "Pink": "#e377c2",
    "Gray": "#7f7f7f",
    "Olive": "#bcbd22",
    "Cyan": "#17becf",
    "Black": "#000000",
    "Crimson": "crimson",
}
LINE_MARKERS = {
    "None": None,
    "Circle": "circle",
    "Square": "square",
    "Diamond": "diamond",
    "Triangle": "triangle-up",
    "Cross": "cross",
    "X": "x",
    "Star": "star",
}
LINE_DASHES = {
    "Solid": "solid",
    "Dash": "dash",
    "Dot": "dot",
    "DashDot": "dashdot",
}
# Faint gridline colour (low opacity) for 1-D plots.
GRID_RGBA = "rgba(128,128,128,0.25)"


def curve_style_controls(key, defaults=None):
    """Render CSV-plotter-style per-curve styling widgets; return a style dict.

    Compact single-row layout so it fits above a 1-D plot.
    """
    d = {
        "color": "Auto",
        "marker": "None",
        "dash": "Solid",
        "width": 2.0,
        "size": 6.0,
        "opacity": 1.0,
    }
    if defaults:
        d.update(defaults)
    s1, s2, s3, s4, s5, s6 = st.columns(6)
    color = s1.selectbox(
        "Color", list(LINE_COLORS), key=f"{key}_col", index=list(LINE_COLORS).index(d["color"])
    )
    marker = s2.selectbox(
        "Marker", list(LINE_MARKERS), key=f"{key}_mk", index=list(LINE_MARKERS).index(d["marker"])
    )
    dash = s3.selectbox(
        "Line", list(LINE_DASHES), key=f"{key}_ls", index=list(LINE_DASHES).index(d["dash"])
    )
    width = s4.slider("Width", 0.5, 8.0, d["width"], 0.5, key=f"{key}_w")
    size = s5.slider("Marker size", 2.0, 20.0, d["size"], 1.0, key=f"{key}_sz")
    opacity = s6.slider("Opacity", 0.1, 1.0, d["opacity"], 0.05, key=f"{key}_op")
    return dict(color=color, marker=marker, dash=dash, width=width, size=size, opacity=opacity)


def apply_curve_style(trace_kwargs, style, base_color=None):
    """Fold a style dict into go.Scatter kwargs (mode/line/marker/opacity)."""
    color = LINE_COLORS.get(style["color"]) or base_color
    marker_sym = LINE_MARKERS.get(style["marker"])
    mode = "lines+markers" if marker_sym else "lines"
    trace_kwargs["mode"] = mode
    trace_kwargs["opacity"] = style["opacity"]
    line = dict(width=style["width"], dash=LINE_DASHES.get(style["dash"], "solid"))
    if color:
        line["color"] = color
    trace_kwargs["line"] = line
    if marker_sym:
        mk = dict(symbol=marker_sym, size=style["size"])
        if color:
            mk["color"] = color
        trace_kwargs["marker"] = mk
    return trace_kwargs


def style_1d_axes(fig, xlog, ylog, grid=True):
    """Apply log/linear + faint grid to a 1-D figure's axes."""
    common = dict(showgrid=grid, gridcolor=GRID_RGBA, gridwidth=1, zeroline=False)
    fig.update_xaxes(type="log" if xlog else "linear", **common)
    fig.update_yaxes(type="log" if ylog else "linear", **common)
