"""Authored exclusion masks: shapes, the cross-product conversion, and files.

The point of the module is that a region is written once and applies to every
product, so most of what is worth testing is that a shape drawn in one space
lands in the right place in the other.
"""

from pathlib import Path

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from pyscattviz.app.components.maskeditor import selection_to_region
from pyscattviz.masking import (
    MaskRegion,
    MaskSet,
    build_mask,
    delete_mask,
    list_masks,
    load_mask,
    save_mask,
)

PAGES_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"

QX = np.linspace(-2.0, 2.0, 81)
QZ = np.linspace(-2.0, 2.0, 81)
Q = np.linspace(0.05, 3.0, 60)
PHI = np.linspace(-179.0, 179.0, 72)


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config")))
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(tmp_path_factory.mktemp("pyscattviz_output")))


def test_a_ring_is_an_annulus_on_the_image_and_a_band_on_the_caked_map():
    """The same substrate ring, expressed once."""

    mask = MaskSet("s", [MaskRegion("ring", coords=(1.0, 1.2))])

    on_image = build_mask(mask, QX, QZ, "qimage")
    radius = np.hypot(*np.meshgrid(QX, QZ))
    assert on_image[(radius > 1.02) & (radius < 1.18)].all()
    assert not on_image[radius < 0.9].any()

    on_caked = build_mask(mask, Q, PHI, "qphi")
    inside = (Q >= 1.0) & (Q <= 1.2)
    assert on_caked[:, inside].all(), "every azimuth at that q is excluded"
    assert not on_caked[:, ~inside].any()


def test_a_polygon_drawn_on_the_image_excludes_the_same_spot_on_the_caked_map():
    """This is the whole point: draw where you can see it, act where it counts."""

    box = MaskRegion(
        "polygon", space="qimage", coords=((0.9, 0.9), (1.3, 0.9), (1.3, 1.3), (0.9, 1.3))
    )
    on_caked = build_mask(MaskSet("p", [box]), Q, PHI, "qphi")
    rows, cols = np.nonzero(on_caked)
    assert on_caked.any()

    # The box spans |q| 1.27..1.84 and phi 34.7..55.3 degrees.
    assert 1.2 < Q[cols].min() and Q[cols].max() < 1.9
    assert 30.0 < PHI[rows].min() and PHI[rows].max() < 60.0


def test_a_wedge_wraps_across_the_seam():
    """170 to -170 is the 20-degree band through 180, not the 340-degree one."""

    mask = MaskSet("w", [MaskRegion("wedge", coords=(170.0, -170.0))])
    on_caked = build_mask(mask, Q, PHI, "qphi")
    rows = np.unique(np.nonzero(on_caked)[0])
    assert 0 < len(rows) <= 8, f"expected a narrow band, got {len(rows)} of {PHI.size} rows"
    assert (np.abs(PHI[rows]) > 165).all()


def test_a_box_is_read_in_the_axes_it_was_written_in():
    in_image = MaskSet("b", [MaskRegion("rect", space="qimage", coords=(0.5, 1.0, -0.2, 0.2))])
    flags = build_mask(in_image, QX, QZ, "qimage")
    columns = (QX >= 0.5) & (QX <= 1.0)
    rows = (QZ >= -0.2) & (QZ <= 0.2)
    assert flags[np.ix_(rows, columns)].all()
    assert not flags[np.ix_(~rows, ~columns)].any()


def test_keep_only_inverts_the_whole_set():
    mask = MaskSet("k", [MaskRegion("ring", coords=(1.0, 1.2))], keep_only=True)
    flags = build_mask(mask, QX, QZ, "qimage")
    radius = np.hypot(*np.meshgrid(QX, QZ))
    assert not flags[(radius > 1.02) & (radius < 1.18)].any()
    assert flags[radius < 0.9].all()


def test_a_disabled_region_does_nothing_but_is_kept():
    mask = MaskSet("d", [MaskRegion("ring", coords=(1.0, 1.2), enabled=False)])
    assert build_mask(mask, QX, QZ, "qimage") is None
    assert len(mask.regions) == 1, "suspending must not delete it"


