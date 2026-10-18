"""What the Org pages share: the open data folder, its org, its products.

The open *source* is a data folder read by a layout
(:mod:`pyscattviz.org.layouts`); what it holds is re-read every
:data:`REFRESH_S` seconds, so a run still being measured shows its new
frames. When pyDataOrg is installed the source usually comes from an org
(:mod:`pyscattviz.org.store`), and new frames are linked into it as they
come (:func:`sync_org`); without pyDataOrg a folder can be looked at all the
same — there is just no org to keep.

Products are read with pyScattViz's loaders, cached per file.

Widget keys of the Org pages start ``svorg_``.
"""

from __future__ import annotations

import functools
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import streamlit as st

from pyscattviz.app.components import scattering as sv
from pyscattviz.app.state import action_key
from pyscattviz.org import cms, layouts, store

# pyScattViz's reader without Streamlit's cache: it runs in worker threads.
_load_cir = getattr(sv.load_cir, "__wrapped__", sv.load_cir)

SOURCE = "svorg_source"  # {"layout", "root", "options"} of the open folder
ORG = "svorg_org"  # the open org (a pyDataOrg Organizer), or absent
LINKED = "svorg_linked"  # {(folder, sample): frames linked} in the org
AUTO_OPENED = "svorg_auto_opened"
#: Pages re-read the folder listings after this long, so new frames appear.
REFRESH_S = 15
ORG_PAGE = "pages/14_Org.py"


# ---------------------------------------------------------------------------
# The open folder
# ---------------------------------------------------------------------------


def _options(text: str) -> dict:
    return json.loads(text) if text else {}


@st.cache_data(ttl=REFRESH_S, show_spinner=False)
def _index(root: str, layout: str, options: str) -> pd.DataFrame:
    return layouts.index(root, layout, _options(options))


@st.cache_data(ttl=REFRESH_S, show_spinner=False)
def _progress(root: str, layout: str, options: str) -> pd.DataFrame:
    return layouts.progress(root, layout, _options(options))


@st.cache_data(ttl=REFRESH_S, show_spinner=False)
def _samples(root: str, layout: str, options: str) -> pd.DataFrame:
    return cms.sample_table(_index(root, layout, options))


def read(folder, layout: str, options=None) -> pd.DataFrame:
    """Every reduced frame of *folder* read by *layout* (kept a while: a
    preview, then the open folder, read once)."""
    return _index(str(folder), layout, json.dumps(dict(options or {}), sort_keys=True))


def source() -> Optional[dict]:
    """``{"layout", "root", "options"}`` of the open folder, or None."""
    return st.session_state.get(SOURCE)


def _key() -> Optional[Tuple[str, str, str]]:
    found = source()
    if not found:
        return None
    return found["root"], found["layout"], json.dumps(dict(found["options"]), sort_keys=True)


def root() -> Optional[Path]:
    """The open data folder, or None."""
    found = source()
    return Path(found["root"]) if found else None


def title() -> str:
    found = org()
    if found is not None and found.project.config.name:
        return found.project.config.name
    return store.title(root()) if root() is not None else ""


def frames() -> pd.DataFrame:
    """Every reduced frame of the open folder (:data:`cms.FRAME_COLUMNS`)."""
    key = _key()
    if key is None:
        return pd.DataFrame(columns=list(cms.FRAME_COLUMNS))
    return _index(*key)


def samples() -> pd.DataFrame:
    """One row per sample of the open folder (:func:`cms.sample_table`)."""
    key = _key()
    if key is None:
        return cms.sample_table(frames())
    return _samples(*key)


def progress() -> pd.DataFrame:
    """Raw against reduced per folder and detector (empty if the layout
    cannot tell)."""
    key = _key()
    return pd.DataFrame() if key is None else _progress(*key)


def rescan() -> None:
    """Read the folders again now, rather than at the next refresh."""
    _index.clear()
    _progress.clear()
    _samples.clear()


def open_folder(path, layout: Optional[str] = None, options=None) -> None:
    """Look at the data folder *path* (no org): read by *layout*, the one
    that recognises it by default."""
    path = Path(path).expanduser().resolve()
    layout = layout or layouts.detect_layout(path)
    if layout is None:
        raise ValueError(f"no layout recognises {shown(path)}: choose one on Org")
    st.session_state[SOURCE] = {
        "layout": layout,
        "root": str(path),
        "options": layouts.check_options(layout, options),
    }
    st.session_state.pop(ORG, None)
    st.session_state[LINKED] = {}
    rescan()


def org():
    """The open org, or None."""
    return st.session_state.get(ORG)


def _attach(found) -> object:
    """Make *found* the session's org, and its data folder the open one."""
    src = store.source_of(found)
    where = store.data_root(found)
    if src is None or where is None:
        raise ValueError(
            f"{shown(found.path)} records no data folder: it was not made by pyScattViz"
        )
    st.session_state[SOURCE] = {
        "layout": src.layout,
        "root": str(where),
        "options": dict(src.options),
    }
    st.session_state[ORG] = found
    st.session_state[LINKED] = {}
    rescan()
    if where.is_dir():
        sync_org()
    return found


def open_org(path) -> object:
    """Open the org kept at *path*; the frames written since it was saved
    are linked in (not saved)."""
    return _attach(store.open_org(path, refresh=False))


def create_org(
    path, folder, layout: Optional[str] = None, options=None, name: str = "", description: str = ""
) -> object:
    """Make an org of *folder*, keep it at *path* (saved), and open it."""
    found = store.create_org(
        path, folder, layout=layout, options=options, name=name, description=description
    )
    st.session_state[LINKED] = {}
    return _attach(found)


