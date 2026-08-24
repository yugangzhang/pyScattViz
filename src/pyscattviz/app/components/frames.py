"""Choose a frame, and step through the frames, without opening any of them.

Choosing a folder must read names and nothing else. A result folder holds
hundreds or thousands of reduced frames, it is usually on a mount, and opening
one the moment the folder is named is both a surprise and a wait nobody asked
for. So :func:`render_frame_picker` opens on *no* frame and the page draws its
panels only for a frame that has actually been asked for.

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

__all__ = [
    "apply_pending_step",
    "render_frame_catalog",
    "render_frame_picker",
    "render_frame_stepper",
]

# The names a frame table can offer without opening a single file — every one of
# them came out of the filename or the directory entry during indexing.
_CATALOG_COLUMNS = (
    "stem",
    "th",
    "well",
    "timestamp",
    "has_raw",
    "has_raw_plot",
    "has_qc",
    "has_qimg",
    "has_qphi",
    "has_cir",
)


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
        # No frame is open — a step left over from the previous folder. Drop it:
        # honouring it would open a frame the user never asked for, which is the
        # one thing choosing a folder must not do.
        return
    # Clamp rather than wrap: running off the end of a series and reappearing at
    # the start looks like the data changed under you.
    st.session_state[key] = labels[max(0, min(len(labels) - 1, index + int(step)))]


def render_frame_picker(prefix: str, labels, container=None, *, label: str = "Frame"):
    """The frame dropdown, opening on nothing. Returns ``None`` until chosen.

    Streamlit gives a value in ``session_state`` precedence over ``index``, so a
    frame that has already been opened stays open across a rerun and across a
    page change, and the arrows keep working — but a fresh folder starts closed.
    A stem remembered from a different folder is not an option here, so it is
    forgotten rather than left to raise.
    """

    host = container if container is not None else st
    options = list(labels)
    key = f"{prefix}_frame"
    if st.session_state.get(key) not in options:
        st.session_state[key] = None
    # Consume a step queued by the arrows under the panels. Must happen before
    # the dropdown is created: Streamlit refuses to change a widget after that.
    apply_pending_step(prefix, options)
    return host.selectbox(
        label,
        options=options,
        index=None,
        placeholder=f"Choose one of {len(options):,} frames",
        key=key,
    )


def render_frame_catalog(frames, container=None, *, message: str = "") -> None:
    """List what is available without opening any of it.

    This is what a page shows in place of its panels while no frame has been
    chosen: the names, the angle, and which products each frame has — all of it
    already known from the filename scan.
    """

    host = container if container is not None else st
    host.info(
        message
        or "Pick a frame above to open it. Choosing a folder reads filenames only; "
        "no image, map, or curve is read from disk until a frame is chosen."
    )
    columns = [name for name in _CATALOG_COLUMNS if name in frames]
    host.dataframe(frames[columns], width="stretch", hide_index=True)


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
