"""Transmission layout, the log-q axis range, and data-driven 1D limits.

All three came from a CMS transmission SAXS folder where the q–φ panel came out
blank and the layout left a hole where the raw image would have been.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from pyscattviz.app.components.scattering import (
    frame_axis_ranges,
    heatmap_fig,
    index_frames,
    intensity_limits_in_window,
)
from pyscattviz.despike import DEFAULT_RATIO, DEFAULT_WINDOW, DEFAULT_ZMAX

PAGES_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config")))
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(tmp_path_factory.mktemp("pyscattviz_output")))


def test_a_log_axis_range_is_given_in_log_units():
    """Passing raw q drew the panel at 10^0.001 … 10^0.5, i.e. 1 … 3 A^-1."""

    z = np.ones((4, 6))
    q = np.linspace(0.006, 0.25, 6)
    phi = np.linspace(-179, 179, 4)

    figure = heatmap_fig("q–φ", z, q, phi, "q", "φ", xlog=True, x_range=(0.001, 0.5))
    low, high = figure.layout.xaxis.range
    assert 10**low == pytest.approx(0.001)
    assert 10**high == pytest.approx(0.5)
    # The data has to fall inside the drawn window, or the panel is empty.
    assert 10**low <= q.min() and 10**high >= q.max()


def test_a_linear_axis_range_is_left_alone():
    figure = heatmap_fig(
        "q–φ",
        np.ones((4, 6)),
        np.linspace(0, 3, 6),
        np.linspace(0, 180, 4),
        "q",
        "φ",
        xlog=False,
        x_range=(0.0, 3.0),
    )
    assert tuple(figure.layout.xaxis.range) == pytest.approx((0.0, 3.0))


@pytest.fixture
def transmission(tmp_path):
    """A CMS-like transmission folder: no stitched raw image, as is normal."""

    root = tmp_path / "saxs" / "analysis"
    (root / "cir_avg").mkdir(parents=True)
    (root / "qphi").mkdir()
    (root / "q_image").mkdir()

    # Signal only over part of the recorded q range, as a real SAXS curve is.
    q = np.linspace(0.0056, 0.31, 400)
    intensity = 3000.0 * np.exp(-((q / 0.02) ** 2)) + 0.01
    intensity[q > 0.25] = 0.0
    pd.DataFrame({"q_ca": q, "iq_ca": intensity}).to_csv(
        root / "cir_avg" / "Cir_Avg_sampleA.tiff.csv", index=False
    )
    np.savez(
        root / "qphi" / "qphi_sampleA.tiff.npz",
        q=np.linspace(0.0062, 0.2498, 120),
        phi=np.linspace(-179, 179, 60),
        qphi=np.abs(np.random.default_rng(0).normal(50, 5, (60, 120))),
    )
    np.savez(
        root / "q_image" / "qimg_sampleA.tiff.npz",
        qimg=np.abs(np.random.default_rng(1).normal(50, 5, (40, 50))),
        qx=np.linspace(-0.2, 0.2, 50),
        qz=np.linspace(-0.2, 0.2, 40),
    )
    return root


def test_the_1d_limits_come_from_where_the_signal_is(transmission):
    index_frames.clear()
    row = index_frames(str(transmission)).iloc[0]
    ranges = frame_axis_ranges(row)

    # The file runs to q = 0.31 but dies at 0.25; it starts at 0.0056, not 0.001.
    assert ranges["cir_q"][0] == pytest.approx(0.0056, abs=1e-3)
    assert ranges["cir_q"][1] < 0.26
    assert ranges["cir_I"][0] > 0


def test_only_the_panels_that_exist_are_drawn(transmission):
    """The fixed A/B/C/D grid left the first cell empty for transmission data."""

    app = AppTest.from_file(str(PAGES_DIR / "06_Transmission_SAXS.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(transmission)
    app.run()

    assert not app.exception
    # cir_avg, qphi and q_image are present; stitched is not, and no slot is
    # reserved for it.
    assert len(app.get("plotly_chart")) >= 3
    assert not any("No raw image" in item.value for item in app.info)


def test_a_selected_but_missing_product_is_named_not_left_blank(transmission):
    import shutil

    shutil.rmtree(transmission / "q_image")
    app = AppTest.from_file(str(PAGES_DIR / "06_Transmission_SAXS.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(transmission)
    app.run()
    assert not app.exception


def test_the_despike_toggle_is_on_by_default(transmission):
    app = AppTest.from_file(str(PAGES_DIR / "06_Transmission_SAXS.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(transmission)
    app.run()

    assert not app.exception
    assert app.session_state["pyscattviz_tsaxs_hot_enabled"] is True
    assert any("Remove hot pixels" in item.label for item in app.checkbox)


def test_the_hot_pixel_thresholds_are_on_screen(transmission):
    """The thresholds must be adjustable, not baked into the checkbox."""

    app = AppTest.from_file(str(PAGES_DIR / "06_Transmission_SAXS.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(transmission)
    app.run()

    assert not app.exception
    prefix = "pyscattviz_tsaxs_hot"
    assert app.session_state[f"{prefix}_window"] == DEFAULT_WINDOW
    assert app.session_state[f"{prefix}_zmax"] == DEFAULT_ZMAX
    assert app.session_state[f"{prefix}_ratio"] == DEFAULT_RATIO

    # And changing one must survive into the settings the page acts on.
    app.session_state[f"{prefix}_zmax"] = 20.0
    app.session_state[f"{prefix}_ratio"] = 12.0
    app.run()
    assert not app.exception
    assert app.session_state[f"{prefix}_zmax"] == 20.0


def test_the_batch_offers_both_q_phi_reductions(transmission):
    """Transmission wants I(q) and I(φ): the average over φ and the one over q."""

    app = AppTest.from_file(str(PAGES_DIR / "06_Transmission_SAXS.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(transmission)
    app.run()

    assert not app.exception
    keys = {item.key for item in app.checkbox if item.key}
    assert "pyscattviz_tsaxs_bp_iq" in keys
    assert "pyscattviz_tsaxs_bp_iphi" in keys
    # And a transmission page opens with both ticked, since both are the point.
    assert app.session_state["pyscattviz_tsaxs_bp_iq"] is True
    assert app.session_state["pyscattviz_tsaxs_bp_iphi"] is True


def test_the_intensity_limits_follow_the_chosen_q_window():
    """Choosing a q range by hand must rescale I, or the zoom is a flat line."""

    q = np.linspace(0.006, 0.31, 400)
    intensity = 3000.0 * np.exp(-((q / 0.02) ** 2)) + 0.01

    whole = intensity_limits_in_window(q, intensity)
    zoomed = intensity_limits_in_window(q, intensity, (0.05, 0.15))

    assert whole[1] > 1000  # the beam-centre decade dominates the full curve
    assert zoomed[1] < 100  # the window holds nothing like it
    assert zoomed[1] < whole[1] / 10


def test_an_empty_q_window_leaves_the_limits_alone():
    q = np.linspace(0.006, 0.31, 50)
    assert intensity_limits_in_window(q, np.ones_like(q), (5.0, 6.0)) is None


def test_auto_q_and_auto_intensity_are_separate_toggles(transmission):
    app = AppTest.from_file(str(PAGES_DIR / "06_Transmission_SAXS.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(transmission)
    app.run()

    assert not app.exception
    assert app.session_state["pyscattviz_tsaxs_auto_q"] is True
    assert app.session_state["pyscattviz_tsaxs_auto_i"] is True

    # Pin q by hand, keep the intensity automatic: the pinned window must stand.
    app.session_state["pyscattviz_tsaxs_auto_q"] = False
    app.session_state["pyscattviz_tsaxs_d_q_lo"] = 0.05
    app.session_state["pyscattviz_tsaxs_d_q_hi"] = 0.15
    app.run()

    assert not app.exception
    assert app.session_state["pyscattviz_tsaxs_d_q_lo"] == 0.05
    assert app.session_state["pyscattviz_tsaxs_d_q_hi"] == 0.15
