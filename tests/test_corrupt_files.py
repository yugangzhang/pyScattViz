"""A real proposal folder always contains a few files that cannot be read.

An interrupted reduction leaves a zero-byte CSV; a dropped mount leaves a
truncated npz. None of that may take a page down — the frame reports itself and
the rest of the review continues.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pyscattviz.app.components.scattering import load_cir, load_qimg, load_qphi, load_raw
from pyscattviz.dataio import DataReadError, read_arrays, read_curve, read_image

PAGES_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config")))
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(tmp_path_factory.mktemp("pyscattviz_output")))


@pytest.fixture
def broken(tmp_path):
    """A result folder with one good frame and every failure mode I have seen."""

    root = tmp_path / "Results" / "giwaxs"
    (root / "cir_avg").mkdir(parents=True)
    (root / "q_image").mkdir()
    (root / "qphi").mkdir()
    (root / "qc").mkdir()

    (root / "cir_avg" / "Cir_Avg_good.tif.csv").write_text("q_ca,iq_ca\n0.01,100\n0.05,20\n0.1,5\n")
    # "empty" would match the calibration filter (Empty), so name it plainly.
    (root / "cir_avg" / "Cir_Avg_zerobyte.tif.csv").write_text("")
    (root / "cir_avg" / "Cir_Avg_prose.tif.csv").write_text("no numbers here\nat all\n")
    (root / "cir_avg" / "Cir_Avg_onecolumn.tif.csv").write_text("I\n1\n2\n")
    (root / "q_image" / "qimg_truncated.tif.npz").write_bytes(b"PK\x03\x04truncated")
    (root / "q_image" / "qimg_notanarchive.tif.npz").write_bytes(b"not a numpy file")
    (root / "qphi" / "qphi_empty.tif.npz").write_bytes(b"")
    (root / "qc" / "qc_notanimage.png").write_text("hello")
    return root


BAD_CIR = ("Cir_Avg_zerobyte.tif.csv", "Cir_Avg_prose.tif.csv", "Cir_Avg_onecolumn.tif.csv")
BAD_NPZ = ("qimg_truncated.tif.npz", "qimg_notanarchive.tif.npz")


def test_scattering_loaders_raise_one_catchable_error(broken):
    for name in BAD_CIR:
        with pytest.raises(DataReadError):
            load_cir(str(broken / "cir_avg" / name))
    for name in BAD_NPZ:
        with pytest.raises(DataReadError):
            load_qimg(str(broken / "q_image" / name))
    with pytest.raises(DataReadError):
        load_qphi(str(broken / "qphi" / "qphi_empty.tif.npz"))
    with pytest.raises(DataReadError):
        load_raw(str(broken / "qc" / "qc_notanimage.png"))


def test_a_good_file_still_loads(broken):
    q, intensity = load_cir(str(broken / "cir_avg" / "Cir_Avg_good.tif.csv"))
    assert q.tolist() == [0.01, 0.05, 0.1]
    assert intensity.tolist() == [100.0, 20.0, 5.0]


def test_dataio_readers_raise_one_catchable_error(broken):
    for name in BAD_CIR:
        with pytest.raises(DataReadError):
            read_curve(broken / "cir_avg" / name)
    for name in BAD_NPZ:
        # A truncated npz raises EOFError and a non-archive raises BadZipFile;
        # neither is an OSError, so both used to escape.
        with pytest.raises(DataReadError):
            read_arrays(broken / "q_image" / name)
    with pytest.raises(DataReadError):
        read_image(broken / "qc" / "qc_notanimage.png")


@pytest.mark.parametrize(
    "page",
    [
        "04_GISAXS_Explorer.py",
        "05_GIWAXS_Explorer.py",
        "06_Transmission_SAXS.py",
        "07_Transmission_WAXS.py",
        "08_Quick_Plot.py",
        "09_Publication_Plot.py",
        "10_Plotting_Studio.py",
    ],
)
def test_a_page_survives_a_folder_full_of_corrupt_files(page, broken):
    app = AppTest.from_file(str(PAGES_DIR / page), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(broken)
    app.session_state["pyscattviz_dataset_paths"] = [str(broken)]
    app.run()

    assert not app.exception, [item.message for item in app.exception]


def test_the_explorer_names_the_file_it_could_not_read(broken):
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(broken)
    app.run()
    assert not app.exception

    frame = next(item for item in app.selectbox if item.label == "Frame")
    assert "zerobyte" in frame.options
    frame.set_value("zerobyte")
    app.run()

    assert not app.exception
    reported = " ".join(item.value for item in app.error)
    assert "Cir_Avg_zerobyte.tif.csv could not be read" in reported


def test_publication_plot_skips_unreadable_curves_and_keeps_the_good_one(broken):
    app = AppTest.from_file(str(PAGES_DIR / "09_Publication_Plot.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(broken)
    app.run()

    assert not app.exception
    warned = " ".join(item.value for item in app.warning)
    assert warned.count("could not be read") == 3
    # The one good curve is still plotted rather than the page giving up: the
    # save panel only renders once a figure has been built.
    assert any(item.key == "publication_save_save" for item in app.button)
