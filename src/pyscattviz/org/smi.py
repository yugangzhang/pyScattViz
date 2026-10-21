"""SMI (NSLS-II 12-ID): what an experiment's names, reduction configs and
raw folders say about it.

An SMI project is ``<proposal>/projects/<name>/``: the raw frames in
``user_data/<detector>/`` (``2M``, ``900KW``), the reduction's products in
``Results/<folder>/`` (``giwaxs/cir_avg`` …) and the YAML configs it ran
with in ``Results/configs/``. A frame's name is written by the acquisition
(``YZhang_SMI_Base.py`` in SWAXS_user_scripts) and appended to by the
beamline::

    <group>_<sample>[_<ai>deg][_<idx>_<t>s]_x<x>_y<y>_z<z>[_T<T>C][_E<E>V][_<extra>]
        _expt<t>s_<energy>eV_wa<arc>_sdd<mm>mm_id<scan>_<frame>_<SAXS2M|WAXS>.tif

The reduction keeps the name, with ``waxsSTITCH`` for the arc of a WAXS
frame stitched over its arcs. The first field is the group's tag (``QYu``)
where the name before the conditions has more than one; the sample is the
rest (``SR_2025S4``).

:func:`parse_frame` reads a name; :func:`with_raw` adds to each reduced
frame the raw frames it was made of; :func:`describe` is what an org keeps
about the experiment — where it was measured, how it was acquired, how it
was reduced. Only listings and the YAML configs are read, never a frame.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from pyscattviz.org import cms

_NUM = r"-?\d+(?:\.\d+)?"
_POS = r"\d+(?:\.\d+)?"
#: What the beamline appends: energy, WAXS arc (``waxsSTITCH`` once
#: stitched), SAXS distance, scan id, frame, detector.
_SUFFIX = (
    rf"_(?P<energy_eV>{_POS})eV_wa(?:(?P<arc_deg>{_NUM})|xs(?P<arc_tag>[A-Za-z0-9]*))"
    rf"_sdd(?P<sdd_mm>{_POS})mm_id(?P<scan>\d+)_(?P<frame>\d+)_(?P<det_token>[A-Za-z0-9]+)"
    r"(?:\.tiff?)?$"
)
NAME_RE = re.compile(
    r"^(?P<head>.+?)"
    r"(?:_(?P<th>\d+\.\d+)deg)?"
    rf"(?:_(?P<index>\d+)_(?P<elapsed_s>{_POS})s)?"
    rf"_x(?P<x>{_NUM})(?:_y(?P<y>{_NUM}))?(?:_z(?P<z>{_NUM}))?"
    rf"(?:_T(?P<T_C>{_NUM})C)?(?:_E(?P<E_V>{_NUM})V)?"
    r"(?:_(?P<extra>.+?))?"
    rf"_expt(?P<exposure_s>{_POS})s" + _SUFFIX
)
#: A frame the beamline wrote with no sample's name (``alignment_gisaxs_…``,
#: ``snapshot_…``).
OTHER_RE = re.compile(r"^(?P<head>.*?)" + _SUFFIX)
_TIFF_RE = re.compile(r"\.tiff?$", re.IGNORECASE)
_CYCLE_RE = re.compile(r"^\d{4}-\d+$")
_FLOATS = (
    "th",
    "elapsed_s",
    "x",
    "y",
    "z",
    "T_C",
    "E_V",
    "exposure_s",
    "energy_eV",
    "arc_deg",
    "sdd_mm",
)
_INTS = ("index", "scan", "frame")
#: A calibrant's sample name (``AgBH``, ``AgBH_run2``) — not a sample
#: made of one (``…_CeO2_Powder``).
CALIBRANT_RE = re.compile(r"^(?:agbh|agbe|lab6)(?:[_-]|$)", re.IGNORECASE)
BACKGROUND_RE = re.compile(r"(?:^|_)(?:empty|blank|bkg|background)", re.IGNORECASE)

#: The columns an SMI frame has beyond :data:`cms.FRAME_COLUMNS`, and what
#: each holds.
COLUMNS = {
    "group": str,
    "y": float,
    "z": float,
    "E_V": float,
    "energy_eV": float,
    "arc_deg": float,
    "arc_tag": str,
    "sdd_mm": float,
    "det_token": str,
    "arcs": str,
    "raw_scans": str,
}
#: One row per raw frame (:func:`raw_frames`).
RAW_COLUMNS = (
    "raw_folder",
    "path",
    "stem",
    "other",
    "group",
    "sample",
    "kind",
    *_FLOATS,
    *_INTS,
    "det_token",
)


# ---------------------------------------------------------------------------
# One frame
# ---------------------------------------------------------------------------


def _number(name: str, text: Optional[str]):
    if text is None:
        return None
    value = float(text)
    return int(value) if name in _INTS else value + 0.0  # wa-0.0 is arc 0


def parse_frame(name: str) -> Optional[dict]:
    """What an SMI frame name says, or None for a name that is not one.

    ``group`` is the first field of the name before its conditions when
    there are more than one, ``sample`` the rest; ``kind`` is ``"insitu"``
    for a frame of a series (``_<idx>_<t>s``). ``arc_deg`` is None for a
    stitched WAXS frame, whose ``arc_tag`` says how (``STITCH``).
    """
    stem = os.path.basename(str(name))
    match = NAME_RE.match(stem)
    if match is None:
        return None
    found = match.groupdict()
    row = {k: _number(k, found[k]) for k in _FLOATS + _INTS}
    group, _, sample = found["head"].partition("_")
    if not sample:
        group, sample = None, found["head"]
    moving = row["index"] is not None or row["elapsed_s"] is not None
    row.update(
        stem=stem,
        sample=sample,
        group=group,
        kind="insitu" if moving else "static",
        pos=None,
        RH=None,
        arc_tag=found["arc_tag"],
        det_token=found["det_token"],
    )
    return row


def _key(group, sample, th, index, x, y, det) -> str:
    """One spot of one sample, at one angle (and one point of a series), on
    one detector: what the frames of its arcs share."""

    def text(v):
        return "" if v is None or (isinstance(v, float) and np.isnan(v)) else f"{v}"

    def number(v):
        return "" if v is None or pd.isna(v) else f"{float(v):.3f}"

    return "|".join(
        [text(group), text(sample), number(th), number(index), number(x), number(y), text(det)]
    )


def _keys(frame: pd.DataFrame) -> List[str]:
    columns = ("group", "sample", "th", "index", "x", "y", "det_token")
    return [_key(*values) for values in zip(*(frame[c] for c in columns))]


# ---------------------------------------------------------------------------
# A project and its raw frames
# ---------------------------------------------------------------------------


def project_parts(root) -> Optional[tuple]:
    """``(cycle, proposal, project, below)`` of a folder of an SMI project,
    ``…/<cycle>/<proposal>/projects/<project>[/<below>…]``; None for any
    other folder."""
    parts = Path(root).parts
    for i in range(len(parts) - 2, 1, -1):
        if parts[i] == "projects" and _CYCLE_RE.match(parts[i - 2]):
            return parts[i - 2], parts[i - 1], parts[i + 1], tuple(parts[i + 2 :])
    return None


def project_dir(root) -> Optional[Path]:
    """The project folder *root* is in: *root* or one of the three folders
    above it, the first holding ``user_data/``."""
    root = Path(root)
    for folder in (root, *list(root.parents)[:3]):
        if (folder / "user_data").is_dir():
            return folder
    return None


def raw_folders(project) -> List[Path]:
    """The detector folders of ``user_data/`` (``2M``, ``900KW``, ``OVA`` …)."""
    home = Path(project) / "user_data"
    return [home / n for n in sorted(cms._names(home)) if (home / n).is_dir()]


def raw_frames(project) -> pd.DataFrame:
    """Every raw frame of a project, one row per file of ``user_data/*/``:
    what its name says, or — for a frame the beamline wrote with no sample's
    name — what it was in ``other`` (``alignment_gisaxs``, ``snapshot``)."""
    rows = []
    for folder in raw_folders(project) if project is not None else []:
        for name in cms._names(folder):
            if not _TIFF_RE.search(name):
                continue
            row = parse_frame(name)
            if row is None:
                match = OTHER_RE.match(name)
                row = dict(stem=name, other=match["head"] if match else "other")
                if match:
                    row.update(scan=int(match["scan"]), det_token=match["det_token"])
            row.update(raw_folder=folder.name, path=str(folder / name))
            rows.append(row)
    return pd.DataFrame(rows, columns=list(RAW_COLUMNS))


def with_raw(frames: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """*frames* with, for each reduced frame, the raw frames of its spot on
    its detector: their arcs (``arcs``, ``"0, 20, 40"``) and scans
    (``raw_scans``) — and its raw file (``raw``) where it is one."""
    frames = frames.copy()
    frames["arcs"] = None
    frames["raw_scans"] = None
    named = raw[raw["sample"].notna()] if not raw.empty else raw
    if frames.empty or named.empty:
        return frames
    spots: Dict[str, list] = {}
    for key, arc, scan in zip(_keys(named), named["arc_deg"], named["scan"]):
        spots.setdefault(key, []).append((arc, scan))
    files = {_TIFF_RE.sub("", s): p for s, p in zip(named["stem"], named["path"])}
    arcs, scans = [], []
    for key in _keys(frames):
        found = spots.get(key, [])
        arcs.append(", ".join(f"{a:g}" for a in sorted({a for a, _ in found if pd.notna(a)})))
        scans.append(", ".join(str(int(s)) for s in sorted({s for _, s in found if pd.notna(s)})))
    frames["arcs"] = [a or None for a in arcs]
    frames["raw_scans"] = [s or None for s in scans]
    missing = frames["raw"].isna()
    frames.loc[missing, "raw"] = frames.loc[missing, "stem"].map(files)
    return frames


def raw_token(det_folder: str, frames: pd.DataFrame) -> Optional[str]:
    """The detector a reduced folder holds frames of (``WAXS``, ``SAXS2M``):
    as its frames' names say, else as its name does."""
    if not frames.empty and frames["det_token"].notna().any():
        return frames["det_token"].mode().iloc[0]
    name = det_folder.lower()
    return "WAXS" if "waxs" in name else "SAXS2M" if "saxs" in name else None


def raw_of(det_folder: str, frames: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """The raw frames a reduced folder is made of: its detector's, and of a
    grazing folder (``gi…``) those at an angle, of a transmission one
    (``t…``) those at none."""
    if raw.empty:
        return raw
    keep = raw["sample"].notna() & (raw["det_token"] == raw_token(det_folder, frames))
    name = det_folder.lower()
    if name.startswith("gi"):
        keep &= raw["th"].notna()
    elif name.startswith("t"):
        keep &= raw["th"].isna()
    return raw[keep]


def to_reduce(det_folder: str, frames: pd.DataFrame, raw: pd.DataFrame) -> int:
    """The spots of *det_folder*'s raw frames with no reduced frame yet."""
    return len(set(_keys(raw_of(det_folder, frames, raw))) - set(_keys(frames)))


# ---------------------------------------------------------------------------
# What an org keeps
# ---------------------------------------------------------------------------


def _jsonable(value):
    """*value* as JSON can hold it: string keys, lists, plain numbers, ISO
    dates; NaN is None."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, (datetime.date, datetime.datetime, pd.Timestamp)):
        return value.isoformat()
    if value is None or isinstance(value, str):
        return value
    return str(value)


def _values(series) -> List[float]:
    v = pd.to_numeric(pd.Series(series), errors="coerce").dropna()
    return sorted({round(float(x), 4) + 0.0 for x in v})


def _range(series) -> Optional[List[int]]:
    v = pd.to_numeric(pd.Series(series), errors="coerce").dropna()
    return None if v.empty else [int(v.min()), int(v.max())]


def _written(paths: pd.Series) -> Optional[List[str]]:
    """When the first and the last of *paths* were written."""
    times = []
    for path in (paths.iloc[0], paths.iloc[-1]) if len(paths) else ():
        try:
            times.append(datetime.datetime.fromtimestamp(os.stat(path).st_mtime))
        except OSError:
            return None
    return [t.isoformat(timespec="seconds") for t in times] or None


def identity(root) -> dict:
    """Where an experiment was measured: beamline, cycle, proposal, project."""
    found = dict(facility="NSLS-II", beamline="SMI (12-ID)")
    parts = project_parts(root)
    if parts:
        found.update(cycle=parts[0], proposal=parts[1], project=parts[2])
    return found


def _read_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        return {"error": "PyYAML is not installed here: the config was not read"}
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        return {"error": str(exc)}
    return {"config": data} if isinstance(data, dict) else {"error": "not a YAML mapping"}


def _config_folders(root: Path) -> List[Path]:
    """``configs/`` at *root*, one folder below it (``Results/<group>/``),
    and above it up to its project."""
    project = project_dir(root)
    found = [root / "configs", *sorted(root.glob("*/configs"))]
    for folder in root.parents:
        if project is None or project not in (folder, *folder.parents):
            break
        found.append(folder / "configs")
    return [f for f in dict.fromkeys(found) if f.is_dir()]


