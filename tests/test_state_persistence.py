"""Widget values must survive leaving a page and coming back.

Streamlit discards a widget as soon as its page stops being rendered. That made
the application exhausting: every setting was lost on each tab change.
"""

import re
from pathlib import Path

import pytest

from pyscattviz.app.state import (
    ACTION_KEYS,
    action_key,
    coerce_choice,
    coerce_choices,
    keep_widget_state,
)

APP_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app"
WIDGETS = (
    "selectbox",
    "checkbox",
    "number_input",
    "text_input",
    "text_area",
    "radio",
    "slider",
    "multiselect",
    "toggle",
)


def test_keeping_state_reassigns_every_key():
    state = {"a": 1, "b": "two"}
    assert keep_widget_state(state) == 2
    assert state == {"a": 1, "b": "two"}


def test_action_keys_are_registered_and_then_left_alone():
    """A button refuses assignment, and refuses it when the widget is built."""

    state = {}
    assert action_key(state, "save_btn") == "save_btn"
    state["save_btn"] = False
    state["colour"] = "Viridis"

    kept = keep_widget_state(state)
    assert kept == 1  # colour only; the button and the registry are skipped
    assert state["colour"] == "Viridis"


def test_transient_keys_are_not_restored():
    state = {"pyscattviz_console_result": {"value": 1}, "keep_me": 2}
    assert keep_widget_state(state) == 1


def test_a_remembered_choice_is_snapped_back_when_its_options_change():
    """Pick svg for a figure, switch to a table, and svg is no longer offered."""

    state = {"fmt": "svg"}
    coerce_choice(state, "fmt", ["csv", "txt"])
    assert state["fmt"] == "csv"

    coerce_choice(state, "fmt", ["csv", "txt"])
    assert state["fmt"] == "csv"  # already valid, left alone


def test_coercing_a_choice_handles_an_empty_option_list():
    state = {"fmt": "svg"}
    coerce_choice(state, "fmt", [])
    assert state["fmt"] is None


def test_a_remembered_multi_selection_drops_entries_that_are_gone():
    state = {"files": ["a.csv", "b.csv", "c.csv"]}
    coerce_choices(state, "files", ["a.csv", "c.csv"])
    assert state["files"] == ["a.csv", "c.csv"]


def test_coercing_leaves_an_untouched_key_alone():
    state = {}
    coerce_choice(state, "missing", ["a"])
    coerce_choices(state, "missing", ["a"])
    assert state == {}


def _unkeyed_widgets(path: Path):
    """Widget calls with no key=; those cannot survive a page change."""

    source = path.read_text()
    pattern = re.compile(r"\.(" + "|".join(WIDGETS) + r")\(")
    found = []
    for match in pattern.finditer(source):
        start = source.index("(", match.end() - 1)
        depth, end = 0, start
        while end < len(source):
            if source[end] == "(":
                depth += 1
            elif source[end] == ")":
                depth -= 1
                if depth == 0:
                    break
            end += 1
        if "key=" not in source[start : end + 1]:
            found.append((source[: match.start()].count("\n") + 1, match.group(1)))
    return found


@pytest.mark.parametrize("path", sorted(APP_DIR.rglob("*.py")), ids=lambda item: item.name)
def test_every_input_widget_has_a_key(path):
    """A widget without a key has no session-state entry to preserve."""

    unkeyed = _unkeyed_widgets(path)
    assert not unkeyed, f"{path.name}: unkeyed widgets at lines {[line for line, _ in unkeyed]}"


def test_every_page_keeps_its_state():
    """The call has to be there, or that page still loses everything."""

    pages = sorted((APP_DIR / "pages").glob("[0-9][0-9]_*.py"))
    assert len(pages) >= 12
    for page in pages:
        source = page.read_text()
        if "runpy.run_module" in source:
            continue  # the wrapper's component calls it instead
        assert "keep_widget_state(st.session_state)" in source, page.name

    for component in ("grazing_explorer_page.py", "transmission_explorer_page.py"):
        source = (APP_DIR / "components" / component).read_text()
        assert "keep_widget_state(st.session_state)" in source, component


def test_the_registry_key_itself_is_never_restored():
    state = {ACTION_KEYS: {"a_btn"}, "a_btn": False, "real": 3}
    assert keep_widget_state(state) == 1
