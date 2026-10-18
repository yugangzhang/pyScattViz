"""Ask AI: a question in plain words about the open org, answered by an AI
model configured on this machine — from the org's records only
(:mod:`pyscattviz.org.ask`).

The model is given the org as text: raw against reduced per folder, one
line per sample, and the frames of the samples the question names. It
reads no data file and writes nothing. Off on a password-protected server
unless its owner turns it on (``pyscattviz --ask``): a model bills the
account of whoever runs the GUI.
"""

from __future__ import annotations

import streamlit as st

from pyscattviz.app.auth import require_password
from pyscattviz.app.state import action_key, keep_widget_state

keep_widget_state(st.session_state)
require_password()

from pyscattviz.app.components.org import state  # noqa: E402
from pyscattviz.org import ask, store  # noqa: E402

state.on_page()

HISTORY = "svorg_ask_history"
PENDING = "svorg_ask_pending"
EXAMPLES = (
    "What has been measured so far, folder by folder?",
    "Which frames are still to reduce?",
    "Which samples were measured at more than one angle?",
    "Which in-situ runs are there, and how long is each?",
    "What should we measure next, and why?",
)

st.title("💬 Ask AI")
st.caption(
    "Questions about the open org — its folders, samples, frames and progress — "
    "answered by your AI model from the org's records. The model is not shown "
    "the scattering, only names and counts."
)

if not ask.enabled():
    st.info(
        "Asking is off on this server: an AI model bills the account of whoever runs "
        "it. The owner turns it on with `pyscattviz --ask`; or run pyScattViz on your "
        "own machine, where it uses your own models.",
        icon=":material/lock:",
    )
    st.stop()


@st.cache_resource(ttl=300, show_spinner=False)
def _backends():
    return ask.backends()


found = _backends()
if not found:
    st.warning(
        "No AI command-line tool found on this machine (codex, claude, gemini or "
        "ollama) — see README ▸ Ask AI."
    )
    st.stop()
state.require_source()


def _show(entry: dict) -> None:
    with st.chat_message("user"):
        st.markdown(entry["question"])
    answer = entry["answer"]
    with st.chat_message("assistant"):
        if answer["error"]:
            st.error(answer["error"])
        if answer["text"]:
            st.markdown(answer["text"])
        named = f" · frames of {', '.join(answer['samples'])}" if answer["samples"] else ""
        st.caption(
            f"{entry['model']} · {answer['seconds']:.0f} s · answered from the "
            f"org's records ({entry['about']}){named}"
        )
        with st.expander("What the model was given"):
            st.code(answer["context"], language=None)


labels = {b.key: b.label for b in found}
left, right = st.columns([3, 1])
key = left.selectbox(
    "Model",
    list(labels),
    format_func=labels.get,
    key="svorg_ask_model",
    help="The AI tools configured here, for the account running this "
    "GUI; the first is the default. Your own list of models goes in "
    f"{ask.USER_CONFIG} (README ▸ Ask AI).",
)
with right:
    st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
    if st.button(
        "Clear the conversation",
        width="stretch",
        key=action_key(st.session_state, "svorg_ask_clear"),
    ):
        st.session_state[HISTORY] = []
cols = st.columns(len(EXAMPLES))
for n, (col, example) in enumerate(zip(cols, EXAMPLES)):
    if col.button(
        example, width="stretch", key=action_key(st.session_state, f"svorg_ask_example_{n}")
    ):
        st.session_state[PENDING] = example

history = st.session_state.setdefault(HISTORY, [])
for entry in history:
    _show(entry)

typed = st.chat_input("Ask about the org…")
question = typed or st.session_state.pop(PENDING, None)
if question:
    backend = next((b for b in found if b.key == key), found[0])
    with st.chat_message("user"):
        st.markdown(question)
    frames = state.frames()
    src = state.source()
    with st.spinner(f"Asking {backend.label} …"):
        answer = ask.ask(
            question,
            frames,
            backend=backend,
            history=[(e["question"], e["answer"]["text"]) for e in history],
            org=state.org(),
            progress=state.progress(),
            source=store.Source(**src),
            root=state.root(),
        )
    history.append(
        {
            "question": question,
            "model": backend.label,
            "about": f"{frames['sample'].nunique()} samples, {len(frames)} frames",
            "answer": answer.as_dict(),
        }
    )
    st.rerun()
