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
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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


def scattering_product_selector(key: str, path: str):
    """Render the shared scattering-product chooser in a sidebar.

    The returned product keys are the panels the caller should render. All
    discovered products start selected; users can uncheck any panel before
    the frame is loaded. A path ending in a known product folder focuses the
    chooser on that product, which makes pasting ``.../q_image`` useful for a
    quick count/inspection.
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
                value=True,
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


# ---------------------------------------------------------------------------
# Filename ↔ frame indexing
# ---------------------------------------------------------------------------
def stem_of(fname: str) -> str:
    """Shared ``<name>`` stem: strip known prefixes / extensions from a name.

    Handles the mixed conventions used by the auto-reduction, e.g.
    ``stitched/<name>.tiff``, ``q_image/qimg_<name>.tiff.npz`` and
    ``cir_avg/Cir_Avg_<name>.tiff.csv`` all reduce to the same ``<name>``.
    """
    s = Path(fname).name
    for pref in ("Cir_Avg_", "qphi_", "qimg_", "qc_"):
        if s.startswith(pref):
            s = s[len(pref) :]
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


def index_remote_frames(
    product_entries,
    query: str = "",
    filename_list=(),
    max_frames: int = 5_000,
) -> pd.DataFrame:
    """Index remote Globus filenames without opening or downloading arrays.

    ``product_entries`` maps public product keys such as ``q_image`` to the
    dictionaries returned by :func:`pyscattviz.globus_cli.list_globus_directory`.
    The returned table uses the same columns as :func:`index_frames`, but its
    file-path cells contain remote collection paths.
    """

    if max_frames < 1:
        raise ValueError("max_frames must be at least 1")
    max_frames = min(int(max_frames), 50_000)
    predicate = compile_filter(query)
    exact_stems = {stem_of(item) for item in parse_filename_list(filename_list) if item}
    column_for_product = {
        "stitched": "raw",
        "qc": "qc",
        "q_image": "qimg",
        "qphi": "qphi",
        "cir_avg": "cir",
    }
    maps = {key: {} for key in ("raw", "qc", "qimg", "qphi", "cir")}
    selected_stems: set[str] = set()
    scanned_entries = 0
    truncated = False

    for product_key in ("q_image", "qphi", "cir_avg", "qc", "stitched"):
        column = column_for_product[product_key]
        patterns = SCATTERING_PRODUCTS[product_key]["patterns"]
        for entry in product_entries.get(product_key, ()):
            if entry.get("is_dir"):
                continue
            name = str(entry.get("name") or "")
            if not name or not any(
                fnmatch.fnmatch(name.lower(), pattern.lower()) for pattern in patterns
            ):
                continue
            scanned_entries += 1
            stem = stem_of(name)
            already_selected = stem in selected_stems
            exact_match = not exact_stems or stem in exact_stems
            query_match = predicate(name) or predicate(stem)
            can_add = len(selected_stems) < max_frames
            if exact_match and query_match and (already_selected or can_add):
                selected_stems.add(stem)
                maps[column][stem] = str(entry["path"])
            elif exact_match and query_match and not already_selected:
                truncated = True

    rows = []
    for stem in sorted(selected_stems):
        meta = parse_meta(stem)
        rows.append(
            dict(
                stem=stem,
                label=stem,
                raw=maps["raw"].get(stem),
                qimg=maps["qimg"].get(stem),
                qc=maps["qc"].get(stem),
                qphi=maps["qphi"].get(stem),
                cir=maps["cir"].get(stem),
                has_raw=stem in maps["raw"],
                has_qimg=stem in maps["qimg"],
                has_qc=stem in maps["qc"],
                has_qphi=stem in maps["qphi"],
                has_cir=stem in maps["cir"],
                **meta,
            )
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(
            by=[column for column in ("timestamp", "th", "stem") if column in df],
            na_position="last",
        ).reset_index(drop=True)
    df.attrs["scanned_entries"] = scanned_entries
    df.attrs["truncated"] = truncated
    df.attrs["max_frames"] = max_frames
    df.attrs["remote"] = True
    return df


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_raw(fpath: str):
    from PIL import Image

    return np.asarray(Image.open(fpath)).astype(float)


@st.cache_data(show_spinner=False)
def load_qimg(fpath: str):
    """Return every array in the q_image npz as a plain dict.

    Known keys: ``qimg (nz, nx)``, ``qx (nx,)``, ``qz (nz,)``,
    ``qimg_mask (nz, nx)``. Optional keys enable the qr–qz view:

    * a 2D remesh ``qrimg`` / ``qr_image`` / ``qr_img`` (+ ``qr (nx,)``), or
    * a 1D ``qr (nx,)`` axis reused with ``qimg`` as an alternative x-axis.
    """
    d = np.load(fpath)
    return {k: d[k] for k in d.files}


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
    d = np.load(fpath)
    return (d.get("q"), d.get("phi"), d.get("qphi"), d.get("qphi_mask"))


@st.cache_data(show_spinner=False)
def load_cir(fpath: str):
    df = pd.read_csv(fpath)
    cols = {c.lower(): c for c in df.columns}
    qcol = cols.get("q_ca") or cols.get("q") or df.columns[-2]
    icol = cols.get("iq_ca") or cols.get("intensity") or df.columns[-1]
    return df[qcol].to_numpy(float), df[icol].to_numpy(float)


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
    xr = list(x_range) if x_range and None not in x_range else None
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
