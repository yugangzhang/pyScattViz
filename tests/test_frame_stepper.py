"""Browsing frames with arrows, and the ordering problem behind them.

Streamlit refuses to change a widget's value after that widget has been
instantiated in the same run. The frame dropdown is created near the top of the
page and the arrows belong under the panels, so the arrows cannot touch the
dropdown directly — they queue a step which is consumed on the next run, before
the dropdown exists.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from pyscattviz.app.components.frames import apply_pending_step

PAGES_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config")))
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(tmp_path_factory.mktemp("pyscattviz_output")))


@pytest.fixture
def saxs(tmp_path):
    root = tmp_path / "saxs" / "analysis"
    (root / "cir_avg").mkdir(parents=True)
    (root / "qphi").mkdir()
    q = np.linspace(0.006, 0.3, 60)
    for index in range(5):
        stem = f"sample_{index:02d}_10.00s_24160{index:02d}_000000_saxs"
        pd.DataFrame({"q_ca": q, "iq_ca": (index + 1) * np.exp(-q)}).to_csv(
            root / "cir_avg" / f"Cir_Avg_{stem}.tiff.csv", index=False
        )
        np.savez(
            root / "qphi" / f"qphi_{stem}.tiff.npz",
            q=q,
            phi=np.linspace(-179, 179, 24),
            qphi=np.full((24, 60), 50.0),
        )
    return root


def test_a_queued_step_moves_one_frame():
    labels = ["a", "b", "c"]
    state = {"p_frame": "a", "p_frame_step": 1}

    import streamlit as st

    original = st.session_state
    try:
        st.session_state = state  # noqa: SLF001 - a plain dict is enough here
        apply_pending_step("p", labels)
    finally:
        st.session_state = original
    assert state["p_frame"] == "b"
    assert "p_frame_step" not in state, "the step must be consumed, not repeated"


def test_stepping_clamps_rather_than_wraps():
    """Running off the end and reappearing at the start looks like a data change."""

    import streamlit as st

    labels = ["a", "b", "c"]
    for start, step, expected in (("c", 1, "c"), ("a", -1, "a"), ("a", 99, "c"), ("c", -99, "a")):
        state = {"p_frame": start, "p_frame_step": step}
        original = st.session_state
        try:
            st.session_state = state
            apply_pending_step("p", labels)
        finally:
            st.session_state = original
        assert state["p_frame"] == expected, f"{start} {step:+d} → {state['p_frame']}"


def test_the_arrows_step_through_the_frames(saxs):
    app = AppTest.from_file(str(PAGES_DIR / "06_Transmission_SAXS.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(saxs)
    app.run()
    assert not app.exception

    def current():
        return app.session_state["pyscattviz_tsaxs_frame"]

    labels = [item for item in app.selectbox if item.key == "pyscattviz_tsaxs_frame"][0].options
    assert len(labels) == 5

    start = current()
    next(item for item in app.button if item.label == "▶").click().run()
    assert not app.exception
    assert current() == labels[labels.index(start) + 1]

    next(item for item in app.button if item.label == "◀").click().run()
    assert current() == start

    next(item for item in app.button if item.label == "⏭").click().run()
    assert current() == labels[-1]
    assert next(item for item in app.button if item.label == "⏭").disabled

    next(item for item in app.button if item.label == "⏮").click().run()
    assert current() == labels[0]
    assert next(item for item in app.button if item.label == "◀").disabled


def test_one_frame_gets_no_arrows(tmp_path):
    root = tmp_path / "saxs" / "analysis"
    (root / "cir_avg").mkdir(parents=True)
    q = np.linspace(0.006, 0.3, 40)
    pd.DataFrame({"q_ca": q, "iq_ca": np.exp(-q)}).to_csv(
        root / "cir_avg" / "Cir_Avg_only_10.00s_1_000000_saxs.tiff.csv", index=False
    )
    app = AppTest.from_file(str(PAGES_DIR / "06_Transmission_SAXS.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(root)
    app.run()

    assert not app.exception
    assert not any(item.label in ("◀", "▶") for item in app.button)


def test_the_qc_panel_exists_on_a_transmission_page(saxs):
    """It was offered as a product checkbox but had no panel, so ticking it did nothing."""

    (saxs / "qc").mkdir()
    from PIL import Image

    for path in (saxs / "cir_avg").glob("Cir_Avg_*.csv"):
        stem = path.name[len("Cir_Avg_") : -len(".csv")]
        Image.fromarray(np.full((12, 16, 3), 128, dtype=np.uint8)).save(
            saxs / "qc" / f"qc_{stem}.png"
        )

    app = AppTest.from_file(str(PAGES_DIR / "06_Transmission_SAXS.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(saxs)
    app.run()
    next(item for item in app.checkbox if item.label.startswith("QC image")).set_value(True).run()

    assert not app.exception
    assert not any("No QC image" in item.value for item in app.info)


def test_the_q_image_panel_has_its_own_limits(saxs):
    """Transmission never used to carry a q-image, so B had no controls at all."""

    (saxs / "q_image").mkdir()
    for path in (saxs / "cir_avg").glob("Cir_Avg_*.csv"):
        stem = path.name[len("Cir_Avg_") : -len(".csv")]
        np.savez(
            saxs / "q_image" / f"qimg_{stem}.npz",
            qimg=np.full((20, 24), 7.0),
            qx=np.linspace(-0.2, 0.2, 24),
            qz=np.linspace(-0.1, 0.3, 20),
        )

    app = AppTest.from_file(str(PAGES_DIR / "06_Transmission_SAXS.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(saxs)
    app.run()

    assert not app.exception
    keys = {item.key for item in app.number_input if item.key}
    for name in ("b_v_lo", "b_v_hi", "b_qx_lo", "b_qx_hi", "b_qz_lo", "b_qz_hi"):
        assert f"pyscattviz_tsaxs_{name}" in keys, f"missing the B control {name}"


def test_quick_plot_offers_the_full_figure_controls(tmp_path):
    """Same builder as Publication Plot, so it should have the same knobs."""

    folder = tmp_path / "curves"
    folder.mkdir()
    q = np.linspace(0.01, 2.0, 50)
    for index in range(2):
        pd.DataFrame({"q": q, "I": (index + 1) * np.exp(-q)}).to_csv(
            folder / f"curve_{index}.csv", index=False
        )

    app = AppTest.from_file(str(PAGES_DIR / "08_Quick_Plot.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(folder)
    app.session_state["quickplot_folder"] = str(folder)
    app.run()
    assert not app.exception

    keys = {item.key for item in app.number_input if item.key}
    keys |= {item.key for item in app.selectbox if item.key}
    keys |= {item.key for item in app.checkbox if item.key}
    # The ones Quick Plot never had: y limits, fonts, ticks, legend placement.
    for name in ("ylim_lo", "ylim_hi", "font_size", "tick_direction", "legend_loc"):
        assert f"quickplot_pub_{name}" in keys, f"Quick Plot is still missing {name}"
