"""Helpers for values that must survive Streamlit multipage navigation."""

from __future__ import annotations


def widget_key(persistent_key: str) -> str:
    """Return the disposable widget key paired with a persistent state key."""

    return f"_{persistent_key}"


def _marker_key(persistent_key: str) -> str:
    return f"{persistent_key}__widget_value"


def prepare_persistent_widget(session_state, persistent_key: str, default):
    """Restore persistent data into a widget key before creating the widget.

    Streamlit removes a widget's key when its page is no longer rendered. The
    unprefixed key is never attached to a widget, so it survives page changes.
    """

    if persistent_key not in session_state:
        session_state[persistent_key] = default
    disposable_key = widget_key(persistent_key)
    marker_key = _marker_key(persistent_key)
    persistent_value = session_state[persistent_key]
    if (
        disposable_key not in session_state
        or session_state.get(marker_key) != persistent_value
    ):
        session_state[disposable_key] = persistent_value
        session_state[marker_key] = persistent_value
    return disposable_key


def store_persistent_widget(session_state, persistent_key: str) -> None:
    """Copy a changed disposable widget value into persistent state."""

    value = session_state[widget_key(persistent_key)]
    session_state[persistent_key] = value
    session_state[_marker_key(persistent_key)] = value


def set_persistent_value(session_state, persistent_key: str, value) -> None:
    """Set persistent state; its widget will synchronize on the next rerun."""

    session_state[persistent_key] = value
