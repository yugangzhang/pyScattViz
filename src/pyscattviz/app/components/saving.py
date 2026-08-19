"""One shared save-to-disk panel used by every page that draws something.

pyScattViz runs on the user's own computer, so I would rather write a figure
straight into a folder the user names than make them hunt through the browser's
download directory. The panel below does that, and it puts each page's output in
its own subfolder — a figure saved from the GIWAXS Explorer lands in
``<output root>/GIWAXS_Explorer/`` — so a long session stays sorted by itself.

Every page calls :func:`render_save_panel` with its own tab name and a unique
``key``. The output root and the subfolder preferences are shared, remembered
between pages, and written to ``~/.pyscattviz/settings.json``.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from pyscattviz.app.state import action_key, coerce_choice
from pyscattviz.exporting import (
    ARRAY_FORMATS,
    MATPLOTLIB_FORMATS,
    PLOTLY_FORMATS,
    TABLE_FORMATS,
    ExportError,
    default_output_root,
    load_settings,
    resolve_output_dir,
    safe_component,
    save_arrays,
    save_matplotlib_figure,
    save_plotly_figure,
    save_settings,
    save_table,
    save_text,
)

ROOT_KEY = "pyscattviz_output_root"
SUBFOLDER_KEY = "pyscattviz_output_subfolder_per_tab"
DATE_KEY = "pyscattviz_output_date_subfolder"
OVERWRITE_KEY = "pyscattviz_output_overwrite"
HISTORY_KEY = "pyscattviz_saved_files"

_FORMATS = {
    "plotly": PLOTLY_FORMATS,
    "matplotlib": MATPLOTLIB_FORMATS,
    "table": TABLE_FORMATS,
    "arrays": ARRAY_FORMATS,
    "text": ("txt",),
}


_SETTING_KEYS = {
    ROOT_KEY: "output_root",
    SUBFOLDER_KEY: "output_subfolder_per_tab",
    DATE_KEY: "output_date_subfolder",
    OVERWRITE_KEY: "output_overwrite",
}


def ensure_output_settings() -> None:
    """Fill any missing output preference from the saved settings file.

    Each key is filled independently so a value already placed in session state
    — by another page, or by a test — is never overwritten.
    """

    missing = [key for key in _SETTING_KEYS if key not in st.session_state]
    if not missing:
        return
    settings = load_settings()
    for key in missing:
        st.session_state[key] = settings[_SETTING_KEYS[key]]


def output_root() -> str:
    """Return the folder the user has chosen for saved output."""

    ensure_output_settings()
    return str(st.session_state.get(ROOT_KEY) or default_output_root())


def set_output_root(value: str, persist: bool = True) -> None:
    """Change the output root and remember it for the next session."""

    ensure_output_settings()
    cleaned = str(value).strip() or str(default_output_root())
    st.session_state[ROOT_KEY] = cleaned
    if persist:
        try:
            save_settings({"output_root": cleaned})
        except OSError:
            pass


def target_folder(tab_name: str, *extra: str) -> Path:
    """Resolve the folder a save from ``tab_name`` would use, without creating it."""

    ensure_output_settings()
    parts = []
    if st.session_state.get(SUBFOLDER_KEY, True):
        parts.append(tab_name)
    parts.extend(extra)
    return resolve_output_dir(
        output_root(),
        *parts,
        create=False,
        date_subfolder=bool(st.session_state.get(DATE_KEY, False)),
    )


def record_saved(path: Path) -> None:
    """Remember one saved file so a page can show what it just wrote."""

    history = st.session_state.setdefault(HISTORY_KEY, [])
    entry = str(path)
    if entry in history:
        history.remove(entry)
    history.insert(0, entry)
    del history[40:]


def _root_input(host, widget_key: str, label: str, help_text: str) -> None:
    """Draw an output-root box that stays in step with every other one.

    Several boxes can be on screen at once — the sidebar plus one per save
    panel. Each keeps its own widget key and is re-seeded whenever another box
    changes the shared root, so they never fight over the value. Boxes drawn
    *earlier* in the script have already been rendered by then, so a change
    triggers one rerun and every box shows the new folder immediately.
    """

    marker_key = f"{widget_key}__seen"
    shared = output_root()
    if st.session_state.get(marker_key) != shared:
        st.session_state[widget_key] = shared
        st.session_state[marker_key] = shared
    value = host.text_input(label, key=widget_key, help=help_text)
    if value != shared:
        set_output_root(value)
        st.session_state[marker_key] = value
        st.rerun()


def render_output_settings(container=None) -> None:
    """Render the shared output-root controls, usually in a sidebar."""

    ensure_output_settings()
    host = container if container is not None else st
    _root_input(
        host,
        "pyscattviz_output_root_widget",
        "Save figures and tables to",
        "Any folder on this computer. pyScattViz creates it, and a subfolder "
        "per page, the first time something is saved.",
    )
    columns = host.columns(3)
    per_tab = columns[0].checkbox(
        "Subfolder per page",
        value=bool(st.session_state.get(SUBFOLDER_KEY, True)),
        key="pyscattviz_output_subfolder_widget",
    )
    dated = columns[1].checkbox(
        "Date subfolder",
        value=bool(st.session_state.get(DATE_KEY, False)),
        key="pyscattviz_output_date_widget",
    )
    overwrite = columns[2].checkbox(
        "Overwrite",
        value=bool(st.session_state.get(OVERWRITE_KEY, False)),
        key="pyscattviz_output_overwrite_widget",
        help="Off by default: a repeated name becomes name_001, name_002, …",
    )
    changed = (
        per_tab != st.session_state.get(SUBFOLDER_KEY)
        or dated != st.session_state.get(DATE_KEY)
        or overwrite != st.session_state.get(OVERWRITE_KEY)
    )
    st.session_state[SUBFOLDER_KEY] = per_tab
    st.session_state[DATE_KEY] = dated
    st.session_state[OVERWRITE_KEY] = overwrite
    if changed:
        try:
            save_settings(
                {
                    "output_subfolder_per_tab": per_tab,
                    "output_date_subfolder": dated,
                    "output_overwrite": overwrite,
                }
            )
        except OSError:
            pass


def _write(kind: str, payload, folder: Path, name: str, fmt: str, options: dict) -> Path:
    overwrite = bool(st.session_state.get(OVERWRITE_KEY, False))
    if kind == "plotly":
        return save_plotly_figure(
            payload,
            folder,
            name,
            fmt=fmt,
            scale=options.get("scale", 2.0),
            width=options.get("width"),
            height=options.get("height"),
            overwrite=overwrite,
        )
    if kind == "matplotlib":
        return save_matplotlib_figure(
            payload,
            folder,
            name,
            fmt=fmt,
            dpi=options.get("dpi", 300),
            overwrite=overwrite,
            transparent=options.get("transparent", False),
        )
    if kind == "table":
        return save_table(payload, folder, name, fmt=fmt, overwrite=overwrite)
    if kind == "arrays":
        return save_arrays(payload, folder, name, fmt=fmt, overwrite=overwrite)
    if kind == "text":
        return save_text(payload, folder, name, fmt=fmt, overwrite=overwrite)
    raise ExportError(f"Unknown save kind: {kind}")


def render_save_panel(
    tab_name: str,
    default_name: str,
    *,
    key: str,
    figure=None,
    figure_kind: str = "plotly",
    table=None,
    arrays=None,
    text: str | None = None,
    subfolder: str = "",
    label: str = "💾 Save to disk",
    expanded: bool = False,
    caption: str = "",
) -> None:
    """Render the save controls for whatever this page has produced.

    Parameters
    ----------
    tab_name
        The page or tab title. It becomes the subfolder name, sanitized, so
        ``"🧭 GIWAXS Explorer"`` writes into ``GIWAXS_Explorer/``.
    default_name
        Suggested file stem, normally the frame or dataset name.
    key
        Unique widget-key prefix for this call site.
    figure, figure_kind
        A Plotly or matplotlib figure, and which of the two it is.
    table, arrays, text
        Optional companion payloads offered in the same panel.
    subfolder
        An extra level below the tab folder, for example the sample name.
    """

    ensure_output_settings()
    choices: dict[str, tuple[str, object]] = {}
    if figure is not None:
        choices["Figure"] = (figure_kind, figure)
    if table is not None:
        choices["Plotted data (table)"] = ("table", table)
    if arrays is not None:
        choices["Displayed array"] = ("arrays", arrays)
    if text is not None:
        choices["Text list"] = ("text", text)
    if not choices:
        return

    with st.expander(label, expanded=expanded):
        if caption:
            st.caption(caption)
        _root_input(
            st,
            f"{key}_root",
            "Output folder",
            "Type any folder on this computer; missing folders are created.",
        )

        controls = st.columns([1.2, 1.2, 1, 1])
        coerce_choice(st.session_state, f"{key}_what", list(choices))
        what = controls[0].selectbox("What to save", list(choices), key=f"{key}_what")
        kind, payload = choices[what]
        formats = list(_FORMATS[kind])
        # A remembered format outlives its payload: pick svg for a figure, switch
        # to the table, and "svg" is still there but no longer offered.
        coerce_choice(st.session_state, f"{key}_format", formats)
        fmt = controls[1].selectbox("Format", formats, key=f"{key}_format")
        options: dict = {}
        if kind == "matplotlib":
            options["dpi"] = controls[2].number_input(
                "DPI", 72, 1200, 300, 50, key=f"{key}_dpi", disabled=fmt not in {"png", "tif"}
            )
            options["transparent"] = controls[3].checkbox(
                "Transparent", value=False, key=f"{key}_transparent"
            )
        elif kind == "plotly":
            options["scale"] = controls[2].slider(
                "Image scale",
                1.0,
                4.0,
                2.0,
                0.5,
                key=f"{key}_scale",
                disabled=fmt in {"html", "json"},
                help="2 gives roughly 2× the on-screen pixel size.",
            )
            controls[3].caption("HTML stays interactive; PNG/SVG/PDF need kaleido.")

        name_columns = st.columns([3, 2])
        file_name = name_columns[0].text_input(
            "File name (no extension)",
            value=safe_component(default_name),
            key=f"{key}_name",
        )
        extra = name_columns[1].text_input(
            "Optional subfolder",
            value=subfolder,
            key=f"{key}_subfolder",
            help="A sample or session name below the page folder.",
        )

        folder = target_folder(tab_name, extra) if extra.strip() else target_folder(tab_name)
        preview = folder / f"{safe_component(file_name) or 'pyscattviz'}.{fmt}"
        st.caption("Will be written to")
        st.code(str(preview), language=None)

        if st.button(
            "Save to disk", type="primary", key=action_key(st.session_state, f"{key}_save")
        ):
            try:
                created = resolve_output_dir(
                    output_root(),
                    *(
                        ([tab_name] if st.session_state.get(SUBFOLDER_KEY, True) else [])
                        + ([extra] if extra.strip() else [])
                    ),
                    create=True,
                    date_subfolder=bool(st.session_state.get(DATE_KEY, False)),
                )
                written = _write(kind, payload, created, file_name, fmt, options)
            except ExportError as exc:
                st.error(str(exc))
            except OSError as exc:
                st.error(f"Could not write the file: {exc}")
            else:
                record_saved(written)
                st.success(f"Saved {written}")

        history = st.session_state.get(HISTORY_KEY, [])
        if history:
            st.caption("Recently saved")
            st.code("\n".join(history[:5]), language=None)
