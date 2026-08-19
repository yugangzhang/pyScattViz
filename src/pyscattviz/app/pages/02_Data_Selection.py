"""Find the folders and files worth reviewing, then keep them in a basket.

This page is the GUI form of the ``ls_dir`` helper I have used in pyScatt for
years: give it search roots and three term lists — must contain, may contain,
must not contain — and it returns matching folders or files with their full
paths. Whatever is selected goes into a **dataset basket** that the explorers,
Quick Plot, and Publication Plot all read, and that can be saved under a name
and reopened next week.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from pyscattviz.app.components.saving import render_save_panel
from pyscattviz.app.state import (
    prepare_persistent_widget,
    set_persistent_value,
    store_persistent_widget,
)
from pyscattviz.data_sources import load_path_mappings, translate_remote_path
from pyscattviz.datasets import (
    delete_collection,
    list_collections,
    load_collection,
    normalize_paths,
    save_collection,
)
from pyscattviz.discovery import (
    DATA_EXTENSIONS,
    classify_folder,
    describe_paths,
    find_files,
    find_folders,
    parse_terms,
)

TAB_NAME = "Data Selection"
BASKET_KEY = "pyscattviz_dataset_paths"

st.set_page_config(page_title="Data Selection", page_icon="🎯", layout="wide")
st.title("🎯 Data Selection")
st.caption(
    "Filter folders or files with AND / OR / EXCLUDE term lists, or paste a list "
    "of full paths. Only names are read — no array is opened here."
)

st.session_state.setdefault("pyscattviz_path_mappings", load_path_mappings())
st.session_state.setdefault(BASKET_KEY, [])
mappings = st.session_state["pyscattviz_path_mappings"]


def _add_to_basket(paths) -> int:
    """Add paths to the basket, keeping order and dropping duplicates."""

    basket = list(st.session_state.get(BASKET_KEY, []))
    added = 0
    for item in normalize_paths(paths, mappings):
        if item not in basket:
            basket.append(item)
            added += 1
    st.session_state[BASKET_KEY] = basket
    return added


def _default_roots() -> list[str]:
    candidates = []
    for value in (
        st.session_state.get("pyscattviz_active_root"),
        st.session_state.get("pyscattviz_file_root"),
        *st.session_state.get("pyscattviz_roots", []),
        *(item["local_root"] for item in mappings),
    ):
        if not value:
            continue
        text = str(value)
        if text not in candidates and Path(text).expanduser().is_dir():
            candidates.append(text)
    return candidates


search_tab, paste_tab, basket_tab, saved_tab = st.tabs(
    ["🔍 Search", "📋 Paste full paths", "🧺 Dataset basket", "💾 Saved collections"]
)

# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
with search_tab:
    roots_key = prepare_persistent_widget(
        st.session_state,
        "pyscattviz_search_roots_text",
        "\n".join(_default_roots()),
    )
    roots_text = st.text_area(
        "Search roots (one folder per line)",
        key=roots_key,
        on_change=store_persistent_widget,
        args=(st.session_state, "pyscattviz_search_roots_text"),
        height=90,
        placeholder=r"Z:\ or /home/me/data or a mounted proposal root",
        help=(
            "A registered mount, a local disk, or a USB drive. An original "
            "/nsls2/... root is translated through the saved mount mappings."
        ),
    )
    raw_roots = [line.strip() for line in roots_text.splitlines() if line.strip()]
    search_roots, missing_roots = [], []
    for value in raw_roots:
        translated, _mapping = translate_remote_path(value, mappings)
        candidate = Path(translated).expanduser()
        (search_roots if candidate.is_dir() else missing_roots).append(str(candidate))
    if missing_roots:
        st.warning(
            "These roots are not available on this computer and will be skipped: "
            + ", ".join(f"`{item}`" for item in missing_roots)
        )

    mode = st.radio(
        "Find",
        ["Folders", "Files"],
        horizontal=True,
        key="pyscattviz_search_mode",
        help="Folders is the usual choice: pick result folders, then open an explorer.",
    )

    term_columns = st.columns(3)
    and_text = term_columns[0].text_input(
        "Must contain (AND)",
        key="pyscattviz_search_and",
        placeholder="Results, giwaxs",
        help="Every term must appear. Separate with commas or new lines.",
    )
    or_text = term_columns[1].text_input(
        "May contain (OR)",
        key="pyscattviz_search_or",
        placeholder="0.10deg, 0.15deg",
        help="At least one term must appear. Leave empty to impose no condition.",
    )
    no_text = term_columns[2].text_input(
        "Must not contain (EXCLUDE)",
        key="pyscattviz_search_not",
        placeholder="AgBH, DirBeam, test",
        help="A folder or file matching any of these is dropped.",
    )
    st.caption(
        "A term is a plain substring unless it contains a wildcard: `Kim_*_WAXS` "
        "matches the whole name. Matching ignores case."
    )

    option_columns = st.columns(4)
    match_on = option_columns[0].selectbox(
        "Match on",
        ["name", "path"],
        index=1,
        key="pyscattviz_search_match_on",
        help="`path` lets `Results AND giwaxs` match a folder by where it sits.",
    )
    max_depth = option_columns[1].number_input(
        "Depth below each root",
        1,
        12,
        4,
        1,
        key="pyscattviz_search_depth",
        help="Keep this small over a network mount; 4 covers most proposal layouts.",
    )
    max_results = option_columns[2].number_input(
        "Maximum results", 10, 20_000, 500, 50, key="pyscattviz_search_max"
    )
    if mode == "Folders":
        with option_columns[3]:
            products_only = st.checkbox(
                "Only reduction folders",
                value=False,
                key="pyscattviz_search_products_only",
                help="Keep folders that contain cir_avg, q_image, qphi, qc, or stitched.",
            )
            describe_products = st.checkbox(
                "Report products",
                value=True,
                key="pyscattviz_search_describe",
                disabled=products_only,
                help=(
                    "Lists which products each folder holds. It costs one extra "
                    "directory listing per match — free locally, noticeable over "
                    "SFTP. Turn it off for a fast first pass."
                ),
            )
        extensions: tuple[str, ...] = ()
    else:
        products_only = False
        describe_products = True
        extensions = tuple(
            option_columns[3].multiselect(
                "Extensions",
                sorted({item for group in DATA_EXTENSIONS.values() for item in group}),
                default=[".csv", ".npz"],
                key="pyscattviz_search_extensions",
            )
        )

    if st.button("Search", type="primary", disabled=not search_roots):
        and_list = parse_terms(and_text)
        or_list = parse_terms(or_text)
        no_list = parse_terms(no_text)
        with st.spinner("Reading directory names only …"):
            if mode == "Folders":
                rows, truncated = find_folders(
                    search_roots,
                    and_list,
                    or_list,
                    no_list,
                    match_on=match_on,
                    max_depth=int(max_depth),
                    max_results=int(max_results),
                    products_only=products_only,
                    describe_products=describe_products,
                )
            else:
                rows, truncated = find_files(
                    search_roots,
                    and_list,
                    or_list,
                    no_list,
                    extensions=extensions,
                    match_on=match_on,
                    max_depth=int(max_depth),
                    max_results=int(max_results),
                )
        st.session_state["pyscattviz_search_rows"] = rows
        st.session_state["pyscattviz_search_truncated"] = truncated
        st.session_state["pyscattviz_search_kind"] = mode
        # Record the cap actually used, so the warning below stays truthful even
        # after the user edits the widget without searching again.
        st.session_state["pyscattviz_search_used_max"] = int(max_results)

    rows = st.session_state.get("pyscattviz_search_rows")
    if rows is not None:
        if not rows:
            st.warning(
                "Nothing matched. Widen the term lists, raise the depth, or switch "
                "`Match on` between name and path."
            )
        else:
            if st.session_state.get("pyscattviz_search_truncated"):
                used_max = st.session_state.get("pyscattviz_search_used_max", max_results)
                st.warning(
                    f"Stopped at the {int(used_max):,}-result cap. Narrow the terms "
                    "or raise the cap to see the rest."
                )
            st.success(
                f"{len(rows):,} matching "
                f"{st.session_state.get('pyscattviz_search_kind', 'Folders').lower()}."
            )
            table = pd.DataFrame(rows)
            table.insert(0, "select", False)
            display_columns = [
                column
                for column in (
                    "select",
                    "name",
                    "products",
                    "data_files",
                    "suffix",
                    "size",
                    "modified",
                    "depth",
                    "path",
                )
                if column in table
            ]
            edited = st.data_editor(
                table[display_columns],
                width="stretch",
                hide_index=True,
                disabled=[column for column in display_columns if column != "select"],
                column_config={
                    "select": st.column_config.CheckboxColumn("✔", width="small"),
                    "path": st.column_config.TextColumn("full path", width="large"),
                },
                key="pyscattviz_search_editor",
            )
            chosen = edited[edited["select"]]["path"].tolist()

            action_columns = st.columns([1.4, 1.4, 1.2, 2])
            if action_columns[0].button(
                f"Add {len(chosen)} selected to basket", disabled=not chosen
            ):
                st.success(f"Added {_add_to_basket(chosen)} new path(s) to the basket.")
            if action_columns[1].button("Add every result to basket"):
                added = _add_to_basket([row["path"] for row in rows])
                st.success(f"Added {added} new path(s) to the basket.")
            if action_columns[2].button(
                "Open first in explorers", disabled=not chosen
            ):
                first = chosen[0]
                folder = first if Path(first).is_dir() else str(Path(first).parent)
                set_persistent_value(st.session_state, "pyscattviz_file_root", folder)
                st.session_state["pyscattviz_active_root"] = folder
                st.success(
                    f"`{folder}` is now the active folder for the scattering explorers."
                )
            action_columns[3].caption(
                "Tick the ✔ column to choose rows, or add every result at once."
            )

            render_save_panel(
                TAB_NAME,
                "search_results",
                key="data_selection_results",
                table=pd.DataFrame(rows),
                text="\n".join(row["path"] for row in rows),
                caption="Save the result table, or a plain list of full paths.",
            )

# ---------------------------------------------------------------------------
# Paste
# ---------------------------------------------------------------------------
with paste_tab:
    st.markdown(
        "Paste full paths — one per line — from an email, a notebook, or a "
        "previous session. Folders and files may be mixed. An original "
        "`/nsls2/...` path is translated through the registered mount mappings."
    )
    pasted = st.text_area(
        "Full paths",
        height=200,
        key="pyscattviz_paste_paths",
        placeholder=(
            "/nsls2/data/smi/proposals/2026-2/pass-319371/.../Results/giwaxs\n"
            "Z:\\projects\\microbeam_Kim\\Results\\giwaxs\\cir_avg\\Cir_Avg_sample.tif.csv"
        ),
    )
    upload = st.file_uploader("…or load a .txt/.csv list", type=["txt", "csv"])
    uploaded_text = ""
    if upload is not None:
        try:
            uploaded_text = upload.getvalue().decode("utf-8-sig")
        except UnicodeDecodeError:
            st.error("The path list must be UTF-8 text.")

    candidates = normalize_paths(
        [line for chunk in (pasted, uploaded_text) for line in chunk.splitlines()],
        mappings,
    )
    if candidates:
        described = describe_paths(candidates)
        available = [item for item in described if item["available"]]
        missing = [item for item in described if not item["available"]]
        st.dataframe(
            pd.DataFrame(described)[["name", "kind", "products", "path"]],
            width="stretch",
            hide_index=True,
        )
        if missing:
            st.warning(
                f"{len(missing)} path(s) are not available on this computer. Mount the "
                "proposal or correct the path; the rest can still be added."
            )
        left, right = st.columns(2)
        if left.button(
            f"Add {len(available)} available path(s) to basket", disabled=not available
        ):
            st.success(
                f"Added {_add_to_basket(item['path'] for item in available)} new path(s)."
            )
        if right.button("Add all pasted paths anyway", disabled=not described):
            st.info(f"Added {_add_to_basket(item['path'] for item in described)} path(s).")

# ---------------------------------------------------------------------------
# Basket
# ---------------------------------------------------------------------------
with basket_tab:
    basket = st.session_state.get(BASKET_KEY, [])
    if not basket:
        st.info(
            "The basket is empty. Use the Search or Paste tab, then come back here to "
            "send the selection to an explorer, to Quick Plot, or to a saved collection."
        )
    else:
        described = describe_paths(basket)
        summary = pd.DataFrame(described)
        summary.insert(0, "keep", True)
        edited = st.data_editor(
            summary[["keep", "name", "kind", "products", "path"]],
            width="stretch",
            hide_index=True,
            disabled=["name", "kind", "products", "path"],
            column_config={"keep": st.column_config.CheckboxColumn("keep", width="small")},
            key="pyscattviz_basket_editor",
        )
        folders = [item["path"] for item in described if item["kind"] == "folder"]
        files = [item["path"] for item in described if item["kind"] == "file"]
        st.caption(f"{len(folders):,} folder(s) · {len(files):,} file(s)")

        row = st.columns(4)
        if row[0].button("Apply keep/remove"):
            st.session_state[BASKET_KEY] = edited[edited["keep"]]["path"].tolist()
            st.rerun()
        if row[1].button("Clear the basket"):
            st.session_state[BASKET_KEY] = []
            st.rerun()
        if row[2].button("Send first folder to explorers", disabled=not folders):
            set_persistent_value(st.session_state, "pyscattviz_file_root", folders[0])
            st.session_state["pyscattviz_active_root"] = folders[0]
            st.success(f"`{folders[0]}` is now the active folder for the explorers.")
        row[3].caption("Quick Plot and Publication Plot read this basket directly.")

        if folders:
            st.markdown("**Reduction products found in the selected folders**")
            product_rows = []
            for folder in folders[:200]:
                info = classify_folder(folder)
                product_rows.append(
                    {
                        "folder": folder,
                        "products": ", ".join(info["products"]) or "—",
                        "data files": info["data_files"],
                    }
                )
            st.dataframe(pd.DataFrame(product_rows), width="stretch", hide_index=True)

        save_columns = st.columns([2, 3, 1.2])
        collection_name = save_columns[0].text_input(
            "Collection name", value="", placeholder="microbeam_Kim_giwaxs"
        )
        collection_note = save_columns[1].text_input(
            "Note (optional)", value="", placeholder="0.10 and 0.15 deg, no calibration"
        )
        with save_columns[2]:
            st.write("")
            st.write("")
            if st.button("Save collection", disabled=not collection_name.strip()):
                try:
                    written = save_collection(
                        collection_name, st.session_state[BASKET_KEY], collection_note
                    )
                except (ValueError, OSError) as exc:
                    st.error(str(exc))
                else:
                    st.success(f"Saved {written}")

        render_save_panel(
            TAB_NAME,
            "dataset_basket",
            key="data_selection_basket",
            table=pd.DataFrame(described),
            text="\n".join(st.session_state[BASKET_KEY]),
            caption="Write the basket to disk as a table or a plain path list.",
        )

# ---------------------------------------------------------------------------
# Saved collections
# ---------------------------------------------------------------------------
with saved_tab:
    collections = list_collections()
    if not collections:
        st.info(
            "No saved collections yet. Build a basket, give it a name, and save it — "
            "the file is plain JSON under `~/.pyscattviz/collections/` and holds "
            "nothing but paths."
        )
    else:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "name": item["name"],
                        "paths": item["count"],
                        "saved": item["saved"],
                        "note": item["note"],
                    }
                    for item in collections
                ]
            ),
            width="stretch",
            hide_index=True,
        )
        chosen = st.selectbox(
            "Collection",
            [item["name"] for item in collections],
            key="pyscattviz_collection_choice",
        )
        actions = st.columns(3)
        if actions[0].button("Load into basket"):
            try:
                payload = load_collection(chosen)
            except ValueError as exc:
                st.error(str(exc))
            else:
                added = _add_to_basket(payload["paths"])
                st.success(f"Loaded {payload['name']}: {added} new path(s) added.")
        if actions[1].button("Replace basket"):
            try:
                payload = load_collection(chosen)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state[BASKET_KEY] = normalize_paths(payload["paths"], mappings)
                st.success(f"The basket now holds {len(st.session_state[BASKET_KEY])} path(s).")
        if actions[2].button("Delete collection"):
            try:
                removed = delete_collection(chosen)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.success("Deleted." if removed else "It was already gone.")
                st.rerun()
