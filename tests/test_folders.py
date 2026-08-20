"""The remembered-folder file: round trips, hand edits, and reopening.

The point of writing markdown rather than JSON is that a user can open the file
and edit it, so the parser has to cope with what a person would actually type —
no backticks, no date, a note after a plain double hyphen.
"""

from pathlib import Path

import pytest

from pyscattviz.folders import (
    MAX_RECENT,
    FolderEntry,
    folder_paths,
    folders_file,
    forget_folder,
    load_folder_entries,
    parse_markdown,
    remember_folder,
    render_markdown,
    save_folder_entries,
    set_note,
    set_pinned,
)

PAGES_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config")))
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(tmp_path_factory.mktemp("pyscattviz_output")))


def test_the_file_lives_outside_any_repository():
    """A path to an embargoed proposal must not be committable by accident."""

    location = folders_file()
    assert location.name == "data_folders.md"
    assert "Repos" not in str(location) or "pyscattviz_config" in str(location)


def test_a_folder_survives_a_round_trip(tmp_path):
    folder = tmp_path / "analysis"
    folder.mkdir()

    entries = remember_folder(str(folder), note="CMS GIWAXS", today="2026-08-19")
    save_folder_entries(entries)

    reloaded = load_folder_entries()
    assert [item.path for item in reloaded] == [str(folder)]
    assert reloaded[0].note == "CMS GIWAXS"
    assert reloaded[0].last_used == "2026-08-19"
    assert reloaded[0].exists


def test_the_most_recent_folder_comes_first(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()

    entries = remember_folder(str(first), today="2026-08-18", entries=[])
    entries = remember_folder(str(second), today="2026-08-19", entries=entries)
    assert [item.path for item in entries] == [str(second), str(first)]

    # Opening the first one again moves it back to the front.
    entries = remember_folder(str(first), today="2026-08-19", entries=entries)
    assert [item.path for item in entries] == [str(first), str(second)]


def test_reopening_a_folder_keeps_its_note(tmp_path):
    folder = str(tmp_path)
    entries = remember_folder(folder, note="PVDF on MXene", today="2026-08-18", entries=[])
    entries = remember_folder(folder, today="2026-08-19", entries=entries)
    assert entries[0].note == "PVDF on MXene"
    assert entries[0].last_used == "2026-08-19"


def test_a_hand_written_file_is_read():
    """What a person would type, not what the writer emits."""

    text = """# my folders

## Pinned

- /mnt/data32/beamtime/analysis -- the one I keep coming back to

## Recent

- `/mnt/data32/other/analysis` — with backticks <!-- used 2026-08-19 -->
* /plain/star/bullet
not a list item at all
"""
    entries = parse_markdown(text)
    paths = [item.path for item in entries]
    assert paths == [
        "/mnt/data32/beamtime/analysis",
        "/mnt/data32/other/analysis",
        "/plain/star/bullet",
    ]
    assert entries[0].pinned and entries[0].note == "the one I keep coming back to"
    assert not entries[1].pinned and entries[1].note == "with backticks"
    assert entries[1].last_used == "2026-08-19"
    assert entries[2].note == ""


def test_what_is_written_is_what_is_read_back():
    entries = [
        FolderEntry("/a/pinned", note="a note", last_used="2026-08-19", pinned=True),
        FolderEntry("/b/recent", last_used="2026-08-18"),
    ]
    assert parse_markdown(render_markdown(entries)) == entries


def test_a_pinned_folder_is_offered_first_and_never_ages_out():
    entries = set_pinned("/keep/me", True, entries=[])
    for index in range(MAX_RECENT + 5):
        entries = remember_folder(f"/tmp/folder{index}", today="2026-08-19", entries=entries)

    assert entries[0].path == "/keep/me"
    assert entries[0].pinned
    assert len([item for item in entries if not item.pinned]) <= MAX_RECENT
    assert "/keep/me" in folder_paths(entries)


def test_a_folder_can_be_forgotten_and_annotated():
    entries = remember_folder("/a", today="2026-08-19", entries=[])
    entries = remember_folder("/b", today="2026-08-19", entries=entries)

    entries = set_note("/a", "  spaced note  ", entries=entries)
    assert next(item for item in entries if item.path == "/a").note == "spaced note"

    entries = forget_folder("/a", entries=entries)
    assert [item.path for item in entries] == ["/b"]


def test_a_trailing_separator_is_not_a_different_folder():
    entries = remember_folder("/data/analysis/", today="2026-08-19", entries=[])
    entries = remember_folder("/data/analysis", today="2026-08-19", entries=entries)
    assert len(entries) == 1


def test_saving_is_skipped_when_nothing_changed(tmp_path):
    entries = remember_folder(str(tmp_path), today="2026-08-19", entries=[])
    save_folder_entries(entries)
    stamp = folders_file().stat().st_mtime_ns

    save_folder_entries(entries)
    assert folders_file().stat().st_mtime_ns == stamp


def test_an_unwritable_config_dir_does_not_raise(monkeypatch, tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("I am a file, not a folder")
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(blocked))
    assert save_folder_entries([FolderEntry("/a")]) is None
    assert load_folder_entries() == []


def test_a_folder_used_once_is_waiting_next_session(tmp_path, monkeypatch):
    """The whole point: close the browser, come back, the folder is already there."""

    from streamlit.testing.v1 import AppTest

    analysis = tmp_path / "giwaxs" / "analysis"
    (analysis / "cir_avg").mkdir(parents=True)
    import numpy as np
    import pandas as pd

    q = np.linspace(0.1, 3.0, 50)
    pd.DataFrame({"q_ca": q, "iq_ca": np.exp(-q)}).to_csv(
        analysis / "cir_avg" / "Cir_Avg_sampleA.tiff.csv", index=False
    )

    # Session one: open the folder the way a user would, by typing it.
    first = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=300)
    first.run()
    box = next(item for item in first.text_input if "Data path" in item.label)
    box.set_value(str(analysis)).run()
    assert not first.exception

    assert folders_file().exists()
    assert str(analysis) in folders_file().read_text()

    # Session two: a brand new app, nothing carried over in memory.
    second = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=300)
    second.run()
    assert not second.exception
    assert second.session_state["pyscattviz_active_root"] == str(analysis)
    assert str(analysis) in second.session_state["pyscattviz_recent_roots"]


def test_a_remembered_folder_that_is_gone_is_not_opened(tmp_path):
    """A dropped mount must not become the folder the app opens on."""

    from streamlit.testing.v1 import AppTest

    save_folder_entries([FolderEntry("/mnt/gone/analysis", last_used="2026-08-19")])
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=300)
    app.run()

    assert not app.exception
    assert "pyscattviz_active_root" not in app.session_state
    # It stays in the file, though — the mount may well come back.
    assert "/mnt/gone/analysis" in folders_file().read_text()
