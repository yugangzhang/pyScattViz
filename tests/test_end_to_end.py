"""The journey a collaborator actually takes, start to finish.

Register a folder → find the result folders with term lists → keep them in the
basket → plot them → write the figure to a folder of their own. Each page is
tested on its own elsewhere; this checks that the state they hand each other
still lines up.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

PAGES_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"

Q = np.logspace(-2, 0.4, 50)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config")))


@pytest.fixture
def output_root(tmp_path_factory, monkeypatch):
    folder = tmp_path_factory.mktemp("pyscattviz_output")
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(folder))
    return folder


@pytest.fixture
def proposal(tmp_path):
    """A local folder shaped like a mounted proposal: two projects, two geometries."""

    for project in ("microbeam_Kim", "thinfilm_Lee"):
        for geometry in ("giwaxs", "gisaxs"):
            folder = tmp_path / "projects" / project / "Results" / geometry
            (folder / "cir_avg").mkdir(parents=True)
            for index, angle in enumerate(("0.1000", "0.1500", "0.2000")):
                stem = f"{project}_{geometry}_th{angle}deg"
                pd.DataFrame({"q_ca": Q, "iq_ca": (index + 1) * Q**-2}).to_csv(
                    folder / f"cir_avg/Cir_Avg_{stem}.tif.csv", index=False
                )
            pd.DataFrame({"q_ca": Q, "iq_ca": Q**-3}).to_csv(
                folder / "cir_avg/Cir_Avg_AgBH_calibration.tif.csv", index=False
            )
    return tmp_path


def test_register_then_select_then_plot_then_save(proposal, output_root):
    # 1. Register a folder that is already on this computer.
    mounts = AppTest.from_file(
        str(PAGES_DIR / "01_Data_Sources_and_Mounts.py"), default_timeout=120
    ).run()
    next(item for item in mounts.selectbox if item.label == "Access method").set_value(
        "Data already on this computer"
    )
    mounts.run()
    next(item for item in mounts.text_input if item.label == "Folder on this computer").set_value(
        str(proposal)
    )
    mounts.run()
    next(
        item for item in mounts.button if item.label == "Register folder for the other pages"
    ).click().run()
    assert not mounts.exception
    assert mounts.session_state["pyscattviz_active_root"] == str(proposal)

    # 2. Find Kim's GIWAXS results with the term lists, excluding the other project.
    selection = AppTest.from_file(str(PAGES_DIR / "02_Data_Selection.py"), default_timeout=120)
    selection.session_state["pyscattviz_search_roots_text"] = str(proposal)
    selection.run()
    next(item for item in selection.text_input if item.label.startswith("Must contain")).set_value(
        "Results, microbeam_Kim"
    )
    next(item for item in selection.text_input if item.label.startswith("May contain")).set_value(
        "giwaxs"
    )
    selection.run()
    next(item for item in selection.button if item.label == "Search").click().run()
    assert not selection.exception

    rows = selection.session_state["pyscattviz_search_rows"]
    assert [Path(row["path"]).name for row in rows] == ["giwaxs"]
    assert "microbeam_Kim" in rows[0]["path"]

    # 3. Put every result into the basket and save it under a name.
    next(
        item for item in selection.button if item.label == "Add every result to basket"
    ).click().run()
    basket = selection.session_state["pyscattviz_dataset_paths"]
    assert basket == [rows[0]["path"]]

    next(item for item in selection.text_input if item.label == "Collection name").set_value(
        "Kim giwaxs"
    )
    selection.run()
    next(item for item in selection.button if item.label == "Save collection").click().run()
    assert any("Saved" in item.value for item in selection.success)

    # 4. Plot the basket, excluding the calibration frame.
    plot = AppTest.from_file(str(PAGES_DIR / "08_Quick_Plot.py"), default_timeout=300)
    plot.session_state["pyscattviz_dataset_paths"] = basket
    plot.session_state["quickplot_not"] = "AgBH"
    plot.run()
    assert not plot.exception
    assert any("3 table" in item.value for item in plot.success)
    assert plot.get("plotly_chart")

    # 5. Write the figure into a folder named after the page.
    next(item for item in plot.selectbox if item.key == "quickplot_1d_save_format").set_value(
        "html"
    )
    plot.run()
    next(item for item in plot.button if item.key == "quickplot_1d_save_save").click().run()
    written = list((output_root / "Quick_Plot").glob("*.html"))
    assert len(written) == 1

    # 6. A new session reopens the saved collection without retyping anything.
    reopened = AppTest.from_file(str(PAGES_DIR / "02_Data_Selection.py"), default_timeout=120).run()
    next(item for item in reopened.button if item.label == "Replace basket").click().run()
    assert reopened.session_state["pyscattviz_dataset_paths"] == basket


def test_the_basket_folder_opens_directly_in_an_explorer(proposal, output_root):
    giwaxs = proposal / "projects" / "microbeam_Kim" / "Results" / "giwaxs"

    explorer = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=300)
    explorer.session_state["pyscattviz_dataset_paths"] = [str(giwaxs)]
    explorer.session_state["pyscattviz_active_root"] = str(giwaxs)
    explorer.run()

    assert not explorer.exception
    # Three angles plus the calibration frame, which the default filter hides.
    frame = next(item for item in explorer.selectbox if item.label == "Frame")
    assert len(frame.options) == 3
    assert all("AgBH" not in option for option in frame.options)

    next(
        item for item in explorer.selectbox if item.key == "pyscattviz_giwaxs_batch_format"
    ).set_value("html")
    explorer.run()
    next(
        item for item in explorer.button if item.key == "pyscattviz_giwaxs_batch_run"
    ).click().run()

    assert not explorer.exception
    written = list((output_root / "GIWAXS_Explorer").rglob("*.html"))
    assert len(written) == 3
