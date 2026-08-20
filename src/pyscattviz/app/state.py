"""Helpers for values that must survive Streamlit multipage navigation.

Streamlit forgets a widget as soon as its page stops being rendered: switch to
another tab and back, and every colour map, every q limit, every filter is at
its default again. That makes the application exhausting to use, because moving
between the explorer and Quick Plot throws away the setup you just did.

:func:`keep_widget_state` fixes it for every widget at once. Streamlit only
discards keys it considers "widget state"; assigning a key back to itself marks
it as set by the user, and it is then kept. Every page calls it as its first
statement, so a page's widgets survive a visit to any other page.

The older :func:`prepare_persistent_widget` pair remains for the handful of
values that must also survive a *widget* being recreated with a different
default — the data-folder box, mainly — where mirroring into a second key that
is never attached to a widget is the more predictable choice.
"""

from __future__ import annotations

# Keys that must not be kept alive: caches and one-shot handoffs which should be
# recomputed or consumed rather than restored.
_TRANSIENT_PREFIXES = ("pyscattviz_console_result", "pyscattviz_console_handoff")

# A chart created with `on_select` is a widget, and like a button it refuses
# assignment through session_state — at *widget creation*, so a try/except
# around the assignment cannot catch it. `action_key` cannot help either: it
# registers when the chart is drawn, which is long after this function has run
# at the top of the page. A suffix rule is what makes it order-independent, and
# it protects the next selection chart somebody adds without their having to
# know any of this. Its value is a fresh selection each run and holds nothing
# worth restoring.
_WIDGET_SUFFIXES = ("_chart",)

# Buttons, download buttons, and file uploaders refuse assignment through
# session_state, and refuse it when the *widget* is created rather than when the
# value is set — so a try/except around the assignment cannot catch it. They also
# hold nothing worth restoring: a button is True for exactly one run. Each keyed
# one registers itself through `action_key` so it can be left alone.
ACTION_KEYS = "pyscattviz_action_keys"

try:  # pragma: no cover - the fallback only matters without Streamlit installed
    from streamlit.errors import StreamlitAPIException as _StreamlitAPIException

    # Buttons, downloads, and file uploaders refuse assignment through
    # session_state. They also have nothing worth restoring, so skipping them is
    # exactly right.
    _SKIP_ERRORS: tuple = (KeyError, TypeError, ValueError, _StreamlitAPIException)
except ImportError:
    _SKIP_ERRORS = (KeyError, TypeError, ValueError)


def action_key(session_state, key: str) -> str:
    """Register and return the key of a button, download, or uploader.

    Those widgets must be left out of :func:`keep_widget_state`; registering
    them here is how it knows. A selection-enabled chart is the same kind of
    widget but is handled by the ``_chart`` suffix rule instead, because it is
    drawn too late in the page to register itself in time.

    Returns ``key`` so it reads naturally inline::

        st.button("Save", key=action_key(st.session_state, f"{prefix}_save"))
    """

    registered = session_state.setdefault(ACTION_KEYS, set())
    registered.add(key)
    return key


def keep_widget_state(session_state) -> int:
    """Stop Streamlit from discarding this session's widget values.

    Call it as the first statement of every page. Returns the number of keys
    refreshed, which is useful to assert on in a test.
    """

    actions = session_state.get(ACTION_KEYS) or set()
    kept = 0
    for key in list(session_state.keys()):
        name = str(key)
        if (
            name.startswith(_TRANSIENT_PREFIXES)
            or name.endswith(_WIDGET_SUFFIXES)
            or name in actions
            or name == ACTION_KEYS
        ):
            continue
        try:
            session_state[key] = session_state[key]
        except _SKIP_ERRORS:
            # A widget key can vanish between listing and assignment, and a
            # button's value cannot be assigned at all. Neither is worth
            # restoring, so skip quietly.
            continue
        kept += 1
    return kept


def coerce_choice(session_state, key: str, options, default_index: int = 0) -> None:
    """Keep a remembered single choice valid when its options change.

    Now that widget values survive a page change, a selectbox can hold a value
    its options no longer contain — pick "svg", switch the payload to a table,
    and the format is stale. Streamlit will not complain; the next save simply
    goes wrong. Snap it back to a real option instead.
    """

    choices = list(options)
    if key in session_state and session_state[key] not in choices:
        session_state[key] = choices[default_index] if choices else None


def coerce_choices(session_state, key: str, options) -> None:
    """Keep a remembered multi-selection valid, dropping entries that are gone."""

    choices = list(options)
    current = session_state.get(key)
    if isinstance(current, (list, tuple)):
        kept = [item for item in current if item in choices]
        if len(kept) != len(current):
            session_state[key] = kept


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
    if disposable_key not in session_state or session_state.get(marker_key) != persistent_value:
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
