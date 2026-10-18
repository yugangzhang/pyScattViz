"""Org: open an org, make one of a data folder, or just look at a folder.

An org is one JSON file (pyDataOrg's organiser) that knows where an
experiment's reduced frames are: a sample per sample name, a stage per
folder, every product linked where it is — nothing is copied. It records
how its folder is read (a *layout*), so opening it again re-reads the
folder and links the frames written since. The Org pages — Overview, One
sample, Compare, In-situ, Ask AI — all work on the folder opened here.

A folder no layout recognises can be described by an AI model the user
runs (*Ask AI to propose*): it is shown the folder's names, never a file,
and proposes a layout and its options; the user looks at what that reads
and builds the org — or does not.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from pyscattviz.app.auth import require_password
from pyscattviz.app.state import action_key, keep_widget_state

keep_widget_state(st.session_state)
require_password()

from pyscattviz.app.components.datasource import render_folder_picker  # noqa: E402
from pyscattviz.app.components.org import state  # noqa: E402
from pyscattviz.org import ask, cms, layouts, store  # noqa: E402

state.on_page()

PROPOSAL = "svorg_proposal"
PENDING = "svorg_make_pending"

st.title("🗂️ Org")
st.caption(
    "An experiment's reduced frames, read from the file names — nothing is "
    "opened or copied — and kept as an org: one JSON file that links every "
    "product where it is and opens again with the frames written since."
)

if not store.has_pydataorg():
    st.info(
        "Keeping an org needs pyDataOrg, which is not installed here:\n\n"
        f"`{store.INSTALL_HINT}`\n\nA data folder can still be looked at "
        "(**Make an org — or look at a folder**), without keeping an org.",
        icon=":material/info:",
    )


def _go(action, *args, **kwargs) -> None:
    """Run an open/make action, show what went wrong, or rerun on success."""
    try:
        with st.spinner("Reading the folders …"):
            action(*args, **kwargs)
    except (OSError, ValueError, KeyError, ModuleNotFoundError) as exc:
        st.error(str(exc))
        return
    st.rerun()


open_tab, make_tab = st.tabs(["Open an org", "Make an org — or look at a folder"])

# ---------------------------------------------------------------------------
# Open
# ---------------------------------------------------------------------------

with open_tab:
    recent = store.recent()
    typed = st.text_input(
        "Org file (.json), or the folder it is kept in",
        key="svorg_open_path",
        placeholder="…/<proposal>/Org/<name>.json",
    ).strip()
    choices = []
    if typed:
        where = Path(typed).expanduser()
        if where.is_dir():
            choices = [str(p) for p in store.orgs_in(where)]
            if not choices:
                st.warning(f"No org in `{state.shown(where)}`.")
        elif where.is_file():
            choices = [str(where)]
        else:
            st.warning(f"`{typed}` is not a file or folder on this computer.")
    elif recent:
        choices = recent
        st.caption("Opened here before:")
    if choices:
        chosen = st.selectbox("Org", choices, format_func=state.shown, key="svorg_open_pick")
        if st.button(
            "Open this org",
            type="primary",
            disabled=not store.has_pydataorg(),
            key=action_key(st.session_state, "svorg_open_go"),
        ):
            _go(state.open_org, chosen)
    st.caption(
        "An org kept beside its data (`<proposal>/Org/`) records its paths "
        "relative to itself, so it opens wherever the proposal is mounted."
    )

# ---------------------------------------------------------------------------
# Make
# ---------------------------------------------------------------------------


def _option_key(layout: str, name: str) -> str:
    return f"svorg_make_{layout}_{name}"


def _apply_pending() -> None:
    """A proposal the user chose to use goes into the widgets before they
    are drawn."""
    found = st.session_state.pop(PENDING, None)
    if not found:
        return
    layout = found["layout"]
    st.session_state["svorg_make_layout"] = layout
    for name in layouts.get_layout(layout).options:
        value = found["options"].get(name)
        if name == "folders":
            value = ", ".join(value or [])
        elif name == "kind":
            value = value or "auto"
        st.session_state[_option_key(layout, name)] = value or ""
    if found.get("name"):
        st.session_state["svorg_make_name"] = found["name"]


def _options_inputs(layout: str) -> dict:
    """The layout's options, as the user set them."""
    spec = layouts.get_layout(layout)
    options = {}
    for name, what in spec.options.items():
        key = _option_key(layout, name)
        if name == "kind":
            options[name] = st.selectbox("kind", layouts.KINDS, key=key, help=what)
        elif name == "folders":
            text = st.text_input(
                "Only these folders (comma-separated; empty: every one)", key=key, help=what
            )
            options[name] = [t.strip() for t in text.split(",") if t.strip()] or None
        else:
            options[name] = st.text_input(name, key=key, help=what).strip() or None
    return {k: v for k, v in options.items() if v not in (None, "", "auto")}