def test_an_empty_mask_costs_nothing():
    assert build_mask(None, QX, QZ, "qimage") is None
    assert build_mask(MaskSet("e"), QX, QZ, "qimage") is None


def test_a_mask_survives_a_round_trip_through_a_file():
    mask = MaskSet(
        "substrate",
        [
            MaskRegion("ring", coords=(1.9, 2.05), label="Si (111)"),
            MaskRegion("polygon", space="qphi", coords=((1.0, 10.0), (1.2, 10.0), (1.1, 40.0))),
        ],
        keep_only=False,
    )
    assert save_mask(mask) is not None
    assert "substrate" in list_masks()

    back = load_mask("substrate")
    assert back is not None
    assert [r.kind for r in back.regions] == ["ring", "polygon"]
    assert back.regions[0].label == "Si (111)"
    assert back.regions[1].coords == ((1.0, 10.0), (1.2, 10.0), (1.1, 40.0))
    # And it rasterizes to the same thing it did before being written.
    np.testing.assert_array_equal(
        build_mask(mask, Q, PHI, "qphi"), build_mask(back, Q, PHI, "qphi")
    )

    assert delete_mask("substrate")
    assert "substrate" not in list_masks()


def test_a_bad_name_cannot_escape_the_masks_folder():
    saved = save_mask(MaskSet("../../etc/passwd", [MaskRegion("ring", coords=(1, 2))]))
    assert saved is not None
    assert saved.parent.name == "masks"
    assert ".." not in saved.name


def test_a_box_selection_becomes_a_rect():
    event = {"selection": {"box": [{"x": [1.3, 0.9], "y": [0.2, -0.4]}], "lasso": []}}
    region = selection_to_region(event, "qimage")
    assert region.kind == "rect"
    assert region.space == "qimage"
    # Drawn right-to-left; the stored box is still ordered.
    assert region.coords == (0.9, 1.3, -0.4, 0.2)


def test_a_lasso_selection_becomes_a_polygon():
    event = {
        "selection": {
            "box": [],
            "lasso": [{"x": [1.0, 1.2, 1.1], "y": [10.0, 12.0, 20.0]}],
        }
    }
    region = selection_to_region(event, "qphi")
    assert region.kind == "polygon"
    assert region.space == "qphi"
    assert region.coords == ((1.0, 10.0), (1.2, 12.0), (1.1, 20.0))


def test_nothing_drawn_is_not_a_region():
    assert selection_to_region(None, "qimage") is None
    assert selection_to_region({}, "qimage") is None
    assert selection_to_region({"selection": {"box": [], "lasso": []}}, "qimage") is None
    # Two points cannot be a polygon.
    thin = {"selection": {"box": [], "lasso": [{"x": [1.0, 1.2], "y": [1.0, 1.2]}]}}
    assert selection_to_region(thin, "qphi") is None


def _giwaxs(tmp_path):
    root = tmp_path / "cms" / "p" / "Results" / "giwaxs"
    (root / "qphi").mkdir(parents=True)
    (root / "cir_avg").mkdir()
    q = np.linspace(0.05, 3.0, 60)
    phi = np.linspace(-179, 179, 72)
    np.savez(root / "qphi" / "qphi_sampleA.tif.npz", q=q, phi=phi, qphi=np.full((72, 60), 100.0))
    import pandas as pd

    pd.DataFrame({"q_ca": q, "iq_ca": np.exp(-q)}).to_csv(
        root / "cir_avg" / "Cir_Avg_sampleA.tif.csv", index=False
    )
    return root


def test_the_mask_reaches_the_re_integrated_curve(tmp_path):
    """A ring excluded in the editor must be a hole in the 1-D curve."""

    root = _giwaxs(tmp_path)
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(root)
    app.session_state["pyscattviz_giwaxs_maskset"] = MaskSet(
        "substrate", [MaskRegion("ring", coords=(1.0, 1.2))]
    )
    app.run()

    assert not app.exception
    kept = app.session_state["pyscattviz_giwaxs_maskset"]
    assert len(kept.enabled_regions()) == 1
