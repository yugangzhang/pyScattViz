from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from pyscattviz.app.components.scattering import BATCH_PANELS, frame_panel_figure

PAGES_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"

Q = np.logspace(-2, 0.4, 40)


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
    """Three angles with a circular average, one of which also has a q-image."""

    root = tmp_path / "Results" / "giwaxs"
    (root / "cir_avg").mkdir(parents=True)
    (root / "q_image").mkdir()
    (root / "qphi").mkdir()
    (root / "stitched").mkdir()
    for index, angle in enumerate(("0.1000", "0.1500", "0.2000")):
        stem = f"Kim_sampleA_th{angle}deg_2026_08_01_12_00_0{index}"
        pd.DataFrame({"q_ca": Q, "iq_ca": (index + 1) * Q**-2}).to_csv(
            root / "cir_avg" / f"Cir_Avg_{stem}.tif.csv", index=False
        )
    first = "Kim_sampleA_th0.1000deg_2026_08_01_12_00_00"
    rng = np.random.default_rng(0)
    np.savez(
        root / "q_image" / f"qimg_{first}.tif.npz",
        qimg=np.abs(rng.normal(10, 2, (30, 40))),
        qx=np.linspace(-3, 3, 40),
        qz=np.linspace(0, 3, 30),
    )
    np.savez(
        root / "qphi" / f"qphi_{first}.tif.npz",
        q=np.linspace(0.01, 3, 25),
        phi=np.linspace(0, 180, 18),
        qphi=np.abs(rng.normal(5, 1, (18, 25))),
    )
    Image.fromarray((rng.random((20, 24)) * 255).astype(np.uint8)).save(
        root / "stitched" / f"{first}.tif"
    )
    return root


def _frame(giwaxs, stem):
    from pyscattviz.app.components.scattering import index_frames

    index_frames.clear()
    table = index_frames(str(giwaxs))
    return table.set_index("stem").loc[stem]


FIRST = "Kim_sampleA_th0.1000deg_2026_08_01_12_00_00"


def test_frame_panel_figure_builds_every_product(giwaxs):
    row = _frame(giwaxs, FIRST)
    for panel in BATCH_PANELS:
        if panel == "qc":
            continue  # this fixture has no QC folder
        built = frame_panel_figure(row, panel, title=FIRST)
        assert built is not None, panel
        figure, table, arrays = built
        assert figure.layout.title.text == FIRST
        if panel == "cir_avg":
            assert list(table.columns) == ["q", "I"]
            assert arrays is None
        else:
            assert table is None
            assert arrays


def test_frame_panel_figure_returns_none_for_a_missing_product(giwaxs):
    row = _frame(giwaxs, "Kim_sampleA_th0.1500deg_2026_08_01_12_00_01")
    assert frame_panel_figure(row, "q_image") is None
    assert frame_panel_figure(row, "qphi") is None
    assert frame_panel_figure(row, "cir_avg") is not None


def test_frame_panel_figure_rejects_an_unknown_panel(giwaxs):
    with pytest.raises(ValueError):
        frame_panel_figure(_frame(giwaxs, FIRST), "not_a_panel")


def test_frame_panel_figure_honours_the_display_settings(giwaxs):
    row = _frame(giwaxs, FIRST)
    figure, _table, _arrays = frame_panel_figure(
        row, "q_image", cmap="Viridis", logI=False, height=500
    )
    assert figure.data[0].colorscale[0][1].lower().startswith("#")
    assert figure.layout.height == 500
    assert figure.data[0].colorbar.title.text == "I"


def test_batch_export_writes_one_file_per_frame(giwaxs, output_root):
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=600)
    app.session_state["pyscattviz_active_root"] = str(giwaxs)
    app.run()
    assert not app.exception

    next(
        item for item in app.selectbox if item.key == "pyscattviz_giwaxs_batch_panel"
    ).set_value("cir_avg")
    app.run()
    next(
        item for item in app.selectbox if item.key == "pyscattviz_giwaxs_batch_format"
    ).set_value("html")
    app.run()
    next(
        item for item in app.button if item.key == "pyscattviz_giwaxs_batch_run"
    ).click().run()

    assert not app.exception
    folder = output_root / "GIWAXS_Explorer" / "batch_cir_avg"
    written = sorted(path.name for path in folder.glob("*.html"))
    assert len(written) == 3
    assert all("th0." in name for name in written)
    assert any("Wrote 3 file(s)" in item.value for item in app.success)


def test_batch_export_reports_frames_without_that_product(giwaxs, output_root):
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=600)
    app.session_state["pyscattviz_active_root"] = str(giwaxs)
    app.run()
    next(
        item for item in app.selectbox if item.key == "pyscattviz_giwaxs_batch_format"
    ).set_value("html")
    app.run()
    next(
        item for item in app.button if item.key == "pyscattviz_giwaxs_batch_run"
    ).click().run()

    assert not app.exception
    assert any("were skipped" in item.value for item in app.info)


def test_batch_subfolder_follows_the_panel_until_the_user_renames_it(giwaxs, output_root):
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=600)
    app.session_state["pyscattviz_active_root"] = str(giwaxs)
    app.run()

    box = next(
        item for item in app.text_input if item.key == "pyscattviz_giwaxs_batch_subfolder"
    )
    assert box.value.startswith("batch_")
    next(
        item for item in app.selectbox if item.key == "pyscattviz_giwaxs_batch_panel"
    ).set_value("cir_avg")
    app.run()
    assert (
        next(
            item
            for item in app.text_input
            if item.key == "pyscattviz_giwaxs_batch_subfolder"
        ).value
        == "batch_cir_avg"
    )

    next(
        item for item in app.text_input if item.key == "pyscattviz_giwaxs_batch_subfolder"
    ).set_value("angle_series")
    app.run()
    next(
        item for item in app.selectbox if item.key == "pyscattviz_giwaxs_batch_panel"
    ).set_value("q_image")
    app.run()
    assert (
        next(
            item
            for item in app.text_input
            if item.key == "pyscattviz_giwaxs_batch_subfolder"
        ).value
        == "angle_series"
    )


def test_the_dataset_basket_offers_folders_in_the_explorer_sidebar(giwaxs):
    other = giwaxs.parent / "gisaxs"
    (other / "cir_avg").mkdir(parents=True)
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=600)
    app.session_state["pyscattviz_active_root"] = str(giwaxs)
    app.session_state["pyscattviz_dataset_paths"] = [str(giwaxs), str(other)]
    app.run()

    assert not app.exception
    picker = next(
        item for item in app.selectbox if item.key == "pyscattviz_giwaxs_basket_pick"
    )
    assert picker.options == ["— type a path below —", "Results/giwaxs", "Results/gisaxs"]