@st.cache_resource(ttl=300, show_spinner=False)
def _backends():
    return ask.backends()


def _proposal_block(folder: str) -> None:
    if not ask.enabled():
        st.caption(
            "Ask AI is off on this server: a model bills the account of whoever "
            "runs it. The owner turns it on with `pyscattviz --ask`."
        )
        return
    found = _backends()
    if not found:
        st.caption(
            "No AI command-line tool found on this machine (codex, claude, gemini "
            "or ollama) — see README ▸ Ask AI."
        )
        return
    labels = {b.key: b.label for b in found}
    a, b = st.columns([1, 2])
    key = a.selectbox("Model", list(labels), format_func=labels.get, key="svorg_make_model")
    hint = b.text_input(
        "Anything the model should know (optional)",
        key="svorg_make_hint",
        placeholder="e.g. names are <sample>_<temperature>C_<scan>",
    )
    if st.button(
        "Propose how to read this folder", key=action_key(st.session_state, "svorg_make_propose")
    ):
        backend = next(x for x in found if x.key == key)
        with st.spinner(f"Asking {backend.label} …"):
            proposal = ask.propose_source(folder, backend=backend, hint=hint)
        st.session_state[PROPOSAL] = {**proposal.as_dict(), "folder": folder}
    proposal = st.session_state.get(PROPOSAL)
    if not proposal or proposal.get("folder") != folder:
        return
    if proposal["error"]:
        st.error(proposal["error"])
    if proposal["layout"]:
        st.markdown(
            f"**Proposed:** layout `{proposal['layout']}`"
            + (f", options `{json.dumps(proposal['options'])}`" if proposal["options"] else "")
            + (f", name *{proposal['name']}*" if proposal["name"] else "")
        )
    if proposal["why"]:
        st.caption(proposal["why"])
    st.caption(f"{proposal['backend']} · {proposal['seconds']:.0f} s")
    if not proposal["error"] and st.button(
        "Use this proposal", key=action_key(st.session_state, "svorg_make_use")
    ):
        st.session_state[PENDING] = proposal
        st.rerun()
    with st.expander("What the model was shown"):
        st.code(proposal["context"] or "", language=None)
        if proposal["text"]:
            st.markdown("**Its reply**")
            st.code(proposal["text"], language=None)


with make_tab:
    _apply_pending()
    folder = render_folder_picker(
        "svorg_make",
        "Data folder",
        help_text="The experiment's folder: a CMS `experiments/<name>`, or any folder "
        "with the reduction's product folders (cir_avg, q_image, qphi, qc …) "
        "below it.",
    )
    if folder:
        detected = layouts.detect_layout(folder)
        keys = list(layouts.LAYOUTS)
        if detected is None:
            st.warning(
                "No layout recognises this folder by itself. Choose one and its "
                "options — or ask an AI model to propose them, below."
            )
        st.session_state.setdefault("svorg_make_layout", detected or keys[0])
        if st.session_state.get("svorg_make_for") != folder:
            st.session_state["svorg_make_for"] = folder
            st.session_state["svorg_make_layout"] = detected or keys[0]
            st.session_state["svorg_make_store"] = str(store.suggest_store(folder))
            st.session_state["svorg_make_name"] = store.title(folder)
        layout = st.selectbox(
            "Layout",
            keys,
            key="svorg_make_layout",
            format_func=lambda k: (
                layouts.LAYOUTS[k].label + (" (recognised)" if k == detected else "")
            ),
            help="How the folder is read into frames.",
        )
        st.caption(layouts.LAYOUTS[layout].description)
        options = _options_inputs(layout)

        with st.expander("Ask AI to propose how to read it", expanded=detected is None):
            _proposal_block(folder)

        try:
            preview = state.read(folder, layout, layouts.check_options(layout, options))
        except (ValueError, KeyError, OSError) as exc:
            st.error(str(exc))
            preview = None
        if preview is not None:
            samples = cms.sample_table(preview)
            cols = st.columns(4)
            cols[0].metric("folders", preview["folder"].nunique())
            cols[1].metric("samples", len(samples))
            cols[2].metric("reduced frames", len(preview))
            cols[3].metric("in-situ runs", int((samples["kind"] == "insitu").sum()))
            if preview.empty:
                st.warning("This reads no reduced frames: check the layout and options.")
            else:
                st.dataframe(
                    samples.head(500).dropna(axis=1, how="all"), hide_index=True, width="stretch"
                )

            st.markdown("**Keep it as an org**")
            a, b = st.columns(2)
            name = a.text_input("Name", key="svorg_make_name")
            where = b.text_input(
                "Org file",
                key="svorg_make_store",
                help="Beside the data (`<proposal>/Org/`) it opens on any "
                "computer the proposal is mounted on.",
            )
            description = st.text_input("Description (optional)", key="svorg_make_desc")
            a, b = st.columns(2)
            if a.button(
                "Build the org",
                type="primary",
                disabled=preview.empty or not store.has_pydataorg(),
                key=action_key(st.session_state, "svorg_make_build"),
            ):
                _go(
                    state.create_org,
                    where,
                    folder,
                    layout=layout,
                    options=options,
                    name=name,
                    description=description,
                )
            if b.button(
                "Look at it without keeping an org",
                disabled=preview.empty,
                key=action_key(st.session_state, "svorg_make_look"),
            ):
                _go(state.open_folder, folder, layout=layout, options=options)

