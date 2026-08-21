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
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config")))


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
        stem = f"sampleA_runA_th{angle}deg_2026_08_01_12_00_0{index}"
        pd.DataFrame({"q_ca": Q, "iq_ca": (index + 1) * Q**-2}).to_csv(
            root / "cir_avg" / f"Cir_Avg_{stem}.tif.csv", index=False
        )
    first = "sampleA_runA_th0.1000deg_2026_08_01_12_00_00"
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


FIRST = "sampleA_runA_th0.1000deg_2026_08_01_12_00_00"


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
    row = _frame(giwaxs, "sampleA_runA_th0.1500deg_2026_08_01_12_00_01")
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


def _tick(app, key, value=True):
    app.session_state[key] = value
    app.run()
    return app


def test_the_batch_writes_the_panels_that_were_ticked(giwaxs, output_root):
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=600)
    app.session_state["pyscattviz_active_root"] = str(giwaxs)
    app.run()
    assert not app.exception

    app.session_state["pyscattviz_giwaxs_bp_iq"] = False
    app.session_state["pyscattviz_giwaxs_bp_manifest"] = False
    app.session_state["pyscattviz_giwaxs_bp_panels"] = True
    app.run()
    next(
        item for item in app.multiselect if item.key == "pyscattviz_giwaxs_bp_panel_list"
    ).set_value(["cir_avg"]).run()
    next(item for item in app.selectbox if item.key == "pyscattviz_giwaxs_bp_panel_fmt").set_value(
        "html"
    ).run()
    next(item for item in app.button if item.key == "pyscattviz_giwaxs_bp_run").click().run()

    assert not app.exception
    folder = output_root / "GIWAXS_Explorer" / "batch"
    written = sorted(path.name for path in folder.glob("*.html"))
    assert len(written) == 3, f"one per frame, got {written}"
    assert all("th0." in name for name in written)


def test_the_batch_applies_the_mask_to_every_frame(giwaxs, output_root):
    """The point of the panel: set the cleaning up once, apply it to the rest."""

    from pyscattviz.masking import MaskRegion, MaskSet

    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=600)
    app.session_state["pyscattviz_active_root"] = str(giwaxs)
    app.session_state["pyscattviz_giwaxs_maskset"] = MaskSet(
        "sub", [MaskRegion("ring", coords=(0.5, 0.7))]
    )
    app.run()
    assert not app.exception

    app.session_state["pyscattviz_giwaxs_bp_iq"] = True
    app.session_state["pyscattviz_giwaxs_bp_manifest"] = True
    app.run()
    next(item for item in app.button if item.key == "pyscattviz_giwaxs_bp_run").click().run()
    assert not app.exception

    folder = output_root / "GIWAXS_Explorer" / "batch"
    curves = sorted(folder.glob("*_Iq.csv"))
    # Only the first frame of this fixture carries a q–φ map, and I(q) is built
    # from that map — a frame without one is passed over rather than faked.
    assert len(curves) == 1, f"expected the one frame with a q–φ map, got {curves}"

    # Every curve must carry the gap the mask cut, not a zero.
    for path in curves:
        table = pd.read_csv(path)
        inside = (table["q"] >= 0.5) & (table["q"] <= 0.7)
        assert inside.any()
        assert table.loc[inside, "I"].isna().all(), f"{path.name} kept the masked ring"
        assert table.loc[~inside, "I"].notna().any()

    manifest = pd.read_csv(folder / "batch_manifest.csv")
    assert len(manifest) == 3, "the manifest records every frame, written or not"
    assert "masked region" in manifest["cleaning"].iloc[0]
    assert manifest["mask"].iloc[0] == "sub"


def test_nothing_ticked_writes_nothing(giwaxs, output_root):
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=600)
    app.session_state["pyscattviz_active_root"] = str(giwaxs)
    app.run()
    for name in ("iq", "iphi", "panels", "arrays", "manifest"):
        app.session_state[f"pyscattviz_giwaxs_bp_{name}"] = False
    app.run()

    assert not app.exception
    assert not any(item.key == "pyscattviz_giwaxs_bp_run" for item in app.button)


def test_the_dataset_basket_offers_folders_in_the_explorer_sidebar(giwaxs):
    other = giwaxs.parent / "gisaxs"
    (other / "cir_avg").mkdir(parents=True)
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=600)
    app.session_state["pyscattviz_active_root"] = str(giwaxs)
    app.session_state["pyscattviz_dataset_paths"] = [str(giwaxs), str(other)]
    app.run()

    assert not app.exception
    picker = next(item for item in app.selectbox if item.key == "pyscattviz_giwaxs_folder_pick")
    # The menu gathers recent folders, registered mounts, and the basket. It
    # shows the tail of each path, since a mounted drive makes them all alike.
    assert any(option.endswith("Results/giwaxs") for option in picker.options)
    assert any(option.endswith("Results/gisaxs") for option in picker.options)
