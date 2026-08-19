"""Filename conventions the CMS and SMI reductions actually use.

These came from reading real output on my own machine rather than from the
layout I assumed. Each one broke something visible in the explorer.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from pyscattviz.app.components.scattering import index_frames, stem_of

PAGES_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"

FRAME = "AY_S5_D300_x9.900_y-0.600_20.00s_2310323_000000_saxs"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config")))
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(tmp_path_factory.mktemp("pyscattviz_output")))


def test_cms_qc_layout_variants_reduce_to_the_frame_stem():
    """CMS writes several QC layouts per frame; all belong to one frame."""

    for prefix in ("qc_", "qc_1panel_", "qc_4panel_", "qc_4panel_autoelevate_"):
        assert stem_of(f"{prefix}{FRAME}.tiff.png") == FRAME
    # The other products already agreed on that stem.
    assert stem_of(f"Cir_Avg_{FRAME}.tiff.csv") == FRAME
    assert stem_of(f"qimg_{FRAME}.tiff.npz") == FRAME
    assert stem_of(f"qphi_{FRAME}.tiff.npz") == FRAME


def test_a_qc_name_without_a_layout_tag_is_untouched():
    assert stem_of("qc_panelless_sample.tiff.png") == "panelless_sample"
    assert stem_of("qc_3d_printed_sample.tiff.png") == "3d_printed_sample"


@pytest.fixture
def cms_saxs(tmp_path):
    """One CMS transmission frame with the five QC layouts it really gets."""

    root = tmp_path / "saxs"
    for product in ("cir_avg", "q_image", "qphi", "qc"):
        (root / product).mkdir(parents=True)

    q = np.logspace(-2, -0.5, 20)
    pd.DataFrame({"q_ca": q, "iq_ca": q**-2}).to_csv(
        root / "cir_avg" / f"Cir_Avg_{FRAME}.tiff.csv", index=False
    )
    np.savez(
        root / "q_image" / f"qimg_{FRAME}.tiff.npz",
        qimg=np.ones((6, 8)),
        qx=np.linspace(-0.2, 0.2, 8),
        qz=np.linspace(-0.3, 0.18, 6),
    )
    np.savez(
        root / "qphi" / f"qphi_{FRAME}.tiff.npz",
        q=np.linspace(0.006, 0.25, 10),
        phi=np.linspace(-179, 179, 12),
        qphi=np.ones((12, 10)),
    )
    from PIL import Image

    for prefix in ("qc_", "qc_1panel_", "qc_2panel_", "qc_4panel_", "qc_4panel_autoelevate_"):
        Image.fromarray(np.zeros((4, 4), dtype=np.uint8)).save(
            root / "qc" / f"{prefix}{FRAME}.tiff.png"
        )
    return root


def test_qc_variants_do_not_become_frames_of_their_own(cms_saxs):
    index_frames.clear()
    table = index_frames(str(cms_saxs))

    # Five QC files plus one of each other product used to index as six frames,
    # five of which had no circular average, no q-image, and no q–φ map.
    assert len(table) == 1
    row = table.iloc[0]
    assert row["stem"] == FRAME
    assert bool(row["has_cir"]) and bool(row["has_qimg"])
    assert bool(row["has_qphi"]) and bool(row["has_qc"])


def test_the_plain_qc_image_is_the_one_kept(cms_saxs):
    index_frames.clear()
    table = index_frames(str(cms_saxs))
    # Directory order is arbitrary, so the choice has to be deterministic.
    assert Path(table.iloc[0]["qc"]).name == f"qc_{FRAME}.tiff.png"


def test_the_explorer_shows_every_panel_for_such_a_frame(cms_saxs):
    app = AppTest.from_file(str(PAGES_DIR / "06_Transmission_SAXS.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(cms_saxs)
    app.run()

    assert not app.exception
    messages = " ".join(item.value for item in app.info)
    assert "No qphi map" not in messages
    assert "No circular average" not in messages


def test_a_calibration_only_folder_says_so(tmp_path):
    """A beamtime's AgBH scans often live alone in their own folder."""

    root = tmp_path / "waxs"
    (root / "cir_avg").mkdir(parents=True)
    (root / "cir_avg" / "Cir_Avg_AgBH_cali_5m_17kev_2310074_000000_waxs.tiff.csv").write_text(
        "q_ca,iq_ca\n0.01,10\n0.1,2\n"
    )

    app = AppTest.from_file(str(PAGES_DIR / "07_Transmission_WAXS.py"), default_timeout=120)
    app.session_state["pyscattviz_active_root"] = str(root)
    app.run()

    assert not app.exception
    warned = " ".join(item.value for item in app.warning)
    assert "calibration scans" in warned
    assert "Hide calibration" in warned


def test_charts_render_without_a_streamlit_deprecation_warning(cms_saxs):
    """st.plotly_chart has no `width` parameter; passing one was deprecated."""

    app = AppTest.from_file(str(PAGES_DIR / "06_Transmission_SAXS.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(cms_saxs)
    app.run()

    assert not app.exception
    assert app.get("plotly_chart")
    assert not any("deprecated" in item.value.lower() for item in app.warning)


def test_an_unreadable_qc_image_is_reported_rather_than_raised(cms_saxs):
    """st.image decodes the file itself, so PIL raises straight out of it."""

    for path in (cms_saxs / "qc").glob("*.png"):
        path.write_bytes(b"")

    app = AppTest.from_file(str(PAGES_DIR / "06_Transmission_SAXS.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(cms_saxs)
    app.run()

    # The QC panel starts unchecked, so ask for it explicitly.
    next(item for item in app.checkbox if item.label.startswith("QC image")).set_value(True)
    app.run()

    assert not app.exception
    assert any("could not be read" in item.value for item in app.error)