def _counts(frames_: pd.DataFrame) -> Dict[Tuple[str, str], int]:
    if frames_.empty:
        return {}
    return {k: int(v) for k, v in frames_.groupby(["folder", "sample"]).size().items()}


def sync_org() -> int:
    """Link the frames that came since the org was last linked; returns
    how many samples were (re)linked. Not saved."""
    found = org()
    if found is None or source() is None:
        return 0
    frames_ = frames()
    counts = _counts(frames_)
    linked = st.session_state.setdefault(LINKED, {})
    changed = [key for key, n in counts.items() if linked.get(key) != n]
    if not changed:
        return 0
    keys = pd.MultiIndex.from_tuples(changed)
    part = frames_[pd.MultiIndex.from_frame(frames_[["folder", "sample"]]).isin(keys)]
    cms.build_organizer(part, None, organizer=found)
    linked.update({key: counts[key] for key in changed})
    return len(changed)


def require_source() -> Path:
    """The open data folder, or a pointer to the Org page and a stop."""
    found = root()
    if found is None:
        st.info(
            "No data folder is open. Open an org — or make one — on **Org**.",
            icon=":material/folder_open:",
        )
        page_link(ORG_PAGE, "Open or make an org", ":material/folder_open:")
        st.stop()
    return found


def auto_open() -> None:
    """On the first visit open ``$PYSCATTVIZ_ORG`` (``pyscattviz --org``)."""
    if st.session_state.get(AUTO_OPENED) or source() is not None:
        return
    st.session_state[AUTO_OPENED] = True
    target = os.environ.get(store.ORG_ENV, "").strip()
    if not target or not store.has_pydataorg():
        return
    target = Path(target).expanduser()
    if target.is_dir():
        found = store.orgs_in(target)
        target = found[0] if len(found) == 1 else target
    if target.is_file():
        try:
            open_org(target)
        except (OSError, ValueError) as exc:
            st.warning(f"Could not open the org {shown(target)}: {exc}")


def sidebar() -> None:
    """The open folder, how far its reduction is, and a re-scan."""
    where = root()
    with st.sidebar:
        st.divider()
        if where is None:
            st.caption("No org open")
            return
        st.caption(f"**{title()}**" + ("" if org() is not None else " (no org)"))
        table = progress()
        if not table.empty:
            reduced, waiting = int(table["cir"].sum()), int(table["to_reduce"].sum())
            st.caption(f"{reduced} frames reduced · {waiting} still to reduce")
        if st.button(
            "↻ Re-scan the folders",
            width="stretch",
            key=action_key(st.session_state, "svorg_sidebar_rescan"),
        ):
            rescan()
            st.rerun()


def on_page() -> None:
    """What every Org page does first: open ``--org`` on the first visit,
    link new frames, the sidebar."""
    auto_open()
    sync_org()
    sidebar()


def page_link(page: str, label: str, icon: Optional[str] = None) -> None:
    """A link to another page; a plain note where there are no pages (a
    page run on its own, as in a test)."""
    try:
        st.page_link(page, label=label, icon=icon)
    except Exception:  # noqa: BLE001 - StreamlitAPIException / page not found
        st.caption(f"→ {label} ({Path(page).stem.split('_', 1)[-1].replace('_', ' ')})")


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


def load_iq(path: str) -> Tuple[np.ndarray, np.ndarray]:
    """``(q, I)`` of one ``Cir_Avg_*.csv``."""
    stat = os.stat(path)
    return _read_iq(path, stat.st_mtime_ns, stat.st_size)


@functools.lru_cache(maxsize=50_000)
def _read_iq(path: str, mtime_ns: int, size: int) -> Tuple[np.ndarray, np.ndarray]:
    # Keyed on the file's size and time too: a CSV caught half-written by
    # the reduction is read again once it is whole.
    return _load_cir(path)


def stack(paths: Sequence[str]) -> Tuple[np.ndarray, np.ndarray]:
    """I(q) of several frames on one q axis (:func:`cms.stack_iq`).

    Read 16 at a time — on NFS a file costs its latency, not its bytes —
    and kept per file, so a live run reads only its new frames."""
    paths = list(paths)
    if len(paths) > 8:
        with ThreadPoolExecutor(16) as pool:
            curves = list(pool.map(load_iq, paths))
    else:
        curves = [load_iq(p) for p in paths]
    return cms.stack_iq(curves)


def load_qimage(path: str, mode: str = "qx"):
    """``(z, x, y, mask, xlabel)`` of one ``qimg_*.npz`` — pyScattViz's view."""
    return sv.resolve_qimage(sv.load_qimg(path), mode)


def load_qphi(path: str):
    """``(q, phi, qphi[phi, q])`` of one ``qphi_*.npz``."""
    q, phi, qphi, _ = sv.load_qphi(path)
    return q, phi, qphi


def shown(path) -> str:
    """A path as the pages show it: the home folder as ``~``."""
    text = str(path)
    home = str(Path.home())
    return "~" + text[len(home) :] if text == home or text.startswith(home + os.sep) else text


__all__ = [
    "REFRESH_S",
    "ORG_PAGE",
    "read",
    "source",
    "root",
    "title",
    "frames",
    "samples",
    "progress",
    "rescan",
    "open_folder",
    "org",
    "open_org",
    "create_org",
    "sync_org",
    "require_source",
    "auto_open",
    "sidebar",
    "on_page",
    "page_link",
    "load_iq",
    "stack",
    "load_qimage",
    "load_qphi",
    "shown",
]
