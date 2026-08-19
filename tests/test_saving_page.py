from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app"
PAGES_DIR = APP_DIR / "pages"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv(
        "PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config"))
    )


@pytest.fixture
def output_root(tmp_path_factory, monkeypatch):
    folder = tmp_path_factory.mktemp("pyscattviz_output")
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(folder))
    return folder


@pytest.fixture
def giwaxs(tmp_path):
    folder = tmp_path / "Results" / "giwaxs" / "cir_avg"
    folder.mkdir(parents=True)
    pd.DataFrame({"q_ca": [0.01, 0.05, 0.1], "iq_ca": [100.0, 20.0, 5.0]}).to_csv(
        folder / "Cir_Avg_Kim_th0.1000deg.tif.csv", index=False
    )
    return tmp_path / "Results" / "giwaxs"


def test_output_folder_page_lists_one_folder_per_page(output_root):
    app = AppTest.from_file(str(PAGES_DIR / "11_Output_Folder.py"), default_timeout=60).run()
    assert not app.exception
    folders = app.dataframe[0].value
    assert "GIWAXS Explorer" in folders["page"].tolist()
    assert all(str(output_root) in item for item in folders["folder"])


def test_output_folder_page_creates_the_root_and_a_custom_subfolder(output_root):
    target = output_root / "chosen"
    app = AppTest.from_file(str(PAGES_DIR / "11_Output_Folder.py"), default_timeout=60).run()
    next(
        item for item in app.text_input if item.label == "Save figures and tables to"
    ).set_value(str(target))
    app.run()
    next(item for item in app.button if item.label == "Create it now").click().run()
    assert target.is_dir()

    next(item for item in app.text_input if item.label == "Subfolder name").set_value(
        "microbeam Kim/2026"
    )
    app.run()
    next(item for item in app.button if item.label == "Create subfolder").click().run()
    assert (target / "microbeam_Kim_2026").is_dir()


def test_the_output_root_is_remembered_across_pages(output_root):
    target = output_root / "shared"
    app = AppTest.from_file(str(PAGES_DIR / "11_Output_Folder.py"), default_timeout=60).run()
    next(
        item for item in app.text_input if item.label == "Save figures and tables to"
    ).set_value(str(target))
    app.run()

    other = AppTest.from_file(str(PAGES_DIR / "08_Quick_Plot.py"), default_timeout=60).run()
    assert other.session_state["pyscattviz_output_root"] == str(target)


def test_a_publication_figure_is_written_into_its_own_page_folder(giwaxs, output_root):
    app = AppTest.from_file(str(PAGES_DIR / "09_Publication_Plot.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(giwaxs)
    app.run()
    assert not app.exception

    next(
        item for item in app.button if item.key == "publication_save_save"
    ).click().run()

    written = list((output_root / "Publication_Plot").glob("*.png"))
    assert len(written) == 1
    assert written[0].stat().st_size > 0


def test_an_explorer_panel_is_written_into_its_own_page_folder(giwaxs, output_root):
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=180)
    app.session_state["pyscattviz_active_root"] = str(giwaxs)
    app.run()
    assert not app.exception

    fmt = next(
        item
        for item in app.selectbox
        if item.key == "pyscattviz_giwaxs_panel_save_format"
    )
    fmt.set_value("html")
    app.run()
    next(
        item
        for item in app.button
        if item.key == "pyscattviz_giwaxs_panel_save_save"
    ).click().run()

    written = list((output_root / "GIWAXS_Explorer").glob("*.html"))
    assert len(written) == 1
    # The frame stem keeps its decimal point rather than being cut at the dot.
    assert "th0.1000deg" in written[0].name


def test_turning_off_the_per_page_subfolder_writes_into_the_root(giwaxs, output_root):
    app = AppTest.from_file(str(PAGES_DIR / "09_Publication_Plot.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(giwaxs)
    app.session_state["pyscattviz_output_subfolder_per_tab"] = False
    app.run()
    next(
        item for item in app.button if item.key == "publication_save_save"
    ).click().run()

    assert list(output_root.glob("*.png"))
    assert not (output_root / "Publication_Plot").exists()


def test_switching_the_payload_switches_to_a_valid_format(giwaxs, output_root):
    """A Plotly-only format must not survive a switch to the table payload."""

    app = AppTest.from_file(str(PAGES_DIR / "08_Quick_Plot.py"), default_timeout=300)
    app.session_state["pyscattviz_dataset_paths"] = [str(giwaxs)]
    app.run()

    next(item for item in app.selectbox if item.key == "quickplot_1d_save_format").set_value(
        "svg"
    )
    app.run()
    next(item for item in app.selectbox if item.key == "quickplot_1d_save_what").set_value(
        "Plotted data (table)"
    )
    app.run()

    assert not app.exception
    fmt = next(item for item in app.selectbox if item.key == "quickplot_1d_save_format")
    assert fmt.options == ["csv", "txt"]
    assert fmt.value in fmt.options


def test_changing_the_root_in_one_panel_updates_the_sidebar_box(giwaxs, output_root):
    """Several output-root boxes are on screen at once and must agree."""

    target = output_root / "moved"
    app = AppTest.from_file(str(PAGES_DIR / "08_Quick_Plot.py"), default_timeout=300)
    app.session_state["pyscattviz_dataset_paths"] = [str(giwaxs)]
    app.run()

    next(
        item for item in app.text_input if item.key == "quickplot_1d_save_root"
    ).set_value(str(target))
    app.run()

    assert not app.exception
    assert app.session_state["pyscattviz_output_root"] == str(target)
    sidebar_box = next(
        item for item in app.text_input if item.key == "pyscattviz_output_root_widget"
    )
    assert sidebar_box.value == str(target)
    other_panel = next(
        item for item in app.text_input if item.key == "quickplot_list_save_root"
    )
    assert other_panel.value == str(target)
