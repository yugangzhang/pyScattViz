"""Per-beamline defaults, and framing a q-image on the data rather than the axes."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from pyscattviz.app.components.scattering import data_extent, detect_beamline

PAGES_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config")))
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(tmp_path_factory.mktemp("pyscattviz_output")))


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/mnt/z/cms/proposals/x/Results/giwaxs", "cms"),
        ("Z:/smi_remote/2026/giwaxs", "smi"),
        ("/data/CMS/2026_Cycle1/giwaxs", "cms"),
        # A word that merely starts with the letters is not the beamline.
        ("/data/commissioning/giwaxs", None),
        ("/data/smithers/giwaxs", None),
        ("/nsls2/data/xxx/proposals", None),
    ],
)
def test_the_beamline_is_read_from_the_path(path, expected):
    assert detect_beamline(path) == expected


def test_data_extent_crops_the_blank_margin():
    """A remeshed q-image covers part of the plane; the rest is NaN."""

    image = np.full((10, 12), np.nan)
    image[3:7, 4:9] = 5.0
    x = np.linspace(-3, 3, 12)
    y = np.linspace(0, 5, 10)

    box = data_extent(image, x, y)
    assert box == pytest.approx((x[4], x[8], y[3], y[6]))


def test_data_extent_ignores_a_stray_pixel_when_asked():
    image = np.full((10, 10), np.nan)
    image[4:6, 4:6] = 1.0
    image[0, 0] = 99.0  # one hot pixel far from the detector
    x = y = np.arange(10, dtype=float)

    generous = data_extent(image, x, y)
    strict = data_extent(image, x, y, min_fraction=0.15)
    assert generous[0] == 0.0
    assert strict[0] == 4.0


def test_data_extent_reports_nothing_for_an_empty_image():
    assert data_extent(np.full((4, 4), np.nan)) is None
    assert data_extent(np.array([])) is None


def _giwaxs(root: Path) -> Path:
    (root / "cir_avg").mkdir(parents=True)
    (root / "q_image").mkdir()
    (root / "qphi").mkdir()
    q = np.logspace(-2, 0.8, 40)
    pd.DataFrame({"q_ca": q, "iq_ca": q**-2}).to_csv(
        root / "cir_avg" / "Cir_Avg_sampleA.tif.csv", index=False
    )
    # Data fills only the middle of the qx–qz plane, as a real remesh does.
    image = np.full((30, 40), np.nan)
    image[8:22, 10:30] = 7.0
    np.savez(
        root / "q_image" / "qimg_sampleA.tif.npz",
        qimg=image,
        qx=np.linspace(-4, 4, 40),
        qz=np.linspace(-2, 6, 30),
    )
    np.savez(
        root / "qphi" / "qphi_sampleA.tif.npz",
        q=np.linspace(0.01, 7, 20),
        phi=np.linspace(-179, 179, 16),
        qphi=np.ones((16, 20)),
    )
    return root


def test_cms_giwaxs_opens_on_the_window_yugang_reviews(tmp_path):
    root = _giwaxs(tmp_path / "cms" / "proposal" / "Results" / "giwaxs")
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(root)
    app.run()

    assert not app.exception
    state = app.session_state
    assert (state["pyscattviz_giwaxs_b_qx_lo"], state["pyscattviz_giwaxs_b_qx_hi"]) == (0.0, 3.0)
    assert (state["pyscattviz_giwaxs_b_qz_lo"], state["pyscattviz_giwaxs_b_qz_hi"]) == (0.0, 3.0)
    assert (state["pyscattviz_giwaxs_c_q_lo"], state["pyscattviz_giwaxs_c_q_hi"]) == (0.5, 3.5)
    assert (state["pyscattviz_giwaxs_c_phi_lo"], state["pyscattviz_giwaxs_c_phi_hi"]) == (
        0.0,
        180.0,
    )
    # Explicit limits were asked for, so auto-fit stays out of the way.
    assert state["pyscattviz_giwaxs_auto_fit"] is False


def test_a_folder_without_a_beamline_starts_on_auto_fit(tmp_path):
    root = _giwaxs(tmp_path / "somewhere" / "Results" / "giwaxs")
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(root)
    app.run()

    assert not app.exception
    assert app.session_state["pyscattviz_giwaxs_auto_fit"] is True


def test_moving_from_one_beamline_to_the_other_reapplies_the_preset(tmp_path):
    smi = _giwaxs(tmp_path / "smi" / "p" / "Results" / "giwaxs")
    cms = _giwaxs(tmp_path / "cms" / "p" / "Results" / "giwaxs")

    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(smi)
    app.run()
    assert app.session_state["pyscattviz_giwaxs_auto_fit"] is True

    next(item for item in app.text_input if item.label.startswith("Data path")).set_value(str(cms))
    app.run()

    assert not app.exception
    assert app.session_state["pyscattviz_giwaxs_b_qx_hi"] == 3.0
    assert app.session_state["pyscattviz_giwaxs_auto_fit"] is False


def test_auto_fit_frames_the_q_image_on_its_data(tmp_path):
    """The SMI GISAXS complaint: a fixed window leaves the picture in a field of NaN."""

    root = _giwaxs(tmp_path / "smi" / "p" / "Results" / "giwaxs")
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(root)
    app.run()
    assert not app.exception
    assert app.session_state["pyscattviz_giwaxs_auto_fit"] is True

    from pyscattviz.app.components.scattering import frame_axis_ranges, index_frames

    index_frames.clear()
    row = index_frames(str(root)).iloc[0]
    ranges = frame_axis_ranges(row)
    # The axes run -4…4 and -2…6; the data occupies a box well inside that.
    assert -4.0 < ranges["qx"][0] and ranges["qx"][1] < 4.0
    assert -2.0 < ranges["qz"][0] and ranges["qz"][1] < 6.0
