"""An org: a pyDataOrg organiser of a data folder, kept as one JSON file.

::

    org = create_org("…/Org/run.json", "…/experiments/run")   # read, linked, saved
    org = open_org("…/Org/run.json")                         # new frames linked in
    source_of(org)          # Source(layout="cms", root="../experiments/run", options={})
    data_root(org)          # the data folder on this machine
    beamline(org)           # how it was measured and reduced, where the layout says

The org records where its data is — the *source*: the layout that reads the
folder (:mod:`pyscattviz.org.layouts`), the folder, the layout's options —
inside its own file, under pyScattViz's key of pyDataOrg's
``ProjectConfig.extensions``. The folder and every linked product are
recorded relative to the org's folder when they are near it
(:func:`pyscattviz.org.cms.recorded_path`), so an org kept beside the data
(``<proposal>/Org/``) opens from the beamline, an SSHFS or rclone mount, or
a RaiDrive letter alike. One kept elsewhere records absolute paths, and the
path mappings of *Data Sources & Mounts* translate them.

pyDataOrg is needed for an org (``pip install "pyScattViz[org]"``); a data
folder can be looked at without one.
"""

from __future__ import annotations

import importlib.util
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from pyscattviz.org import cms, layouts, smi

#: The org's settings for pyScattViz, in ``ProjectConfig.extensions``.
SOURCE_KEY = "pyscattviz"
#: Where an org goes when it is not kept beside its data.
ORGS_ENV = "PYSCATTVIZ_ORGS"
#: An org to open on the first visit (``pyscattviz --org PATH``).
ORG_ENV = "PYSCATTVIZ_ORG"
#: The folder next to ``experiments/`` an org of an experiment is kept in
#: (in an SMI project, next to ``Results/``).
ORG_FOLDER = "Org"
RECENT_NAME = "recent_orgs.json"
MAX_RECENT = 12
INSTALL_HINT = (
    'pip install "pyScattViz[org]"   # or: pip install '
    '"pyDataOrg @ git+https://github.com/yugangzhang/pyDataOrg.git"'
)


def has_pydataorg() -> bool:
    """Whether pyDataOrg can be imported here."""
    return importlib.util.find_spec("pyDataOrg") is not None


def config_dir() -> Path:
    from pyscattviz.datasets import config_dir as _config_dir

    return _config_dir()


def orgs_dir() -> Path:
    """Where an org is kept when not beside its data."""
    text = os.environ.get(ORGS_ENV, "").strip()
    return Path(text).expanduser() if text else config_dir() / "orgs"


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------


def _experiment_parts(root) -> Optional[tuple]:
    """``(cycle, proposal, name, home)`` of a CMS experiment,
    ``…/<cycle>/<proposal>/experiments/<name>``, or of a folder of an SMI
    project, ``…/<cycle>/<proposal>/projects/<project>[/Results[/<sub>…]]``
    (named ``<project>[_<sub>…]``); *home* is the folder its ``Org/`` goes
    in — the proposal's, the project's."""
    root = Path(root)
    parts = root.parts
    if len(parts) >= 4 and parts[-2] == "experiments":
        return parts[-4], parts[-3], parts[-1], root.parent.parent
    found = smi.project_parts(root)
    if found:
        cycle, proposal, project, below = found
        home = root.parents[len(below) - 1] if below else root
        below = below[1:] if below[:1] == ("Results",) else below
        return cycle, proposal, "_".join([project, *below]), home
    return None


def title(root) -> str:
    """``run · 2026-3 · pass-123456`` for an experiment of a proposal (or an
    SMI project); the folder's name for anything else."""
    found = _experiment_parts(root)
    if found:
        cycle, proposal, name, _ = found
        return f"{name} · {cycle} · {proposal}"
    return Path(root).name


def tag(root) -> str:
    """A file name for an org of *root* (``2026-3_pass-123456_run``)."""
    found = _experiment_parts(root)
    if found:
        cycle, proposal, name, _ = found
        return f"{cycle}_{proposal}_{name}"
    return Path(root).name or "org"


