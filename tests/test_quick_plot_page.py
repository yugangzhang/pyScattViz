from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

PAGES_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"
PAGE = PAGES_DIR / "08_Quick_Plot.py"

Q = np.logspace(-2, 0, 60)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config")))


@pytest.fixture
def output_root(tmp_path_factory, monkeypatch):
    folder = tmp_path_factory.mktemp("pyscattviz_output")
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(folder))
    return folder


@pytest.fixture
def curves(tmp_path):
    folder = tmp_path / "Results" / "giwaxs" / "cir_avg"
    folder.mkdir(parents=True)
    for index, angle in enumerate(("0.1000", "0.1500", "0.2000")):
        pd.DataFrame({"q_ca": Q, "iq_ca": (index + 1) * Q**-2}).to_csv(
            folder / f"Cir_Avg_Kim_th{angle}deg.tif.csv", index=False
        )
    pd.DataFrame({"q_ca": Q, "iq_ca": Q**-3}).to_csv(
        folder / "Cir_Avg_AgBH_calibration.tif.csv", index=False
    )
    np.savez(
        tmp_path / "Results" / "giwaxs" / "frame.npz",
        qimg=np.abs(np.arange(120, dtype=float).reshape(10, 12)),
    )
    return tmp_path / "Results" / "giwaxs"


def test_quick_plot_needs_paths_before_it_does_anything():
    app = AppTest.from_file(str(PAGE), default_timeout=60).run()
    assert not app.exception
    assert any("No paths yet" in item.value for item in app.info)


def test_quick_plot_expands_a_folder_from_the_dataset_basket(curves):
    app = AppTest.from_file(str(PAGE), default_timeout=120)
    app.session_state["pyscattviz_dataset_paths"] = [str(curves)]
    app.run()

    assert not app.exception
    assert any("4 table" in item.value for item in app.success)
    assert any("1 array" in item.value for item in app.success)
    # 1D, stacked map, and 2D panels all render.
    assert len(app.get("plotly_chart")) >= 3


def test_exclude_term_drops_the_calibration_file(curves):
    app = AppTest.from_file(str(PAGE), default_timeout=120)
    app.session_state["pyscattviz_dataset_paths"] = [str(curves)]
    app.session_state["quickplot_not"] = "AgBH"
    app.run()

    assert not app.exception
    assert any("3 table" in item.value for item in app.success)


def test_quick_plot_accepts_a_pasted_list_of_full_paths(curves):
    files = sorted(str(path) for path in (curves / "cir_avg").glob("*Kim*.csv"))
    app = AppTest.from_file(str(PAGE), default_timeout=120)
    app.session_state["quickplot_source"] = "Paste full paths"
    app.session_state["quickplot_pasted"] = "\n".join(files)
    app.run()

    assert not app.exception
    assert any("3 file(s)" in item.value for item in app.success)


def test_a_figure_is_written_into_a_subfolder_named_after_the_tab(curves, output_root):
    app = AppTest.from_file(str(PAGE), default_timeout=300)
    app.session_state["pyscattviz_dataset_paths"] = [str(curves)]
    app.run()

    fmt = next(item for item in app.selectbox if item.key == "quickplot_1d_save_format")
    fmt.set_value("html")
    app.run()
    next(item for item in app.button if item.key == "quickplot_1d_save_save").click().run()

    assert not app.exception
    written = list((output_root / "Quick_Plot").glob("*.html"))
    assert len(written) == 1
    assert written[0].stat().st_size > 0
    assert any("Saved" in item.value for item in app.success)


def test_the_plotted_table_can_be_written_next_to_the_figure(curves, output_root):
    app = AppTest.from_file(str(PAGE), default_timeout=300)
    app.session_state["pyscattviz_dataset_paths"] = [str(curves)]
    app.run()

    next(item for item in app.selectbox if item.key == "quickplot_1d_save_what").set_value(
        "Plotted data (table)"
    )
    app.run()
    next(item for item in app.button if item.key == "quickplot_1d_save_save").click().run()

    written = list((output_root / "Quick_Plot").glob("*.csv"))
    assert len(written) == 1
    assert "x[" in written[0].read_text().splitlines()[0]


def test_a_second_save_never_overwrites_the_first(curves, output_root):
    app = AppTest.from_file(str(PAGE), default_timeout=300)
    app.session_state["pyscattviz_dataset_paths"] = [str(curves)]
    app.run()
    fmt = next(item for item in app.selectbox if item.key == "quickplot_1d_save_format")
    fmt.set_value("html")
    app.run()
    for _attempt in range(2):
        next(item for item in app.button if item.key == "quickplot_1d_save_save").click().run()

    names = sorted(path.name for path in (output_root / "Quick_Plot").glob("*.html"))
    assert len(names) == 2
    assert names[1].endswith("_001.html")
