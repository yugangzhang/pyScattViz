"""Organise a CMS experiment's reduced frames for looking at them.

What a beamline experiment folder holds, read from the names alone — no
image is opened::

    idx = index_experiment(root)          # one row per reduced frame, every product's path
    samples = sample_table(idx)           # one row per (folder, sample)
    progress = progress_table(root)       # raw vs reduced, per folder and detector
    q, I = stack_iq(curves)               # I(q) of several frames on one q axis
    org = build_organizer(idx, store)     # a pyDataOrg Organizer with the products linked

The experiment is ``experiments/<user>/`` of a CMS proposal (NSLS-II 11-BM): one folder per
kind of measurement (``1_Static``, ``2_Humidity``, ``3_spincoating``), a
detector folder in each (``saxs``, ``waxs``, ``waxs_temp``, ``maxs``) with
``raw/`` and the reduction's ``analysis/{cir_avg,q_image,qphi,qc}``. A
product is named after its frame: ``Cir_Avg_<frame>.csv``,
``qimg_<frame>.npz``, ``qphi_<frame>.npz``, ``qc_<frame>.png``.

A frame is *static* (a sample measured at spots and angles, perhaps more
than once) or *in-situ* (one run of many frames in time)::

    film_A3_pos2_x+0.001_th+0.080_10.00s_stitched_1000784_000000_waxs_temp.tiff
    \\ sample/    spot    angle  exposure        scan   frame
    film_B_humid_RH50_228_4623.0s_x+0.000_th+0.100_1.00s_RH68.497_T69.982C_1000539_000000_maxs.tiff
    \\___ series ___/ idx elapsed                          RH (%)  T (°C)
    spin_C_1786.0s_x28.800_th0.500_0.29s_1000176_000123_maxs.tiff
    \\series/ start                             scan   frame = the clock of one spin

A sensor that is not connected reads ``T-273.150C`` or an RH outside 0–100
(``RH661.095``); those come back as None, not as a reading.

pyScattViz's Org pages show these; a notebook can call the same functions.
Nothing here needs Streamlit; pyDataOrg only for :func:`build_organizer`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# In-situ names (the stage readings, the elapsed time, the series)
# ---------------------------------------------------------------------------

_ELAPSED_RE = re.compile(r"_(\d+(?:\.\d+)?)s_(?:Linkam|linkam|[A-Za-z])")
# Fall back to the first `<float>s_` group that is NOT the exposure time at
# the tail. We try the Linkam-anchored form first (above), then a generic one.
_ELAPSED_FALLBACK_RE = re.compile(r"_(\d+(?:\.\d+)?)s_")
_LINKAM_RE = re.compile(r"_Linkam(-?\d+(?:\.\d+)?)C", re.IGNORECASE)
_STAGE_T_RE = re.compile(r"_T(-?\d+(?:\.\d+)?)C(?=_)")
_RH_RE = re.compile(r"_RH(-?\d+(?:\.\d+)?)(?=_)")
_INSITU_TH_RE = re.compile(r"_th([+-]?\d+(?:\.\d+)?)")
_UID_RE = re.compile(r"_(\d+)_(\d+)_(?:saxs|waxs|maxs)\w*\.tiff?$", re.IGNORECASE)
# `<series>_<frame idx>_<elapsed>s_` -- what one in-situ run shares.
_SERIES_RE = re.compile(r"^(.*?)_(\d+)_\d+(?:\.\d+)?s_(?=[A-Za-z])")


@dataclass(frozen=True)
class InsituMeta:
    """Parsed in-situ metadata for one frame."""

    filename: str
    elapsed_s: Optional[float]
    temperature_C: Optional[float]
    incident_angle: Optional[float]
    uid: Optional[int]
    humidity_RH: Optional[float] = None
    frame: Optional[int] = None  # frame counter within a scan
    exposure_s: Optional[float] = None
    index: Optional[int] = None  # `<series>_<index>_<elapsed>s_`


def parse_insitu_meta(filename: str) -> InsituMeta:
    """Parse elapsed-time / temperature / humidity / incident-angle / uid.

    Any field that isn't present comes back as None — robust to spin-coating
    files that have an elapsed-time but no Linkam temperature. Temperature is
    the Linkam's when there is one, else the `_T<value>C` stage reading.
    """
    m_th = _INSITU_TH_RE.search(filename)
    incident = float(m_th.group(1)) if m_th else None
    # Stage readings follow the angle and exposure; looking only there keeps
    # a sample called `..._humidAir_RH50_...` from reading as 50 % RH.
    tail = filename[m_th.end() :] if m_th else filename

    m_lin = _LINKAM_RE.search(filename) or _STAGE_T_RE.search(tail)
    temperature = float(m_lin.group(1)) if m_lin else None
    if temperature is not None and temperature <= -273.0:
        temperature = None  # no sensor
    m_rh = _RH_RE.search(tail)
    humidity = float(m_rh.group(1)) if m_rh else None
    if humidity is not None and not (0.0 <= humidity <= 100.0):
        humidity = None  # no sensor

    elapsed: Optional[float] = None
    m_el = _ELAPSED_RE.search(filename)
    if m_el:
        elapsed = float(m_el.group(1))
    else:
        # Generic fallback: the first `<float>s_` that isn't the trailing
        # exposure time. The exposure sits right before the uid tail.
        hits = list(_ELAPSED_FALLBACK_RE.finditer(filename))
        if len(hits) >= 2:
            elapsed = float(hits[0].group(1))  # first = elapsed, last = exposure

    m_uid = _UID_RE.search(filename)
    uid = int(m_uid.group(1)) if m_uid else None
    frame = int(m_uid.group(2)) if m_uid else None
    # The exposure is the last `<float>s_` (stage readings may follow it).
    hits = _ELAPSED_FALLBACK_RE.findall(filename)
    exposure = float(hits[-1]) if hits else None
    m_ser = _SERIES_RE.search(filename)
    index = int(m_ser.group(2)) if m_ser else None
    return InsituMeta(
        filename=filename,
        elapsed_s=elapsed,
        temperature_C=temperature,
        incident_angle=incident,
        uid=uid,
        humidity_RH=humidity,
        frame=frame,
        exposure_s=exposure,
        index=index,
    )


def insitu_series(filename: str) -> str:
    """The name one in-situ run shares: everything before `_<idx>_<t>s_`.

    `film_B_humid_RH50_228_4623.0s_x+0.000_...` → `film_B_humid_RH50`.
    A name without a frame index / elapsed time is its own series (the part
    before `_x`, or the whole name).
    """
    m = _SERIES_RE.search(filename)
    if m:
        return m.group(1)
    # Spin-coating scans: `<sample>_<elapsed>s_x...`, one scan of many frames.
    return re.sub(r"_\d+(?:\.\d+)?s$", "", filename.split("_x", 1)[0])


# key: (folder under analysis/, filename prefix, suffix)
PRODUCTS: Dict[str, Tuple[str, str, str]] = {
    "cir": ("cir_avg", "Cir_Avg_", ".csv"),
    "qimg": ("q_image", "qimg_", ".npz"),
    "qphi": ("qphi", "qphi_", ".npz"),
    "qc": ("qc", "qc_", ".png"),
}
# Detector folders whose raw frames are stitched before reduction: the
# reduced frames are the stitched ones, in analysis/stitched/.
STITCHED_DIR = "stitched"

_TIFF_RE = re.compile(r"\.tiff?$", re.IGNORECASE)
_DET_RE = re.compile(r"_\d+_\d+_((?:saxs|waxs|maxs)\w*)\.tiff?$", re.IGNORECASE)
_X_RE = re.compile(r"_x([+-]?\d+(?:\.\d+)?)(?=_)")
_TH_RE = re.compile(r"_th([+-]?\d+(?:\.\d+)?)(?=_)")
_POS_RE = re.compile(r"_pos(\d+)$")
# `<series>_<index>_<elapsed>s_x` (humidity, Linkam) or `<series>_<start>s_x`
# (one spin: every frame carries the scan's start time).
_INDEXED_RE = re.compile(r"^(.*?)_(\d+)_(\d+(?:\.\d+)?)s_x")
_STARTED_RE = re.compile(r"^(.*?)_(\d+(?:\.\d+)?)s_x")

_NUMERIC = ("pos", "x", "th", "exposure_s", "scan", "frame", "index", "elapsed_s", "T_C", "RH")
FRAME_COLUMNS = (
    "folder",
    "det_folder",
    "det",
    "stem",
    "sample",
    "kind",
    "pos",
    "x",
    "th",
    "exposure_s",
    "scan",
    "frame",
    "index",
    "elapsed_s",
    "T_C",
    "RH",
    "stitched",
    "raw",
    "cir",
    "qimg",
    "qphi",
    "qc",
)


# ---------------------------------------------------------------------------
# One frame
# ---------------------------------------------------------------------------


def _float(match) -> Optional[float]:
    return float(match.group(1)) if match else None


def parse_frame(name: str) -> dict:
    """What a CMS frame name says: sample, spot, angle, scan — and, for an
    in-situ frame, its series, index, elapsed time, temperature and humidity.

    ``kind`` is ``"insitu"`` when the name carries an elapsed time before
    ``_x`` (``<series>_<idx>_<t>s_x`` or ``<series>_<t>s_x``), else
    ``"static"``. ``sample`` is the series for an in-situ frame and the name
    before ``_x`` without its ``_pos<n>`` for a static one. Fields a name
    does not carry are None; a sensor that was not connected reads None.
    """
    base = os.path.basename(str(name))
    stem = _TIFF_RE.sub("", base)
    meta = parse_insitu_meta(base)
    m_det = _DET_RE.search(base)
    head = stem.split("_x", 1)[0] if _X_RE.search(stem) else stem

    indexed, started = _INDEXED_RE.match(stem), _STARTED_RE.match(stem)
    kind = "insitu" if (indexed or started) else "static"
    pos = None
    if kind == "insitu":
        sample = insitu_series(base)
    else:
        m_pos = _POS_RE.search(head)
        pos = int(m_pos.group(1)) if m_pos else None
        sample = _POS_RE.sub("", head)
    return dict(
        stem=base,
        sample=sample,
        kind=kind,
        pos=pos,
        x=_float(_X_RE.search(stem)),
        th=_float(_TH_RE.search(stem)),
        exposure_s=meta.exposure_s,
        scan=meta.uid,
        frame=meta.frame,
        index=int(indexed.group(2)) if indexed else None,
        elapsed_s=meta.elapsed_s if kind == "insitu" else None,
        T_C=meta.temperature_C if kind == "insitu" else None,
        RH=meta.humidity_RH if kind == "insitu" else None,
        stitched="_stitched_" in base,
        det_token=m_det.group(1).lower() if m_det else None,
    )


def product_stem(filename: str, product: str) -> Optional[str]:
    """The frame a product file belongs to (``qimg_<frame>.npz`` → ``<frame>``),
    or None when *filename* is not that product."""
    _, prefix, suffix = PRODUCTS[product]
    if filename.startswith(prefix) and filename.endswith(suffix):
        return filename[len(prefix) : -len(suffix)]
    return None


# ---------------------------------------------------------------------------
# One experiment
# ---------------------------------------------------------------------------


def _names(folder: Path) -> List[str]:
    try:
        with os.scandir(folder) as entries:
            return [e.name for e in entries if not e.name.startswith(".")]
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return []


def detector_folders(folder) -> List[Path]:
    """The detector folders of one experiment folder: those holding
    ``raw/`` or ``analysis/`` (``saxs``, ``waxs_temp``, ``maxs`` …)."""
    folder = Path(folder)
    found = []
    for name in sorted(_names(folder)):
        path = folder / name
        if (path / "raw").is_dir() or (path / "analysis").is_dir():
            found.append(path)
    return found


def experiment_folders(root) -> List[Path]:
    """The folders of an experiment that hold detector folders, in order
    (``1_Static``, ``2_Humidity`` …)."""
    root = Path(root)
    return [
        root / name
        for name in sorted(_names(root))
        if (root / name).is_dir() and detector_folders(root / name)
    ]


def _detector(det_folder: str) -> str:
    """``waxs_temp`` → ``waxs``: the technique a detector folder records."""
    return det_folder.split("_", 1)[0].lower()


def index_folder(det_path) -> pd.DataFrame:
    """One row per reduced frame of one detector folder, with the path of
    each product it has (None for one not written yet)."""
    det_path = Path(det_path)
    analysis = det_path / "analysis"
    paths: Dict[str, Dict[str, str]] = {}
    for product, (sub, _, _) in PRODUCTS.items():
        for name in _names(analysis / sub):
            stem = product_stem(name, product)
            if stem is not None:
                paths.setdefault(stem, {})[product] = str(analysis / sub / name)
    raw_dirs = [analysis / STITCHED_DIR, det_path / "raw"]
    raws = {}
    for raw_dir in raw_dirs:
        for name in _names(raw_dir):
            if _TIFF_RE.search(name):
                raws.setdefault(name, str(raw_dir / name))
    rows = []
    for stem, products in paths.items():
        row = parse_frame(stem)
        row.update({k: products.get(k) for k in PRODUCTS})
        row["raw"] = raws.get(stem)
        rows.append(row)
    frame = pd.DataFrame(
        rows, columns=[c for c in FRAME_COLUMNS if c not in ("folder", "det_folder", "det")]
    )
    frame = frame.astype({c: float for c in _NUMERIC})
    frame.insert(0, "det", _detector(det_path.name))
    frame.insert(0, "det_folder", det_path.name)
    frame.insert(0, "folder", det_path.parent.name)
    return frame


def sort_frames(frames: pd.DataFrame) -> pd.DataFrame:
    """Static frames by sample, spot, angle, scan; in-situ frames by series,
    angle, then time (index, elapsed, frame counter)."""
    if frames.empty:
        return frames
    order = [
        "folder",
        "det_folder",
        "sample",
        "th",
        "pos",
        "x",
        "index",
        "elapsed_s",
        "scan",
        "frame",
        "stem",
    ]
    return frames.sort_values(order, na_position="last", kind="stable").reset_index(drop=True)


def index_experiment(root, *, folders: Optional[Sequence[str]] = None) -> pd.DataFrame:
    """Every reduced frame of an experiment: :data:`FRAME_COLUMNS`.

    *folders* limits it to some experiment folders (``["2_Humidity"]``).
    """
    root = Path(root)
    parts = []
    for folder in experiment_folders(root):
        if folders and folder.name not in folders:
            continue
        for det_path in detector_folders(folder):
            part = index_folder(det_path)
            if not part.empty:
                parts.append(part)
    if not parts:
        return pd.DataFrame(columns=list(FRAME_COLUMNS))
    return sort_frames(pd.concat(parts, ignore_index=True))


def progress_table(root) -> pd.DataFrame:
    """Per experiment folder and detector: raw frames, stitched frames,
    each reduced product, and when each folder last changed.

    ``to_reduce`` is what the reduction has not reached yet: stitched frames
    without an I(q) where frames are stitched, else raw frames without one.
    Counted from directory listings; nothing is opened.
    """
    rows = []
    for folder in experiment_folders(root):
        for det_path in detector_folders(folder):
            analysis = det_path / "analysis"
            raw = [n for n in _names(det_path / "raw") if _TIFF_RE.search(n)]
            stitched = [n for n in _names(analysis / STITCHED_DIR) if _TIFF_RE.search(n)]
            row = dict(
                folder=folder.name, det_folder=det_path.name, raw=len(raw), stitched=len(stitched)
            )
            stems = {}
            for product, (sub, _, _) in PRODUCTS.items():
                stems[product] = {
                    s for s in (product_stem(n, product) for n in _names(analysis / sub)) if s
                }
                row[product] = len(stems[product])
            source = set(stitched) if stitched else set(raw)
            row["to_reduce"] = len(source - stems["cir"])
            row["raw_changed"] = _mtime(det_path / "raw")
            row["reduced_changed"] = _mtime(analysis / PRODUCTS["cir"][0])
            rows.append(row)
    columns = [
        "folder",
        "det_folder",
        "raw",
        "stitched",
        *PRODUCTS,
        "to_reduce",
        "raw_changed",
        "reduced_changed",
    ]
    return pd.DataFrame(rows, columns=columns)


def _mtime(path: Path) -> Optional[pd.Timestamp]:
    try:
        return pd.Timestamp.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Samples, spots, runs
# ---------------------------------------------------------------------------


def span(values) -> Optional[str]:
    v = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    if v.empty:
        return None
    lo, hi = v.min(), v.max()
    return f"{lo:.4g}" if np.isclose(lo, hi) else f"{lo:.4g}–{hi:.4g}"


def _angles(values) -> str:
    v = sorted(set(pd.to_numeric(pd.Series(values), errors="coerce").dropna()))
    return ", ".join(f"{a:g}" for a in v)


def _span_of(lo, hi) -> Optional[str]:
    if lo is None or hi is None or pd.isna(lo) or pd.isna(hi):
        return None
    return f"{lo:.4g}" if np.isclose(lo, hi) else f"{lo:.4g}–{hi:.4g}"


def sample_table(frames: pd.DataFrame) -> pd.DataFrame:
    """One row per (folder, sample): what kind, which detectors, how many
    frames, at which angles and spots, and — in situ — over what time,
    humidity and temperature."""
    columns = [
        "folder",
        "sample",
        "kind",
        "dets",
        "frames",
        "angles",
        "spots",
        "repeats",
        "exposure_s",
        "time_s",
        "RH",
        "T_C",
        "last_scan",
    ]
    if frames.empty:
        return pd.DataFrame(columns=columns)
    keys = ["folder", "sample"]
    f = frames.copy()
    # The clock of a run (run_time): elapsed plus the frame's place in its
    # scan when the elapsed time moves, else the frame counter.
    within = (f["frame"] * f["exposure_s"]).fillna(0.0)
    groups = f.groupby(keys, sort=False)
    out = groups.agg(
        kind=("kind", "first"),
        frames=("stem", "size"),
        last_scan=("scan", "max"),
        e_lo=("elapsed_s", "min"),
        e_hi=("elapsed_s", "max"),
        x_lo=("exposure_s", "min"),
        x_hi=("exposure_s", "max"),
        rh_lo=("RH", "min"),
        rh_hi=("RH", "max"),
        t_lo=("T_C", "min"),
        t_hi=("T_C", "max"),
        f_lo=("frame", "min"),
        f_hi=("frame", "max"),
    )
    f["_clock"] = f["elapsed_s"] + within
    clock = f.groupby(keys, sort=False)["_clock"].agg(["min", "max"])
    out["dets"] = groups["det_folder"].agg(lambda v: ", ".join(sorted(set(v))))
    out["angles"] = groups["th"].agg(_angles)
    out["spots"] = f.drop_duplicates(keys + ["pos", "x"]).groupby(keys, sort=False).size()
    out["repeats"] = (
        f.groupby(keys + ["det", "th", "pos", "x"], dropna=False, sort=False)
        .size()
        .groupby(level=[0, 1], sort=False)
        .max()
    )
    moving = out["e_hi"] > out["e_lo"]
    time_lo = np.where(moving, clock["min"] - out["e_lo"], out["f_lo"])
    time_hi = np.where(moving, clock["max"] - out["e_lo"], out["f_hi"])
    static = out["kind"] == "static"
    out["exposure_s"] = [_span_of(a, b) for a, b in zip(out["x_lo"], out["x_hi"])]
    out["time_s"] = [None if st else _span_of(a, b) for st, a, b in zip(static, time_lo, time_hi)]
    out["RH"] = [_span_of(a, b) for a, b in zip(out["rh_lo"], out["rh_hi"])]
    out["T_C"] = [_span_of(a, b) for a, b in zip(out["t_lo"], out["t_hi"])]
    out.loc[~static, ["spots", "repeats"]] = None
    return out.reset_index()[columns]


def frames_of(
    frames: pd.DataFrame,
    folder: str,
    sample: str,
    *,
    det_folder: Optional[str] = None,
    th: Optional[float] = None,
) -> pd.DataFrame:
    """The frames of one sample in one folder (one detector, one angle)."""
    keep = (frames["folder"] == folder) & (frames["sample"] == sample)
    if det_folder is not None:
        keep &= frames["det_folder"] == det_folder
    if th is not None:
        keep &= np.isclose(pd.to_numeric(frames["th"], errors="coerce"), th)
    return frames[keep]


def run_time(frames: pd.DataFrame) -> Tuple[np.ndarray, str]:
    """``(t, label)`` — the time axis of an in-situ run's frames, in order.

    Seconds since its first frame when the elapsed time moves; the frame
    counter when it does not (every frame of one spin carries the scan's
    start time).
    """
    elapsed = pd.to_numeric(frames["elapsed_s"], errors="coerce").to_numpy(float)
    counter = pd.to_numeric(frames["frame"], errors="coerce").to_numpy(float)
    if np.isfinite(elapsed).sum() > 1 and np.nanmax(elapsed) > np.nanmin(elapsed):
        # Several frames in one scan share its start: spread them by the
        # exposure, so the clock keeps moving.
        exposure = pd.to_numeric(frames["exposure_s"], errors="coerce").to_numpy(float)
        within = np.where(np.isfinite(counter) & np.isfinite(exposure), counter * exposure, 0.0)
        return elapsed + within - np.nanmin(elapsed), "time (s)"
    if np.isfinite(counter).any():
        return counter, "frame"
    return np.arange(len(frames), dtype=float), "frame order"


RUN_AXES = {
    "time": "time (s) — or the frame counter of one spin",
    "index": "frame index in the series",
    "RH": "relative humidity (%)",
    "T_C": "temperature (°C)",
    "scan": "scan id",
}


def run_axis(frames: pd.DataFrame, axis: str = "time") -> Tuple[np.ndarray, str]:
    """``(values, label)`` of one of :data:`RUN_AXES` for a run's frames."""
    if axis == "time":
        return run_time(frames)
    labels = {"index": "index", "RH": "RH (%)", "T_C": "T (°C)", "scan": "scan"}
    if axis not in labels:
        raise ValueError(f"axis must be one of {sorted(RUN_AXES)}, not {axis!r}")
    return pd.to_numeric(frames[axis], errors="coerce").to_numpy(float), labels[axis]


