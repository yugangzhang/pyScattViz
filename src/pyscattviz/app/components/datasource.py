"""Choosing a data folder, and narrowing a frame list, on every page.

Two jobs that every explorer needs and that used to be done badly:

**Picking the folder.** A collaborator normally mounts one drive holding many
proposals, several beamlines, and dozens of projects. The old sidebar had a
single text box seeded from the active folder, with no key: paste a path that
was not yet available and the box cleared itself on the next rerun, so the path
could never be corrected. It also never translated an original ``/nsls2/...``
path through the registered mounts, so pasting the path from a beamline email
simply failed. :func:`render_folder_picker` fixes both and offers every folder
the session already knows about.

**Narrowing the frames.** The old keyword box ANDed its terms, so there was no
way to ask for *UV_20 or UV_30*. :func:`render_term_filters` gives the same
must-contain / may-contain / must-not-contain lists used on Data Selection and
Quick Plot.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from pyscattviz.app.state import action_key, prepare_persistent_widget, store_persistent_widget
from pyscattviz.data_sources import load_path_mappings, translate_remote_path
from pyscattviz.discovery import matches_terms, parse_terms
from pyscattviz.folders import (
    folders_file,
    forget_folder,
    load_folder_entries,
    normalize,
    save_folder_entries,
    set_note,
    set_pinned,
)
from pyscattviz.folders import remember_folder as remember_in_file

__all__ = [
    "ensure_remembered_folders",
    "render_folder_memory",
    "known_folders",
    "remember_folder",
    "render_folder_picker",
    "render_term_filters",
]

ACTIVE_KEY = "pyscattviz_active_root"
RECENT_KEY = "pyscattviz_recent_roots"
ENTRIES_KEY = "pyscattviz_folder_entries"
LOADED_KEY = "pyscattviz_folder_entries_loaded"
PASTE_PROMPT = "— paste a path below —"
MAX_RECENT = 12


def ensure_remembered_folders(session_state=None) -> list:
    """Load the remembered folders from disk once per session, and seed the box.

    Called at the top of every page that cares about the current folder. The
    first call reads ``data_folders.md`` and, if nothing has chosen a folder
    yet, opens on the one used last — which is the whole point of writing the
    file. Later calls in the same session are free.
    """

    state = session_state if session_state is not None else st.session_state
    if state.get(LOADED_KEY):
        return state.get(ENTRIES_KEY, [])

    entries = load_folder_entries()
    state[ENTRIES_KEY] = entries
    state[LOADED_KEY] = True

    # Seed the recent list so the menu is populated before anything is opened.
    remembered = [item.path for item in entries]
    known = list(state.get(RECENT_KEY, []))
    state[RECENT_KEY] = known + [item for item in remembered if item not in known]

    if not state.get(ACTIVE_KEY):
        for entry in entries:
            if entry.exists:
                state[ACTIVE_KEY] = entry.path
                break
    return entries


def known_folders() -> list[str]:
    """Every folder this session knows about, most useful first.

    Recently used folders come first, then the registered roots, the mount
    points, and finally the folders in the dataset basket. Only folders that are
    actually available right now are offered; a disconnected mount is no use as
    a menu entry.
    """

    ensure_remembered_folders()
    mappings = st.session_state.get("pyscattviz_path_mappings") or []
    candidates: list[str] = []
    groups = (
        st.session_state.get(RECENT_KEY, []),
        [st.session_state.get(ACTIVE_KEY, "")],
        st.session_state.get("pyscattviz_roots", []),
        [item.get("local_root", "") for item in mappings],
        st.session_state.get("pyscattviz_dataset_paths", []),
    )
    for group in groups:
        for value in group:
            if not value:
                continue
            text = str(value)
            if text in candidates:
                continue
            try:
                if Path(text).expanduser().is_dir():
                    candidates.append(text)
            except OSError:
                continue
    return candidates


def remember_folder(folder: str, note: str | None = None) -> None:
    """Push a folder to the front of the recently-used list, and write it down.

    The session copy is what the menu is built from; the markdown file is what
    survives closing the browser. Writing is skipped when nothing changed, so
    calling this on every rerun costs nothing.
    """

    recent = [item for item in st.session_state.get(RECENT_KEY, []) if item != folder]
    recent.insert(0, folder)
    st.session_state[RECENT_KEY] = recent[:MAX_RECENT]

    entries = remember_in_file(folder, note=note, entries=st.session_state.get(ENTRIES_KEY))
    st.session_state[ENTRIES_KEY] = entries
    save_folder_entries(entries)


def _folder_label(value: str) -> str:
    """Show enough of a long mounted path to tell two projects apart."""

    if value == PASTE_PROMPT:
        return value
    parts = Path(value).parts
    return "…/" + "/".join(parts[-3:]) if len(parts) > 3 else value


def render_folder_picker(
    state_prefix: str,
    label: str,
    help_text: str = "",
    container=None,
) -> str:
    """Render the folder chooser and return the resolved local folder.

    Returns an empty string when nothing usable has been chosen yet. The caller
    decides what to do about that; this function only reports, it never stops
    the script.
    """

    host = container if container is not None else st
    ensure_remembered_folders()
    st.session_state.setdefault("pyscattviz_path_mappings", load_path_mappings())
    mappings = st.session_state["pyscattviz_path_mappings"]

    path_state = f"{state_prefix}_folder_text"
    folders = known_folders()
    if folders:
        choice = host.selectbox(
            f"Known folders ({len(folders)})",
            [PASTE_PROMPT, *folders],
            format_func=_folder_label,
            key=f"{state_prefix}_folder_pick",
            help=(
                "Registered mounts, the dataset basket, and every folder you "
                "have opened before — kept in data_folders.md between sessions."
            ),
        )
        if choice != PASTE_PROMPT and choice != st.session_state.get(path_state):
            st.session_state[path_state] = choice
            st.session_state.pop(f"_{path_state}", None)
            st.session_state[ACTIVE_KEY] = choice
            remember_folder(choice)
            st.rerun()

    widget_key = prepare_persistent_widget(
        st.session_state, path_state, str(st.session_state.get(ACTIVE_KEY, ""))
    )
    typed = host.text_input(
        label,
        key=widget_key,
        on_change=store_persistent_widget,
        args=(st.session_state, path_state),
        help=help_text or "Type or paste any folder on this computer, or a mounted path.",
    )

    if not typed.strip():
        return ""

    # An original /nsls2 path is what people copy out of an email; translate it
    # through the registered mounts rather than rejecting it.
    translated, mapping = translate_remote_path(typed.strip(), mappings)
    resolved = Path(translated).expanduser()
    if resolved.is_dir():
        folder = str(resolved)
        if mapping:
            host.caption(f"Mapped through `{mapping['remote_root']}`.")
        st.session_state[ACTIVE_KEY] = folder
        # Remember it every time, not only when it changes: a folder arrived at
        # some other way — a handoff from Data Selection, say — would otherwise
        # never reach the menu, and would drop out of it as soon as the user
        # moved somewhere else.
        remember_folder(folder)
        render_folder_memory(state_prefix, folder, container=host)
        return folder

    # Report the problem but keep what was typed, so it can be corrected.
    if typed.strip().startswith("/nsls2/"):
        host.warning(
            "This `/nsls2` path is not mounted on this computer. Open Data Sources & "
            "Mounts, complete the mount, and register it — then this path will work "
            "as typed."
        )
    else:
        host.warning(f"`{typed.strip()}` is not a folder on this computer.")
    return ""


def _apply_entries(entries) -> None:
    """Put a changed folder list into session state and onto disk together."""

    st.session_state[ENTRIES_KEY] = entries
    st.session_state[RECENT_KEY] = [item.path for item in entries]
    save_folder_entries(entries)


def render_folder_memory(state_prefix: str, folder: str, container=None) -> None:
    """Let the current folder be labelled, pinned, or forgotten.

    A path like ``.../2026-2/pass-xxxxxx/experiments/0_Static/maxs/analysis``
    tells you nothing at a glance three weeks later, so the note is the part
    that makes the remembered list worth keeping. Pinning holds a folder at the
    top for a beamtime you keep coming back to.
    """

    host = container if container is not None else st
    entries = ensure_remembered_folders()
    current = next((item for item in entries if item.path == normalize(folder)), None)

    with host.expander("📁 Remembered folders", expanded=False):
        st.caption(
            "Kept in the file below between sessions — on this computer only, "
            "never inside a repository. Edit it by hand if you prefer."
        )
        st.code(str(folders_file()), language=None)

        note_key = f"{state_prefix}_folder_note"
        st.session_state.setdefault(note_key, current.note if current else "")
        note = st.text_input(
            "Note for this folder",
            key=note_key,
            placeholder="CMS GIWAXS, PVDF on MXene",
            help="Shown beside the path in data_folders.md.",
        )
        if current is not None and note.strip() != current.note:
            _apply_entries(set_note(folder, note, entries=entries))

        buttons = st.columns(2)
        pinned = bool(current.pinned) if current else False
        if buttons[0].button(
            "Unpin" if pinned else "📌 Pin this folder",
            key=action_key(st.session_state, f"{state_prefix}_folder_pin"),
            use_container_width=True,
            help="Pinned folders are offered first and are never aged out.",
        ):
            _apply_entries(set_pinned(folder, not pinned, entries=entries))
            st.rerun()
        if buttons[1].button(
            "Forget this folder",
            key=action_key(st.session_state, f"{state_prefix}_folder_forget"),
            use_container_width=True,
        ):
            _apply_entries(forget_folder(folder, entries=entries))
            st.rerun()

        if entries:
            st.caption(f"{len(entries)} folder(s) remembered")
            listed = [
                f"{'📌' if item.pinned else '  '} {item.path}"
                + (f"  — {item.note}" if item.note else "")
                + ("" if item.exists else "   (not mounted)")
                for item in entries[:10]
            ]
            st.code("\n".join(listed), language=None)


def render_term_filters(
    state_prefix: str,
    container=None,
    help_and: str = "Every term must appear.",
    help_or: str = "At least one term must appear.",
    help_not: str = "Drop anything matching one of these.",
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Render must-contain / may-contain / must-not-contain boxes.

    Returns the three parsed term tuples, ready for
    :func:`pyscattviz.discovery.matches_terms`.
    """

    host = container if container is not None else st
    and_text = host.text_input(
        "Must contain (AND)",
        key=f"{state_prefix}_kw_and",
        placeholder="UV",
        help=help_and,
    )
    or_text = host.text_input(
        "May contain (OR)",
        key=f"{state_prefix}_kw_or",
        placeholder="UV_20, UV_30",
        help=help_or + " This is how you ask for two samples at once.",
    )
    not_text = host.text_input(
        "Must not contain (EXCLUDE)",
        key=f"{state_prefix}_kw_not",
        placeholder="AgBH, test",
        help=help_not,
    )
    return parse_terms(and_text), parse_terms(or_text), parse_terms(not_text)


def apply_term_filters(frame_table, and_list, or_list, no_list, column: str = "stem"):
    """Keep the rows of a frame table whose ``column`` passes the term lists."""

    if not (and_list or or_list or no_list):
        return frame_table
    keep = frame_table[column].map(
        lambda value: matches_terms(str(value), and_list, or_list, no_list)
    )
    return frame_table[keep]