# ---------------------------------------------------------------------------
# The open folder
# ---------------------------------------------------------------------------

where = state.root()
if where is None:
    st.stop()

st.divider()
frames = state.frames()
samples = state.samples()
src = state.source()
org = state.org()
st.subheader(state.title())
st.caption(
    f"`{state.shown(where)}` · read as {layouts.LAYOUTS[src['layout']].label}"
    + (f", {json.dumps(src['options'])}" if src["options"] else "")
)

cols = st.columns(4)
cols[0].metric("folders", frames["folder"].nunique())
cols[1].metric("samples", len(samples))
cols[2].metric("reduced frames", len(frames))
cols[3].metric("in-situ runs", int((samples["kind"] == "insitu").sum()))

for name in sorted(samples["folder"].unique()):
    part = samples[samples["folder"] == name]
    kinds = ", ".join(f"{n} {k}" for k, n in part["kind"].value_counts().items())
    with st.expander(
        f"**{name}** — {len(part)} samples ({kinds})", expanded=samples["folder"].nunique() == 1
    ):
        st.dataframe(
            part.drop(columns=["folder"]).dropna(axis=1, how="all"),
            hide_index=True,
            width="stretch",
        )

st.subheader("The org")
if org is None:
    st.info(
        "No org is kept for this folder: it is looked at only. Build one under "
        "**Make an org** to keep its samples and links."
    )
    st.stop()
path = Path(org.path)
table = org.table(level="measurement", all_samples=True)
st.caption(
    f"{len(org.project)} samples · {len(table)} measurements (a product × detector "
    f"× angle) · kept in `{state.shown(path)}` "
    f"{'(saved)' if path.exists() else '(not saved yet)'}"
)
a, b, c = st.columns(3)
if a.button("Link new frames now", key=action_key(st.session_state, "svorg_org_sync")):
    state.rescan()
    n = state.sync_org()
    st.toast(f"{n} samples relinked" if n else "Nothing new")
if b.button("💾 Save the org", key=action_key(st.session_state, "svorg_org_save")):
    try:
        org.save()
        st.toast(f"Saved {state.shown(path)}")
    except OSError as exc:
        st.error(f"Could not save: {exc}")
c.download_button(
    "Links (CSV)",
    cms.link_rows(frames).to_csv(index=False),
    file_name=f"{store.tag(where)}_links.csv",
    key=action_key(st.session_state, "svorg_org_links"),
)
st.caption(
    "New frames are linked as they come, on every Org page; **Save** writes them "
    "into the file, so the next person to open it sees them at once."
)
with st.expander("The same in Python"):
    st.code(
        f'''from pyscattviz.org import cms, layouts, store

org = store.open_org("{state.shown(path)}")      # new frames linked in
source = store.source_of(org)                    # layout "{src["layout"]}"
frames = layouts.index(store.data_root(org), source.layout, source.options)
cms.sample_table(frames)                         # one row per sample
org.table(level="measurement")                   # what is linked
org.save()''',
        language="python",
    )
