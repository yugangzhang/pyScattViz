"""Helpers every page test needs now that nothing opens by itself.

Naming a folder reads filenames and stops there: the explorers open on no frame,
Quick Plot and Publication Plot open on no file. That is the behaviour under
test, so a test that wants a panel has to ask for one exactly as a user does —
by choosing from the picker and letting the page rerun.
"""

from __future__ import annotations


def open_frame(app, index: int = 0, key: str | None = None):
    """Choose a frame on an explorer page and rerun it. Returns the stem."""

    picker = next(
        item
        for item in app.selectbox
        if item.key == key or (key is None and str(item.key).endswith("_frame"))
    )
    stem = picker.options[index]
    picker.set_value(stem).run()
    return stem


def choose_files(app, key: str, count: int = 1, options=None):
    """Tick the first ``count`` entries of a file multiselect and rerun."""

    picker = next(item for item in app.multiselect if item.key == key)
    chosen = list(options if options is not None else picker.options)[:count]
    picker.set_value(chosen).run()
    return chosen


def choose_file(app, key: str, index: int = 0):
    """Choose one entry of a file selectbox and rerun."""

    picker = next(item for item in app.selectbox if item.key == key)
    value = picker.options[index]
    picker.set_value(value).run()
    return value