def experiments_in(folder) -> List[Path]:
    """The experiments a layout can read in a proposal folder
    (``<proposal>/experiments/<name>``) or in its ``experiments/``, by name;
    the ``Org`` folder an org is kept in is not one."""
    folder = Path(folder)
    home = folder if folder.name == "experiments" else folder / "experiments"
    try:
        found = sorted(p for p in home.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError:
        return []
    return [p for p in found if p.name != ORG_FOLDER and layouts.detect_layout(p) is not None]


def suggest_store(root) -> Path:
    """Where an org of *root* is kept by default, beside the data:
    ``<proposal>/Org/<name>.json`` for an experiment of a proposal,
    ``<proposal>/projects/<project>/Org/<name>.json`` for an SMI project;
    else in :func:`orgs_dir`."""
    found = _experiment_parts(root)
    if found:
        return found[3] / ORG_FOLDER / f"{found[2]}.json"
    return orgs_dir() / f"{tag(root)}.json"


# ---------------------------------------------------------------------------
# The source
# ---------------------------------------------------------------------------


@dataclass
class Source:
    """Where an org's frames come from: a folder read by a layout."""

    layout: str
    root: str
    options: Dict = field(default_factory=dict)

    def path(self, base=None) -> Path:
        """The folder on this machine; a relative one is relative to *base*
        (the org's folder)."""
        root = Path(self.root).expanduser()
        if not root.is_absolute() and base is not None:
            root = Path(os.path.normpath(Path(base) / root))
        return root

    def to_dict(self) -> dict:
        return {"layout": self.layout, "root": self.root, "options": dict(self.options)}

    @classmethod
    def from_dict(cls, data) -> "Source":
        return cls(
            layout=str(data.get("layout", "")),
            root=str(data.get("root", "")),
            options=dict(data.get("options") or {}),
        )


def source_of(org) -> Optional[Source]:
    """The source an org records, or None (an org pyScattViz did not make)."""
    found = org.project.config.extensions.get(SOURCE_KEY, {}).get("source")
    return Source.from_dict(found) if found else None


def set_source(org, source: Source) -> None:
    settings = dict(org.project.config.extensions.get(SOURCE_KEY) or {})
    settings["source"] = source.to_dict()
    org.project.config.extensions[SOURCE_KEY] = settings


def data_root(org) -> Optional[Path]:
    """The org's data folder on this machine, or None. A recorded absolute
    path not found here is translated through the path mappings."""
    source = source_of(org)
    if source is None:
        return None
    root = source.path(Path(org.path).parent)
    if not root.is_dir():
        local = Path(org.local(str(root))) if hasattr(org, "local") else root
        if local.is_dir():
            return local
        translated = _translate(str(root))
        if translated is not None:
            return translated
    return root


def _translate(path: str) -> Optional[Path]:
    from pyscattviz.data_sources import load_path_mappings, translate_remote_path

    local, mapping = translate_remote_path(path, load_path_mappings())
    return Path(local) if mapping is not None and Path(local).is_dir() else None


def aliases() -> Dict[str, List[str]]:
    """The path mappings of *Data Sources & Mounts*, as pyDataOrg aliases:
    a recorded path under a remote root is found under its local folder."""
    from pyscattviz.data_sources import load_path_mappings

    return {m["remote_root"]: [m["local_root"]] for m in load_path_mappings()}


# ---------------------------------------------------------------------------
# Making and opening
# ---------------------------------------------------------------------------


def _organizer(store, name: str = ""):
    if not has_pydataorg():
        raise ModuleNotFoundError(f"An org needs pyDataOrg: {INSTALL_HINT}")
    from pyDataOrg import Organizer

    return Organizer(store, name=name, aliases=aliases())


def frames_of(source: Source, base=None) -> pd.DataFrame:
    """Every reduced frame of *source* (``layouts.index``)."""
    return layouts.index(source.path(base), source.layout, source.options)


def link(org, frames: Optional[pd.DataFrame] = None):
    """Link *frames* (default: every frame of the org's source, read now)
    into *org*, and re-read how it was measured (:func:`describe`);
    earlier links of the same samples are replaced. Not saved."""
    if frames is None:
        root = data_root(org)
        source = source_of(org)
        if source is None or root is None:
            raise ValueError("this org records no data folder")
        frames = layouts.index(root, source.layout, source.options)
    cms.build_organizer(frames, None, organizer=org)
    describe(org, frames)
    return org


def beamline(org) -> dict:
    """What *org* keeps about how its data were measured and reduced — for
    an SMI project the beamline, the raw folders, the acquisition's strategy
    and the reduction's configs (:func:`pyscattviz.org.smi.describe`); empty
    where its layout says nothing."""
    return dict(org.project.config.extensions.get(SOURCE_KEY, {}).get("beamline") or {})


def describe(org, frames: Optional[pd.DataFrame] = None) -> dict:
    """Re-read how *org*'s data were measured and reduced, as its layout
    says, and keep it in the org (not saved); returns it. *frames* are the
    org's frames, when they are at hand."""
    source, root = source_of(org), data_root(org)
    layout = layouts.LAYOUTS.get(source.layout) if source is not None else None
    if layout is None or layout.describe is None or root is None or not root.is_dir():
        return beamline(org)
    found = layout.describe(root, source.options, frames, Path(org.path).parent.resolve())
    settings = dict(org.project.config.extensions.get(SOURCE_KEY) or {})
    settings["beamline"] = found
    org.project.config.extensions[SOURCE_KEY] = settings
    return found


def create_org(
    store,
    root,
    *,
    layout: Optional[str] = None,
    options=None,
    name: str = "",
    description: str = "",
    save: bool = True,
):
    """Make an org of the data folder *root*, kept at *store* (a ``.json``).

    *layout* defaults to the one that recognises the folder
    (:func:`layouts.detect_layout`); *options* are that layout's. Every
    reduced frame is linked; the org is saved unless *save* is False.
    """
    root = Path(root).expanduser().resolve()
    layout = layout or layouts.detect_layout(root)
    if layout is None:
        raise ValueError(f"no layout recognises {root}: choose one, with its options")
    options = layouts.check_options(layout, options)
    store = Path(store).expanduser()
    if store.suffix.lower() != ".json":
        store = store / f"{tag(root)}.json"
    org = _organizer(store, name=name or title(root))
    if description:
        org.project.config.description = description
    base = Path(org.path).parent.resolve()
    set_source(org, Source(layout, cms.recorded_path(root, base), options))
    link(org, layouts.index(root, layout, options))
    if save:
        org.save()
        remember(org.path)
    return org


def open_org(store, *, refresh: bool = True):
    """Open the org at *store*; with *refresh*, the frames written since it
    was saved are linked in (not saved)."""
    store = Path(store).expanduser()
    if not store.is_file():
        raise FileNotFoundError(f"no org at {store}")
    org = _organizer(store)
    if (
        refresh
        and source_of(org) is not None
        and data_root(org) is not None
        and data_root(org).is_dir()
    ):
        link(org)
    remember(org.path)
    return org


def linked_frames(org) -> int:
    """How many reduced frames *org* links: its I(q) files."""
    return sum(
        len(m.paths)
        for sample in org.project.samples.values()
        for m in sample.measurements
        if m.modality == "iq"
    )


# ---------------------------------------------------------------------------
# Orgs opened before
# ---------------------------------------------------------------------------


def _recent_file() -> Path:
    return config_dir() / RECENT_NAME


def recent() -> List[str]:
    """Orgs opened here before, newest first, those still there."""
    try:
        found = json.loads(_recent_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [p for p in found if isinstance(p, str) and Path(p).is_file()][:MAX_RECENT]


def remember(store) -> None:
    """Put *store* first among :func:`recent`; quietly does nothing where the
    settings folder cannot be written."""
    text = str(Path(store).expanduser().resolve())
    found = [text] + [p for p in recent() if p != text]
    try:
        _recent_file().parent.mkdir(parents=True, exist_ok=True)
        _recent_file().write_text(json.dumps(found[:MAX_RECENT], indent=1) + "\n", encoding="utf-8")
    except OSError:
        pass


def is_org_file(path) -> bool:
    """Whether *path* is a saved organiser (a JSON with ``project`` and
    ``samples``) — read only as far as its first bytes need."""
    path = Path(path)
    if path.suffix.lower() != ".json" or not path.is_file():
        return False
    try:
        with path.open(encoding="utf-8") as handle:
            head = handle.read(4096)
    except OSError:
        return False
    return '"project"' in head


def orgs_in(folder) -> List[Path]:
    """The orgs in *folder*, by name."""
    try:
        return sorted(p for p in Path(folder).glob("*.json") if is_org_file(p))
    except OSError:
        return []


__all__ = [
    "SOURCE_KEY",
    "ORGS_ENV",
    "ORG_ENV",
    "ORG_FOLDER",
    "INSTALL_HINT",
    "Source",
    "has_pydataorg",
    "orgs_dir",
    "title",
    "tag",
    "experiments_in",
    "suggest_store",
    "source_of",
    "set_source",
    "data_root",
    "aliases",
    "frames_of",
    "link",
    "create_org",
    "open_org",
    "linked_frames",
    "recent",
    "remember",
    "is_org_file",
    "orgs_in",
]
