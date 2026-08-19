from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PAGES_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"
PAGE = PAGES_DIR / "02_Data_Selection.py"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    """Keep saved collections and settings out of the developer's home folder."""

    monkeypatch.setenv(
        "PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config"))
    )
    monkeypatch.setenv(
        "PYSCATTVIZ_OUTPUT_DIR", str(tmp_path_factory.mktemp("pyscattviz_output"))
    )


@pytest.fixture
def proposal(tmp_path):
    for geometry in ("giwaxs", "gisaxs"):
        folder = tmp_path / "projects" / "microbeam_Kim" / "Results" / geometry
        (folder / "cir_avg").mkdir(parents=True)
        (folder / "cir_avg" / f"Cir_Avg_Kim_{geometry}.tif.csv").write_text("q,I\n1,2\n")
    other = tmp_path / "projects" / "other_Lee" / "Results" / "giwaxs" / "cir_avg"
    other.mkdir(parents=True)
    (other / "Cir_Avg_Lee.tif.csv").write_text("q,I\n1,2\n")
    return tmp_path


def _search(app, and_terms="", or_terms="", not_terms=""):
    next(item for item in app.text_input if item.label.startswith("Must contain")).set_value(
        and_terms
    )
    next(item for item in app.text_input if item.label.startswith("May contain")).set_value(
        or_terms
    )
    next(item for item in app.text_input if item.label.startswith("Must not")).set_value(
        not_terms
    )
    app.run()
    next(item for item in app.button if item.label == "Search").click().run()
    return app


def test_folder_search_uses_and_or_exclude_lists(proposal):
    app = AppTest.from_file(str(PAGE), default_timeout=60)
    app.session_state["pyscattviz_search_roots_text"] = str(proposal)
    app.run()
    assert not app.exception

    _search(app, and_terms="Results", or_terms="giwaxs, gisaxs", not_terms="other_Lee")
    assert not app.exception
    rows = app.session_state["pyscattviz_search_rows"]
    assert rows
    assert all("other_Lee" not in row["path"] for row in rows)
    assert {"giwaxs", "gisaxs"} <= {row["name"] for row in rows}


def test_exclude_list_removes_a_matching_folder(proposal):
    app = AppTest.from_file(str(PAGE), default_timeout=60)
    app.session_state["pyscattviz_search_roots_text"] = str(proposal)
    app.run()
    _search(app, or_terms="giwaxs, gisaxs", not_terms="gisaxs")
    names = {row["name"] for row in app.session_state["pyscattviz_search_rows"]}
    assert "gisaxs" not in names


def test_search_reports_an_unavailable_root(tmp_path):
    app = AppTest.from_file(str(PAGE), default_timeout=60)
    app.session_state["pyscattviz_search_roots_text"] = str(tmp_path / "not_mounted")
    app.run()
    assert not app.exception
    assert any("not available" in item.value for item in app.warning)


def test_pasted_paths_are_described_and_can_fill_the_basket(proposal):
    giwaxs = proposal / "projects" / "microbeam_Kim" / "Results" / "giwaxs"
    app = AppTest.from_file(str(PAGE), default_timeout=60)
    app.session_state["pyscattviz_paste_paths"] = f"{giwaxs}\n/nowhere/at/all\n"
    app.run()
    assert not app.exception
    assert any("not available" in item.value for item in app.warning)

    add_button = next(
        item for item in app.button if item.label.startswith("Add 1 available")
    )
    add_button.click().run()
    assert app.session_state["pyscattviz_dataset_paths"] == [str(giwaxs)]


def test_basket_can_be_saved_and_reloaded_as_a_collection(proposal):
    giwaxs = str(proposal / "projects" / "microbeam_Kim" / "Results" / "giwaxs")
    app = AppTest.from_file(str(PAGE), default_timeout=60)
    app.session_state["pyscattviz_dataset_paths"] = [giwaxs]
    app.run()
    next(item for item in app.text_input if item.label == "Collection name").set_value(
        "microbeam Kim"
    )
    app.run()
    next(item for item in app.button if item.label == "Save collection").click().run()
    assert any("Saved" in item.value for item in app.success)

    fresh = AppTest.from_file(str(PAGE), default_timeout=60).run()
    next(item for item in fresh.button if item.label == "Replace basket").click().run()
    assert fresh.session_state["pyscattviz_dataset_paths"] == [giwaxs]


def test_sending_a_folder_to_the_explorers_sets_the_active_root(proposal):
    giwaxs = str(proposal / "projects" / "microbeam_Kim" / "Results" / "giwaxs")
    app = AppTest.from_file(str(PAGE), default_timeout=60)
    app.session_state["pyscattviz_dataset_paths"] = [giwaxs]
    app.run()
    next(
        item for item in app.button if item.label == "Send first folder to explorers"
    ).click().run()
    assert app.session_state["pyscattviz_active_root"] == giwaxs
    assert app.session_state["pyscattviz_file_root"] == giwaxs
