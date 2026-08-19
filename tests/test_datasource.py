"""Choosing a folder, and narrowing frames, in the explorer sidebars.

Both used to fail in ways that had no workaround: a pasted path that was not yet
available cleared itself on the next rerun, and the keyword box ANDed its terms
so there was no way to ask for two samples at once.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

PAGES_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"
EXPLORERS = (
    "04_GISAXS_Explorer.py",
    "05_GIWAXS_Explorer.py",
    "06_Transmission_SAXS.py",
    "07_Transmission_WAXS.py",
)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config")))
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(tmp_path_factory.mktemp("pyscattviz_output")))


def _result_folder(root: Path, names) -> Path:
    """One mounted drive can hold many proposals; this builds one project."""

    cir = root / "cir_avg"
    cir.mkdir(parents=True)
    q = np.logspace(-2, 0.5, 20)
    for name in names:
        pd.DataFrame({"q_ca": q, "iq_ca": q**-2}).to_csv(
            cir / f"Cir_Avg_{name}.tif.csv", index=False
        )
    return root


@pytest.fixture
def drive(tmp_path):
    """Two proposals from two beamlines under one mount, as a real drive looks."""

    first = _result_folder(
        tmp_path / "proposal_one" / "Results" / "giwaxs",
        ["UV_20_A", "UV_30_A", "UV_40_A", "dark_A", "AgBH_cal"],
    )
    second = _result_folder(tmp_path / "proposal_two" / "Results" / "giwaxs", ["sampleB"])
    return first, second


def _folder_box(app):
    return next(item for item in app.text_input if item.label.startswith("Data path"))


def test_a_pasted_folder_is_accepted(drive):
    first, second = drive
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(first)
    app.run()

    _folder_box(app).set_value(str(second))
    app.run()

    assert not app.exception
    assert app.session_state["pyscattviz_active_root"] == str(second)
    assert _folder_box(app).value == str(second)


def test_an_unavailable_path_is_kept_so_it_can_be_corrected(drive):
    """It used to clear itself, which left no way to fix a typo."""

    first, _second = drive
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(first)
    app.run()

    _folder_box(app).set_value("Z:/not/mounted/yet")
    app.run()
    assert not app.exception
    assert _folder_box(app).value == "Z:/not/mounted/yet"
    assert any("not a folder" in item.value for item in app.warning)

    _folder_box(app).set_value(str(first))
    app.run()
    assert app.session_state["pyscattviz_active_root"] == str(first)


def test_an_unmounted_nsls2_path_says_what_to_do(drive):
    first, _second = drive
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(first)
    app.run()

    _folder_box(app).set_value("/nsls2/data/xxx/proposals/2026-2/pass-xxxxxx")
    app.run()

    assert not app.exception
    assert any("not mounted" in item.value for item in app.warning)


def test_a_registered_mount_translates_a_pasted_remote_path(drive):
    first, _second = drive
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=120)
    app.session_state["pyscattviz_path_mappings"] = [
        {"remote_root": "/nsls2/data/xxx/proposals", "local_root": str(first.parents[2])}
    ]
    app.run()

    _folder_box(app).set_value("/nsls2/data/xxx/proposals/proposal_one/Results/giwaxs")
    app.run()

    assert not app.exception
    assert app.session_state["pyscattviz_active_root"] == str(first)


def test_the_menu_offers_folders_already_visited(drive):
    first, second = drive
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(first)
    app.run()
    _folder_box(app).set_value(str(second))
    app.run()
    # The menu is drawn above the box, so a newly visited folder joins it on the
    # next interaction rather than the same one.
    app.run()

    picker = next(item for item in app.selectbox if item.key == "pyscattviz_giwaxs_folder_pick")
    assert any(option.endswith("proposal_one/Results/giwaxs") for option in picker.options)
    assert any(option.endswith("proposal_two/Results/giwaxs") for option in picker.options)


@pytest.mark.parametrize("page", EXPLORERS)
def test_every_explorer_offers_and_or_exclude(page, drive):
    first, _second = drive
    app = AppTest.from_file(str(PAGES_DIR / page), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(first)
    app.run()

    assert not app.exception
    labels = [item.label for item in app.text_input]
    assert "Must contain (AND)" in labels
    assert "May contain (OR)" in labels
    assert "Must not contain (EXCLUDE)" in labels


def test_the_or_box_selects_two_samples_at_once(drive):
    """UV_20 and UV_30 together — the AND-only box could not express this."""

    first, _second = drive
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(first)
    app.run()

    next(item for item in app.text_input if item.label.startswith("May contain")).set_value(
        "UV_20, UV_30"
    )
    app.run()

    frames = next(item for item in app.selectbox if item.label == "Frame").options
    assert sorted(frames) == ["UV_20_A", "UV_30_A"]


def test_the_and_and_exclude_boxes_still_work(drive):
    first, _second = drive
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(first)
    app.run()

    next(item for item in app.text_input if item.label.startswith("Must contain")).set_value("UV")
    app.run()
    assert sorted(next(i for i in app.selectbox if i.label == "Frame").options) == [
        "UV_20_A",
        "UV_30_A",
        "UV_40_A",
    ]

    next(item for item in app.text_input if item.label.startswith("Must not")).set_value("UV_40")
    app.run()
    assert sorted(next(i for i in app.selectbox if i.label == "Frame").options) == [
        "UV_20_A",
        "UV_30_A",
    ]


def test_publication_plot_offers_the_same_filters(drive):
    first, _second = drive
    app = AppTest.from_file(str(PAGES_DIR / "09_Publication_Plot.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(first)
    app.run()
    assert not app.exception

    next(item for item in app.text_input if item.label.startswith("May contain")).set_value(
        "UV_20, UV_30"
    )
    app.run()

    assert not app.exception
    offered = next(item for item in app.multiselect if item.label.startswith("Curves")).options
    assert sorted(offered) == ["UV_20_A", "UV_30_A"]


def test_the_qc_panel_starts_unchecked(drive):
    first, _second = drive
    (first / "qc").mkdir()
    (first / "qc" / "qc_UV_20_A.tif.png").write_bytes(b"")

    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(first)
    app.run()

    qc = next(item for item in app.checkbox if item.label.startswith("QC image"))
    assert qc.value is False
    curves = next(item for item in app.checkbox if item.label.startswith("Circular average"))
    assert curves.value is True