def frame_label(row) -> str:
    """A short name for one frame in a picker."""
    parts = []
    if row.get("kind") == "insitu":
        if pd.notna(row.get("index")):
            parts.append(f"#{int(row['index'])}")
        if pd.notna(row.get("elapsed_s")):
            parts.append(f"{row['elapsed_s']:g} s")
        if pd.notna(row.get("frame")) and row.get("frame"):
            parts.append(f"frame {int(row['frame'])}")
        if pd.notna(row.get("RH")):
            parts.append(f"RH {row['RH']:.1f}%")
        if pd.notna(row.get("T_C")):
            parts.append(f"{row['T_C']:.1f}°C")
    else:
        if pd.notna(row.get("pos")):
            parts.append(f"pos{int(row['pos'])}")
        if pd.notna(row.get("x")):
            parts.append(f"x{row['x']:+.3f}")
        if pd.notna(row.get("th")):
            parts.append(f"th{row['th']:.3f}")
    if pd.notna(row.get("scan")):
        parts.append(f"scan {int(row['scan'])}")
    return " · ".join(parts) or str(row.get("stem"))


# ---------------------------------------------------------------------------
# Curves
# ---------------------------------------------------------------------------


def stack_iq(
    curves: Sequence[Tuple[np.ndarray, np.ndarray]], q: Optional[np.ndarray] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """I(q) of several frames on one q axis: ``(q, I[n_curves, n_q])``.

    Frames reduced with one geometry share their q bins and are stacked as
    they are; any other is interpolated onto *q* (default: the first
    curve's), NaN outside its own range.
    """
    curves = [(np.asarray(x, float), np.asarray(y, float)) for x, y in curves]
    if not curves:
        return np.array([]), np.zeros((0, 0))
    grid = np.asarray(q, float) if q is not None else curves[0][0]
    out = np.full((len(curves), grid.size), np.nan)
    for i, (x, y) in enumerate(curves):
        if x.shape == grid.shape and np.allclose(x, grid, rtol=1e-6, equal_nan=True):
            out[i] = y
            continue
        good = np.isfinite(x) & np.isfinite(y)
        if good.sum() < 2:
            continue
        order = np.argsort(x[good])
        xs, ys = x[good][order], y[good][order]
        inside = (grid >= xs[0]) & (grid <= xs[-1])
        out[i, inside] = np.interp(grid[inside], xs, ys)
    return grid, out


def evenly_spaced(n: int, count: int) -> np.ndarray:
    """*count* indices spread evenly over ``range(n)``, first and last kept."""
    if n <= 0 or count <= 0:
        return np.array([], dtype=int)
    if count >= n:
        return np.arange(n)
    return np.unique(np.round(np.linspace(0, n - 1, count)).astype(int))


# ---------------------------------------------------------------------------
# pyDataOrg
# ---------------------------------------------------------------------------

MODALITIES = {
    # key: (label, shape, x_label, y_label, log_x, log_y, extensions)
    "iq": ("I(q) · circular average", "series", "q (Å⁻¹)", "I(q)", True, True, (".csv",)),
    "qimage": ("q-image (qxy–qz)", "image", "qxy (Å⁻¹)", "qz (Å⁻¹)", False, False, (".npz",)),
    "qphi": ("q–φ map", "image", "q (Å⁻¹)", "φ (°)", False, False, (".npz",)),
    "qc": ("reduction check (QC)", "image", "", "", False, False, (".png",)),
}
PRODUCT_MODALITY = {"cir": "iq", "qimg": "qimage", "qphi": "qphi", "qc": "qc"}


def register_with_pydataorg() -> None:
    """Teach pyDataOrg the four products and the in-situ frame clock, so its
    own pages (Explore, Visualize) can show them. Safe to call again."""
    from pyDataOrg.analysis.frames import FrameGrammar, register_grammar
    from pyDataOrg.core import modality

    for key, (label, shape, xl, yl, lx, ly, ext) in MODALITIES.items():
        modality.register(
            modality.Modality(
                key=key,
                label=label,
                domain="scattering",
                shape=shape,
                x_label=xl,
                y_label=yl,
                log_x=lx,
                log_y=ly,
                extensions=ext,
                category="scattering",
            ),
            overwrite=True,
        )
    register_grammar(
        FrameGrammar(
            key="cms_insitu",
            label="CMS in-situ (…_228_4623.0s_x…_T69.98C_…)",
            patterns=(
                re.compile(r"_\d+_(?P<t>\d+(?:\.\d+)?)s_x.*_T(?P<T>-?\d+(?:\.\d+)?)C_"),
                re.compile(r"_\d+_(?P<t>\d+(?:\.\d+)?)s_x"),
            ),
        ),
        overwrite=True,
    )


def role(det: str, th) -> str:
    """How two measurements of one sample are told apart: the detector and
    the incident angle (``waxs_th0.100``)."""
    return det if th is None or pd.isna(th) else f"{det}_th{float(th):.3f}"


def _params(row: dict) -> dict:
    return {k: (None if (not isinstance(v, str) and pd.isna(v)) else v) for k, v in row.items()}


def sample_params(part: pd.DataFrame) -> dict:
    """The facts :func:`build_organizer` records on a sample, for one folder:
    its row of :func:`sample_table`."""
    row = sample_table(part).iloc[0].to_dict()
    row.pop("folder")
    row.pop("sample")
    return _params(row)


def link_rows(frames: pd.DataFrame) -> pd.DataFrame:
    """The links of an experiment's frames, in pyDataOrg's ``link_table``
    form: a row per sample, product, folder (``stage``) and detector + angle
    (``role``), its files ``;``-joined in ``paths``. Read back with
    ``org.link_table(rows)``."""
    rows = []
    for (folder, sample), part in frames.groupby(["folder", "sample"], sort=False):
        for (det, th), group in part.groupby(["det_folder", part["th"].fillna(-999.0)], sort=False):
            th = None if th == -999.0 else th
            for product, key in PRODUCT_MODALITY.items():
                paths = [p for p in group[product] if isinstance(p, str)]
                if paths:
                    rows.append(
                        dict(
                            sample_id=sample,
                            modality=key,
                            stage=folder,
                            role=role(_detector(det), th),
                            paths=";".join(paths),
                            det_folder=det,
                        )
                    )
    return pd.DataFrame(
        rows, columns=["sample_id", "modality", "stage", "role", "paths", "det_folder"]
    )


#: A link is recorded relative to the org's folder when it climbs at most
#: this many folders from it (``../experiments/<name>/…``): the org and its
#: data then open together from any mount of the tree they share.
MAX_CLIMB = 3


def recorded_path(path, base) -> str:
    """*path* as an org in folder *base* records it: relative to *base* when
    that climbs at most :data:`MAX_CLIMB` folders, else as it is."""
    path = str(path)
    if base is None:
        return path
    try:
        relative = os.path.relpath(path, str(base))
    except ValueError:  # another drive (Windows)
        return path
    climbs = Path(relative).parts.count("..")
    return Path(relative).as_posix() if climbs <= MAX_CLIMB else path


def build_organizer(
    frames: pd.DataFrame,
    store,
    *,
    name: str = "",
    aliases: Optional[Dict[str, Sequence[str]]] = None,
    organizer=None,
    relative: bool = True,
):
    """A pyDataOrg :class:`~pyDataOrg.Organizer` of an experiment's frames.

    A sample per sample name; a stage per experiment folder, holding
    :func:`sample_params`; a measurement per product, detector and angle
    (:func:`link_rows`), linked to its files where they are — nothing is
    copied. *store* is the organiser's JSON (reopened if it exists: links
    are replaced, notes and tags kept). Not saved: call ``org.save()``.

    The files are recorded relative to the organiser's folder where they
    are near it (:func:`recorded_path`); *relative* False keeps them as
    given. Pass *organizer* to relink into one already open.
    """
    from pyDataOrg.core.schema import Measurement

    if organizer is None:
        from pyDataOrg import Organizer

        organizer = Organizer(store, name=name, aliases=aliases)
    register_with_pydataorg()
    for row in sample_table(frames).to_dict("records"):
        folder, sample = row.pop("folder"), row.pop("sample")
        organizer.set_params(sample, stage=folder, **_params(row))
    # What ``org.link(sample, key, paths, stage=…, role=…)`` records, made
    # here: link() stats every file of a list to make sure none is a folder,
    # and an experiment is tens of thousands of files on NFS — a minute.
    # These lists come from directory listings: they are files.
    project = organizer.project
    base = Path(organizer.path).parent if relative else None
    for row in link_rows(frames).itertuples(index=False):
        sample = project.get_sample(row.sample_id) or project.add_sample(row.sample_id)
        sample.add_measurement(
            Measurement(
                sample_id=row.sample_id,
                modality=row.modality,
                stage=row.stage,
                role=row.role,
                paths=[recorded_path(p, base) for p in row.paths.split(";")],
                meta=dict(det_folder=row.det_folder, linked=True),
            )
        )
    return organizer


__all__ = [
    "PRODUCTS",
    "FRAME_COLUMNS",
    "RUN_AXES",
    "MODALITIES",
    "parse_frame",
    "product_stem",
    "detector_folders",
    "experiment_folders",
    "index_folder",
    "index_experiment",
    "sort_frames",
    "progress_table",
    "span",
    "sample_table",
    "frames_of",
    "run_time",
    "run_axis",
    "frame_label",
    "stack_iq",
    "evenly_spaced",
    "register_with_pydataorg",
    "role",
    "sample_params",
    "link_rows",
    "MAX_CLIMB",
    "recorded_path",
    "build_organizer",
    "InsituMeta",
    "parse_insitu_meta",
    "insitu_series",
]