def reduction(root, base=None) -> Dict[str, dict]:
    """The reduction's YAML configs of *root*'s experiment, by file name: each
    as written (``config``: detector, energy, distance, beam centre, mask,
    geometry, products …) and where it is (``file``)."""
    found = {}
    for folder in _config_folders(Path(root)):
        for path in sorted(folder.glob("*.y*ml")):
            found[path.stem] = dict(file=cms.recorded_path(path, base), **_read_yaml(path))
    return found


def _folder_summary(folder: Path, rows: pd.DataFrame, base=None) -> dict:
    named = rows[rows["sample"].notna()].sort_values("scan", na_position="first")
    other = rows[rows["sample"].isna()]
    by_scan = rows.sort_values("scan", na_position="first")
    summary = dict(
        folder=cms.recorded_path(folder, base),
        files=len(cms._names(folder)),
        frames=len(rows),
        sample_frames=len(named),
        detectors=sorted(rows["det_token"].dropna().unique()),
        scans=_range(rows["scan"]),
        written=_written(by_scan["path"]),
        energy_eV=_values(named["energy_eV"]),
        arcs_deg=_values(named["arc_deg"]),
        sdd_mm=_values(named["sdd_mm"]),
        exposure_s=_values(named["exposure_s"]),
    )
    if not other.empty:
        summary["other"] = {
            head: dict(frames=len(part), scans=_range(part["scan"]))
            for head, part in other.groupby("other", sort=True)
        }
    return summary


