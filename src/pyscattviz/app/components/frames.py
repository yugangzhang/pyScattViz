"""Step through frames with the keyboard-free equivalent of a next button.

An angle series or an in-situ run is a few hundred frames, and picking each one
out of a dropdown to compare it with the last is the wrong tool: what you want
is to hold a position and move one at a time.

The awkward part is ordering. The frame dropdown is created near the top of the
script and the arrows belong under the panels, near what you are looking at —
but Streamlit refuses to change a widget's value after that widget has been
instantiated in the same run. So the arrows do not touch the dropdown. They
record a *pending step* in a key of their own and rerun;
:func:`apply_pending_step` consumes it at the top of the next run, before the
dropdown exists, where assignment is allowed.
"""

from __future__ import annotations

import streamlit as st

from pyscattviz.app.state import action_key

__all__ = ["apply_pending_step", "render_frame_stepper"]


def _step_key(prefix: str) -> str:
    return f"{prefix}_frame_step"


def apply_pending_step(prefix: str, labels) -> None:
    """Consume a queued step. Call this *before* creating the frame widget."""

    step = st.session_state.pop(_step_key(prefix), 0)
    if not step or not labels:
        return
    key = f"{prefix}_frame"
    current = st.session_state.get(key)
    try:
        index = list(labels).index(current)
    except ValueError:
        index = 0
    # Clamp rather than wrap: running off the end of a series and reappearing at
    # the start looks like the data changed under you.
    st.session_state[key] = labels[max(0, min(len(labels) - 1, index + int(step)))]


def render_frame_stepper(prefix: str, labels, index: int, container=None) -> None:
    """Draw ◀ / ▶ and the position, for stepping through the filtered frames."""

    host = container if container is not None else st
    total = len(labels)
    if total < 2:
        return

    columns = host.columns([1, 1, 3, 1, 1])
    if columns[0].button(
        "⏮",
        key=action_key(st.session_state, f"{prefix}_frame_first"),
        disabled=index <= 0,
        width="stretch",
        help="First frame",
    ):
        st.session_state[_step_key(prefix)] = -index
        st.rerun()
    if columns[1].button(
        "◀",
        key=action_key(st.session_state, f"{prefix}_frame_prev"),
        disabled=index <= 0,
        width="stretch",
        help="Previous frame",
    ):
        st.session_state[_step_key(prefix)] = -1
        st.rerun()

    columns[2].markdown(
        f"<div style='text-align:center;padding-top:0.45rem'>"
        f"<b>{index + 1:,}</b> / {total:,}</div>",
        unsafe_allow_html=True,
    )

    if columns[3].button(
        "▶",
        key=action_key(st.session_state, f"{prefix}_frame_next"),
        disabled=index >= total - 1,
        width="stretch",
        help="Next frame",
    ):
        st.session_state[_step_key(prefix)] = 1
        st.rerun()
    if columns[4].button(
        "⏭",
        key=action_key(st.session_state, f"{prefix}_frame_last"),
        disabled=index >= total - 1,
        width="stretch",
        help="Last frame",
    ):
        st.session_state[_step_key(prefix)] = total - 1 - index
        st.rerun()
