"""How a data folder is read into frames: a small registry of layouts.

An org is made from a data folder by a *layout*, which reads the folder's
listings — never a file — into one row per reduced frame
(:data:`~pyscattviz.org.cms.FRAME_COLUMNS`). Every Org page works from that
table, so a new kind of folder needs a new layout and nothing else::

    detect_layout(root)                       # "cms", "products" or None
    frames = index(root, "cms")               # one row per reduced frame
    frames = index(root, "products", {"sample_pattern": r"^(?P<sample>.+?)_x"})

Three are built in:

``cms``       a CMS experiment, ``experiments/<name>/<folder>/<detector>/
              {raw,analysis}`` — the names say spot, angle, scan, and for an
              in-situ run its time, humidity and temperature
              (:mod:`pyscattviz.org.cms`)
``smi``       an SMI project's ``Results/`` — the names say group, sample,
              angle, spot, energy, arc, distance and scan; the raw frames of
              ``user_data/`` and the reduction's configs say how it was
              measured and reduced (:mod:`pyscattviz.org.smi`)
``products``  any folder holding the reduction's product folders
              (``cir_avg``, ``q_image``, ``qphi``, ``qc``, SMI's ``Cir_Avg``,
              ``Stitch_Data`` …) somewhere below it; what a name says is read
              with a regular expression whose named groups are the columns
              (``sample``, ``th``, ``x``, ``T_C``, ``RH``, ``elapsed_s`` …)

The options a layout takes are checked by :func:`check_options`, which is
also what an AI model's proposal (:func:`pyscattviz.org.ask.propose_source`)
has to pass before anything is built from it.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional

import pandas as pd

from pyscattviz.org import cms, smi
from pyscattviz.products import (
    SCATTERING_PRODUCTS,
    _iter_product_files,
    product_folders,
    product_key_for_folder,
    stem_of,
)

# Columns a sample pattern may fill, and how each is read.
PATTERN_FIELDS: Dict[str, type] = {
    "sample": str,
    "pos": int,
    "x": float,
    "th": float,
    "exposure_s": float,
    "scan": int,
    "frame": int,
    "index": int,
    "elapsed_s": float,
    "T_C": float,
    "RH": float,
}
KINDS = ("auto", "static", "insitu")
#: Folders below a ``products`` root searched for product folders, at most.
MAX_DEPTH = 4
MAX_FOLDERS = 5_000


@dataclass(frozen=True)
class Layout:
    """One way of reading a data folder into frames.

    *detect* says whether a folder looks like this layout; *index* reads it
    (``(root, options) -> frames``); *progress*, when there is one, counts
    raw against reduced (``(root, options) -> table``); *describe*, when
    there is one, says how the folder was measured and reduced, for an org
    to keep (``(root, options, frames, base) -> dict``). *options* names
    each option it takes and says what it does.
    """

    key: str
    label: str
    description: str
    detect: Callable[[Path], bool]
    index: Callable[[Path, Mapping], pd.DataFrame]
    progress: Optional[Callable[[Path, Mapping], pd.DataFrame]] = None
    options: Mapping[str, str] = field(default_factory=dict)
    describe: Optional[Callable[..., dict]] = None


LAYOUTS: Dict[str, Layout] = {}


def register_layout(layout: Layout, *, overwrite: bool = False) -> Layout:
    """Add a layout. Detection tries layouts in the order registered."""
    if layout.key in LAYOUTS and not overwrite:
        raise ValueError(f"a layout {layout.key!r} is registered already")
    LAYOUTS[layout.key] = layout
    return layout


def get_layout(key: str) -> Layout:
    try:
        return LAYOUTS[key]
    except KeyError:
        raise KeyError(f"no layout {key!r}; there are {sorted(LAYOUTS)}") from None


def detect_layout(root) -> Optional[str]:
    """The first layout that recognises *root*, or None."""
    root = Path(root)
    if not root.is_dir():
        return None
    for layout in LAYOUTS.values():
        try:
            if layout.detect(root):
                return layout.key
        except OSError:
            continue
    return None


def check_options(key: str, options: Optional[Mapping] = None) -> dict:
    """*options* for layout *key*, checked: unknown names, a pattern that
    does not compile or names a column there is not, an unknown kind —
    each raises ValueError. Returns a clean copy."""
    layout = get_layout(key)
    options = dict(options or {})
    unknown = sorted(set(options) - set(layout.options))
    if unknown:
        raise ValueError(f"layout {key!r} takes {sorted(layout.options)}, not {unknown}")
    folders = options.get("folders")
    if folders is not None:
        if isinstance(folders, str) or not all(isinstance(f, str) for f in folders):
            raise ValueError("folders must be a list of folder names")
        options["folders"] = list(folders) or None
    pattern = options.get("sample_pattern")
    if pattern:
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"sample_pattern does not compile: {exc}") from None
        extra = sorted(set(compiled.groupindex) - set(PATTERN_FIELDS))
        if extra:
            raise ValueError(f"sample_pattern names {extra}; it may name {sorted(PATTERN_FIELDS)}")
        if "sample" not in compiled.groupindex:
            raise ValueError("sample_pattern must have a (?P<sample>…) group")
    kind = options.get("kind")
    if kind is not None and kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, not {kind!r}")
    return {k: v for k, v in options.items() if v not in (None, "", [])}


def index(root, key: str, options: Optional[Mapping] = None) -> pd.DataFrame:
    """Every reduced frame under *root*, read by layout *key*."""
    return get_layout(key).index(Path(root), check_options(key, options))


def progress(root, key: str, options: Optional[Mapping] = None) -> pd.DataFrame:
    """Raw against reduced, per folder and detector (empty if the layout
    cannot tell)."""
    layout = get_layout(key)
    if layout.progress is None:
        return pd.DataFrame()
    return layout.progress(Path(root), check_options(key, options))


# ---------------------------------------------------------------------------
# cms
# ---------------------------------------------------------------------------


def _cms_index(root: Path, options: Mapping) -> pd.DataFrame:
    return cms.index_experiment(root, folders=options.get("folders"))


def _cms_progress(root: Path, options: Mapping) -> pd.DataFrame:
    table = cms.progress_table(root)
    folders = options.get("folders")
    return table[table["folder"].isin(folders)] if folders else table


register_layout(
    Layout(
        key="cms",
        label="CMS experiment",
        description="experiments/<name>/<folder>/<saxs|waxs|maxs…>/{raw,analysis/{cir_avg,"
        "q_image,qphi,qc,stitched}}; CMS frame names (spot, angle, scan; in situ "
        "the time, RH and T)",
        detect=lambda root: bool(cms.experiment_folders(root)),
        index=_cms_index,
        progress=_cms_progress,
        options={
            "folders": 'only these experiment folders (e.g. ["2_Humidity"]); default every one'
        },
    )
)


# ---------------------------------------------------------------------------
# products
# ---------------------------------------------------------------------------

# Frame columns ← pyScattViz's product keys.
_COLUMNS = {"raw": "stitched", "cir": "cir_avg", "qimg": "q_image", "qphi": "qphi", "qc": "qc"}
_REDUCED = ("cir", "qimg", "qphi")


def _subdirs(path: Path) -> List[Path]:
    try:
        with os.scandir(path) as entries:
            return sorted(
                Path(e.path) for e in entries if not e.name.startswith(".") and e.is_dir()
            )
    except OSError:
        return []


def product_homes(root, *, depth: int = MAX_DEPTH) -> List[Path]:
    """The folders at or below *root* that hold product folders, in order;
    one is not searched below."""
    found, level, seen = [], [Path(root)], 0
    for _ in range(depth + 1):
        following = []
        for folder in level:
            seen += 1
            if seen > MAX_FOLDERS:
                return found
            if product_folders(folder):
                found.append(folder)
                continue
            following += [
                p
                for p in _subdirs(folder)
                if product_key_for_folder(p.name) is None and p.name != "raw"
            ]
        level = following
    return sorted(found)


def _where(home: Path, root: Path):
    """``(folder, det_folder, det_dir)`` of a product home: ``analysis/``
    belongs to the detector folder holding it."""
    det_dir = home.parent if home.name.lower() == "analysis" and home != root else home
    if det_dir == root:
        return root.name, root.name, det_dir
    folder = Path(os.path.relpath(det_dir.parent, root)).as_posix()
    return (root.name if folder == "." else folder), det_dir.name, det_dir


def _value(text, kind: type):
    try:
        return kind(float(text)) if kind is int else kind(text)
    except (TypeError, ValueError):
        return None


def parse_with(stem: str, pattern: Optional[re.Pattern], kind: str = "auto") -> dict:
    """What *stem* says: the named groups of *pattern* where it matches,
    else what :func:`cms.parse_frame` reads from it."""
    match = pattern.search(stem) if pattern is not None else None
    if match is None:
        row = cms.parse_frame(stem)
        row["matched"] = pattern is None
    else:
        row = dict(stem=stem, matched=True)
        for name, text in match.groupdict().items():
            if text is not None:
                row[name] = _value(text, PATTERN_FIELDS[name])
        row.setdefault("sample", stem)
        moving = any(row.get(k) is not None for k in ("index", "elapsed_s"))
        row["kind"] = "insitu" if moving else "static"
    if kind in ("static", "insitu"):
        row["kind"] = kind
    return row


def _home_frames(
    root: Path,
    home: Path,
    options: Mapping,
    parse=None,
    columns: Optional[Mapping[str, type]] = None,
) -> pd.DataFrame:
    """The reduced frames of one product home; *parse* reads a name (by
    default :func:`parse_with` and the options), filling *columns* too
    (``{name: type}``)."""
    columns = columns or {}
    folder, det_folder, det_dir = _where(home, root)
    folders = product_folders(home)
    paths: Dict[str, Dict[str, str]] = {}
    for column, key in _COLUMNS.items():
        where = folders.get(key)
        if where is None:
            continue
        for name, path in _iter_product_files(where, SCATTERING_PRODUCTS[key]["patterns"]):
            paths.setdefault(stem_of(name), {}).setdefault(column, path)
    if parse is None:
        pattern = re.compile(options["sample_pattern"]) if options.get("sample_pattern") else None
        kind = options.get("kind", "auto")

        def parse(stem):
            return parse_with(stem, pattern, kind)

    rows = []
    for stem, products in paths.items():
        if not any(products.get(c) for c in _REDUCED + ("qc",)):
            continue
        row = parse(stem)
        row.pop("matched", None)
        row.update({c: products.get(c) for c in _COLUMNS})
        row["stem"] = stem
        row["stitched"] = bool(products.get("raw")) and "stitched" in str(products["raw"]).lower()
        rows.append(row)
    keep = [c for c in cms.FRAME_COLUMNS if c not in ("folder", "det_folder", "det")]
    frame = pd.DataFrame(rows, columns=keep + list(columns))
    numeric = [c for c, t in {**PATTERN_FIELDS, **columns}.items() if t is not str]
    text = [c for c, t in columns.items() if t is str]
    frame = frame.astype({**{c: float for c in numeric}, **{c: object for c in text}})
    frame.insert(0, "det", cms._detector(det_folder))
    frame.insert(0, "det_folder", det_folder)
    frame.insert(0, "folder", folder)
    return frame


def _homes(root: Path, options: Mapping) -> List[Path]:
    homes = product_homes(root)
    folders = options.get("folders")
    if folders:
        homes = [h for h in homes if _where(h, root)[0] in folders]
    return homes


def _products_index(
    root: Path, options: Mapping, parse=None, columns: Optional[Mapping[str, type]] = None
) -> pd.DataFrame:
    homes = _homes(root, options)
    parts = [_home_frames(root, h, options, parse, columns) for h in homes]
    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.DataFrame(columns=list(cms.FRAME_COLUMNS) + list(columns or {}))
    return cms.sort_frames(pd.concat(parts, ignore_index=True))


def _products_progress(root: Path, options: Mapping) -> pd.DataFrame:
    rows = []
    for home in _homes(root, options):
        folder, det_folder, det_dir = _where(home, root)
        found = product_folders(home)
        stems = {}
        for column, key in _COLUMNS.items():
            stems[column] = {stem_of(n) for n in cms._names(found[key])} if key in found else set()
        raw = [n for n in cms._names(det_dir / "raw") if re.search(r"\.tiff?$", n, re.I)]
        source = stems["raw"] or {stem_of(n) for n in raw}
        rows.append(
            dict(
                folder=folder,
                det_folder=det_folder,
                raw=len(raw),
                stitched=len(stems["raw"]),
                cir=len(stems["cir"]),
                qimg=len(stems["qimg"]),
                qphi=len(stems["qphi"]),
                qc=len(stems["qc"]),
                to_reduce=len(source - stems["cir"]),
                raw_changed=cms._mtime(det_dir / "raw"),
                reduced_changed=cms._mtime(found["cir_avg"]) if "cir_avg" in found else None,
            )
        )
    columns = [
        "folder",
        "det_folder",
        "raw",
        "stitched",
        *cms.PRODUCTS,
        "to_reduce",
        "raw_changed",
        "reduced_changed",
    ]
    return pd.DataFrame(rows, columns=columns)


# ---------------------------------------------------------------------------
# smi
# ---------------------------------------------------------------------------


def _smi_parse(stem: str) -> dict:
    """An SMI name, or — for one that is not — what a CMS name would say."""
    row = smi.parse_frame(stem)
    return row if row is not None else parse_with(stem, None)


def _smi_detect(root: Path) -> bool:
    """Product folders, the first names of one of them SMI frame names
    (``Mask/Stitch_Image`` holds the calibrant's check, named otherwise)."""
    for home in product_homes(root, depth=2)[:8]:
        for where in product_folders(home).values():
            names = sorted(cms._names(where))[:5]
            if any(smi.parse_frame(stem_of(n)) for n in names):
                return True
    return False


def _smi_index(root: Path, options: Mapping) -> pd.DataFrame:
    frames = _products_index(root, options, _smi_parse, smi.COLUMNS)
    frames["stitched"] = frames["arc_tag"].fillna("").str.upper().str.startswith("STITCH")
    return smi.with_raw(frames, smi.raw_frames(smi.project_dir(root)))


def _smi_progress(root: Path, options: Mapping) -> pd.DataFrame:
    """As for product folders, with the raw frames of ``user_data/``: each
    folder's raw frames, and its spots not reduced yet."""
    table = _products_progress(root, options)
    table = table[table["det_folder"].str.lower() != "mask"].reset_index(drop=True)
    project = smi.project_dir(root)
    if table.empty or project is None:
        return table
    frames, raw = _smi_index(root, options), smi.raw_frames(project)
    for i, row in table.iterrows():
        part = frames[
            (frames["folder"] == row["folder"]) & (frames["det_folder"] == row["det_folder"])
        ]
        mine = smi.raw_of(row["det_folder"], part, raw)
        table.at[i, "raw"] = len(mine)
        table.at[i, "to_reduce"] = smi.to_reduce(row["det_folder"], part, raw)
        if not mine.empty:
            table.at[i, "raw_changed"] = cms._mtime(Path(mine["path"].iloc[0]).parent)
    return table


def _smi_describe(root: Path, options: Mapping, frames=None, base=None) -> dict:
    return smi.describe(root, frames, base=base)


register_layout(
    Layout(
        key="smi",
        label="SMI project",
        description="an SMI project's Results/ (giwaxs, gisaxs, tsaxs … with cir_avg, "
        "q_image, qphi, qc); names read for group, sample, angle, spot, energy, arc, "
        "distance and scan — the group being the name's first field — and the raw "
        "frames of user_data/ and the reduction's configs kept with the org",
        detect=_smi_detect,
        index=_smi_index,
        progress=_smi_progress,
        options={"folders": "only these folders (as the Folder column shows them)"},
        describe=_smi_describe,
    )
)


register_layout(
    Layout(
        key="products",
        label="Product folders",
        description="any folder with the reduction's product folders (cir_avg, q_image, qphi, "
        "qc, stitched; SMI's Cir_Avg, Stitch_Data …) at or below it — the folder "
        "above each is its detector; names read by a regular expression",
        detect=lambda root: bool(product_homes(root, depth=2)),
        index=_products_index,
        progress=_products_progress,
        options={
            "sample_pattern": "a Python regular expression searched in each frame's name; its "
            "named groups fill the columns — (?P<sample>…) is required, and "
            f"may be joined by {', '.join(k for k in PATTERN_FIELDS if k != 'sample')}"
            ". Names it does not match are read as CMS names",
            "kind": "static (spots and angles), insitu (a run in time) or auto: insitu "
            "where the pattern finds an index or elapsed time",
            "folders": "only these folders (as the Folder column shows them)",
        },
    )
)


# ---------------------------------------------------------------------------
# A folder, for a reader (an AI model, a person)
# ---------------------------------------------------------------------------


def describe_tree(root, *, depth: int = 5, examples: int = 4, max_lines: int = 300) -> str:
    """The folders under *root*, how many files each holds, and a few of
    their names — what a model is shown to propose a layout. Names only."""
    root = Path(root)
    lines: List[str] = [f"{root.name}/"]

    def walk(folder: Path, level: int) -> None:
        if len(lines) >= max_lines:
            return
        try:
            with os.scandir(folder) as entries:
                items = [(e.name, e.is_dir()) for e in entries if not e.name.startswith(".")]
        except OSError:
            return
        dirs = sorted(n for n, is_dir in items if is_dir)
        files = sorted(n for n, is_dir in items if not is_dir)
        pad = "  " * level
        if files:
            shown = files if len(files) <= examples else files[: examples - 1] + ["…"] + files[-1:]
            lines.append(f"{pad}[{len(files)} files] " + " | ".join(shown))
        for name in dirs:
            if len(lines) >= max_lines:
                lines.append(f"{pad}… (more left out)")
                return
            lines.append(f"{pad}{name}/")
            if level < depth:
                walk(folder / name, level + 1)

    walk(root, 1)
    return "\n".join(lines[:max_lines])


__all__ = [
    "Layout",
    "LAYOUTS",
    "PATTERN_FIELDS",
    "KINDS",
    "register_layout",
    "get_layout",
    "detect_layout",
    "check_options",
    "index",
    "progress",
    "product_homes",
    "parse_with",
    "describe_tree",
]