def _offsets(values) -> tuple:
    v = sorted(set(round(float(x), 3) for x in pd.Series(values).dropna()))
    return tuple(round(x - v[len(v) // 2], 3) + 0.0 for x in v) if v else ()


def strategy(raw: pd.DataFrame) -> dict:
    """How the samples were measured, as their raw frames' names say: the
    geometry, energy, distance, angles, each detector's arcs, the exposure,
    the spots per sample and where they lie from the middle one, the scans
    and — for a series — its length, temperature and potential."""
    named = raw[raw["sample"].notna()] if not raw.empty else raw
    if named.empty:
        return {}
    samples = named.drop_duplicates(["group", "sample"])["sample"]
    # A calibrant is measured in transmission whatever the samples are.
    grazing = named.loc[~named["sample"].str.contains(CALIBRANT_RE), "th"].notna()
    out = dict(
        geometry=(
            "grazing incidence"
            if grazing.all()
            else "transmission"
            if not grazing.any()
            else "grazing incidence and transmission"
        ),
        groups=sorted(named["group"].dropna().unique()),
        samples=int(len(samples)),
        calibrants=sorted({s for s in samples if CALIBRANT_RE.search(s)}),
        backgrounds=sorted({s for s in samples if BACKGROUND_RE.search(s)}),
        energy_keV=_values(named["energy_eV"] / 1000.0),
        sdd_mm=_values(named["sdd_mm"]),
        incident_angles_deg=_values(named["th"]),
        arcs_deg={det: _values(p["arc_deg"]) for det, p in named.groupby("det_token")},
        frames={det: int(len(p)) for det, p in named.groupby("det_token")},
        exposure_s=_values(named["exposure_s"]),
        scans=_range(named["scan"]),
    )
    static = named[named["kind"] == "static"]
    if not static.empty:
        parts = [p for _, p in static.groupby(["group", "sample", "th"], dropna=False)]
        spots = Counter(len(p.drop_duplicates(["x", "y"])) for p in parts)
        out["spots_per_sample"] = int(spots.most_common(1)[0][0])
        out["spot_offsets_um"] = {
            axis: list(Counter(_offsets(p[axis]) for p in parts).most_common(1)[0][0])
            for axis in ("x", "y")
        }
    series = named[named["kind"] == "insitu"]
    if not series.empty:
        out["series"] = int(len(series.drop_duplicates(["group", "sample"])))
        out["elapsed_s"] = _values([series["elapsed_s"].min(), series["elapsed_s"].max()])
    for column, label in (("T_C", "T_C"), ("E_V", "potential_V")):
        if named[column].notna().any():
            out[label] = _values([named[column].min(), named[column].max()])
    return out


def _logs(project: Optional[Path], base=None) -> dict:
    """The acquisition's own logs, where it wrote them beside the data
    (``yz_logs/``): each logbook's rows and the alignments, as saved."""
    folder = project / "yz_logs" if project is not None else None
    if folder is None or not folder.is_dir():
        return {}
    found: dict = dict(folder=cms.recorded_path(folder, base))
    for path in sorted(folder.glob("logbook_*.csv")):
        try:
            lines = path.read_text().splitlines()
        except OSError:
            continue
        header = lines[0].split(",") if lines else []
        found.setdefault("logbooks", {})[path.name] = dict(
            rows=max(len(lines) - 1, 0), columns=header
        )
    for path in sorted(folder.glob("alignment_*.json")):
        try:
            found.setdefault("alignments", {})[path.stem] = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
    return found


def _of_samples(raw: pd.DataFrame, frames: Optional[pd.DataFrame]) -> pd.DataFrame:
    """The raw frames of the samples *frames* holds, and of their groups'
    calibrants, which are seldom reduced with them (all, without frames): a
    project's ``user_data/`` can hold other groups' too."""
    if raw.empty or frames is None or frames.empty or "group" not in frames:
        return raw
    mine = set(zip(frames["group"].fillna(""), frames["sample"]))
    groups = {g for g, _ in mine}
    keep = [
        (g, s) in mine or (g in groups and isinstance(s, str) and bool(CALIBRANT_RE.search(s)))
        for g, s in zip(raw["group"].fillna(""), raw["sample"])
    ]
    return raw[keep]


def describe(root, frames: Optional[pd.DataFrame] = None, *, base=None) -> dict:
    """What an org keeps about the SMI experiment at *root*:

    ``identity``     facility, beamline, cycle, proposal, project
    ``acquisition``  each raw folder (``user_data/<det>``): frames, scans,
                     when written, energy, arcs, distance, exposure, and the
                     beamline's own frames (alignment scans, snapshots)
    ``strategy``     how the samples were measured (:func:`strategy`)
    ``reduction``    each YAML config the reduction ran with, as written
    ``logs``         the acquisition's logbooks and alignments, where kept

    *frames* (the reduced frames) limits ``strategy`` to their samples;
    files are recorded relative to *base* (the org's folder) where near it.
    """
    root = Path(root)
    project = project_dir(root)
    raw = raw_frames(project)
    found = dict(identity(root))
    found["described_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    if project is not None:
        found["acquisition"] = {
            folder.name: _folder_summary(folder, raw[raw["raw_folder"] == folder.name], base)
            for folder in raw_folders(project)
        }
    found["strategy"] = strategy(_of_samples(raw, frames))
    found["reduction"] = reduction(root, base)
    logs = _logs(project, base)
    if logs:
        found["logs"] = logs
    return _jsonable(found)


__all__ = [
    "NAME_RE",
    "COLUMNS",
    "RAW_COLUMNS",
    "parse_frame",
    "project_parts",
    "project_dir",
    "raw_folders",
    "raw_frames",
    "with_raw",
    "raw_token",
    "raw_of",
    "to_reduce",
    "identity",
    "reduction",
    "strategy",
    "describe",
]
