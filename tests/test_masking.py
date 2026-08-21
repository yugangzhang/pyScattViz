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


def test_a_selection_chart_survives_a_second_run(tmp_path):
    """The crash Yugang hit: a chart with on_select is a widget like a button.

    `keep_widget_state` assigns every key back to itself so widget values
    survive a page change. A selection chart refuses that, and it refuses it at
    *widget creation*, so the page dies on the second render with
    StreamlitValueAssignmentNotAllowedError. `action_key` cannot save it either
    -- the chart registers itself far too late in the page -- which is why the
    skip is a suffix rule.

    AppTest does not populate the chart key by itself, so the state a real
    browser leaves behind after one render is seeded here by hand.
    """

    import pandas as pd

    root = tmp_path / "cms" / "p" / "Results" / "giwaxs"
    (root / "q_image").mkdir(parents=True)
    (root / "qphi").mkdir()
    (root / "cir_avg").mkdir()
    np.savez(
        root / "q_image" / "qimg_s.tif.npz",
        qimg=np.full((30, 40), 5.0),
        qx=np.linspace(-2, 2, 40),
        qz=np.linspace(-1, 3, 30),
        qimg_mask=np.zeros((30, 40), bool),
    )
    np.savez(
        root / "qphi" / "qphi_s.tif.npz",
        q=np.linspace(0.1, 3, 50),
        phi=np.linspace(-179, 179, 40),
        qphi=np.full((40, 50), 5.0),
    )
    q = np.linspace(0.1, 3, 50)
    pd.DataFrame({"q_ca": q, "iq_ca": np.exp(-q)}).to_csv(
        root / "cir_avg" / "Cir_Avg_s.tif.csv", index=False
    )

    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(root)
    empty = {"selection": {"points": [], "box": [], "lasso": []}}
    app.session_state["pyscattviz_giwaxs_qimg_chart"] = empty
    app.session_state["pyscattviz_giwaxs_qphi_chart"] = empty

    for _ in range(3):
        app.run()
        assert not app.exception, [str(item.value) for item in app.exception]


def test_keep_widget_state_leaves_selection_charts_alone():
    """The rule itself, without a page around it."""

    from pyscattviz.app.state import keep_widget_state

    state = {
        "pyscattviz_giwaxs_cmap": "Turbo",
        "pyscattviz_giwaxs_qimg_chart": {"selection": {}},
        "pyscattviz_giwaxs_qphi_chart": {"selection": {}},
    }
    kept = keep_widget_state(state)
    assert kept == 1, "only the colormap should be re-asserted"


def _qphi_frame(tmp_path, value=100.0):
    root = tmp_path / "cms" / "p" / "Results" / "giwaxs"
    (root / "qphi").mkdir(parents=True)
    (root / "cir_avg").mkdir()
    q = np.linspace(0.05, 3.0, 60)
    phi = np.linspace(-179, 179, 72)
    np.savez(root / "qphi" / "qphi_sampleA.tif.npz", q=q, phi=phi, qphi=np.full((72, 60), value))
    import pandas as pd

    pd.DataFrame({"q_ca": q, "iq_ca": np.exp(-q)}).to_csv(
        root / "cir_avg" / "Cir_Avg_sampleA.tif.csv", index=False
    )
    return root, q, phi


def _reintegrated(app):
    """The re-integrated trace from panel D, or (None, None)."""

    import streamlit as stmod
    from streamlit.delta_generator import DeltaGenerator

    captured = []
    for obj, is_cls in ((DeltaGenerator, True), (stmod, False)):
        original = obj.plotly_chart

        def spy(*args, original=original, is_cls=is_cls, **kwargs):
            captured.append(args[1] if is_cls else args[0])
            return original(*args, **kwargs)

        obj.plotly_chart = spy
    try:
        app.run()
    finally:
        pass
    for figure in captured:
        if "circular average" in str(getattr(figure.layout.title, "text", "") or ""):
            for trace in figure.data:
                if "re-integrated" in (trace.name or ""):
                    return np.asarray(trace.x, float), np.asarray(trace.y, float)
    return None, None


def test_the_curve_is_re_integrated_even_with_hot_pixel_removal_off(tmp_path):
    """It used to be gated on the hot-pixel toggle, so a mask alone did nothing."""

    root, _q, _phi = _qphi_frame(tmp_path)
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(root)
    app.session_state["pyscattviz_giwaxs_hot_enabled"] = False

    q_axis, intensity = _reintegrated(app)
    assert q_axis is not None, "no re-integrated curve with hot-pixel removal off"
    assert np.isfinite(intensity).all()
    assert np.allclose(intensity[np.isfinite(intensity)], 100.0)


def test_a_masked_ring_is_a_gap_in_the_curve_not_a_zero(tmp_path):
    """NaN, so the bin drops out of the mean rather than dragging it down."""

    root, q, _phi = _qphi_frame(tmp_path)
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(root)
    app.session_state["pyscattviz_giwaxs_hot_enabled"] = False
    app.session_state["pyscattviz_giwaxs_maskset"] = MaskSet(
        "sub", [MaskRegion("ring", coords=(1.0, 1.2))]
    )

    q_axis, intensity = _reintegrated(app)
    assert q_axis is not None
    inside = (q_axis >= 1.0) & (q_axis <= 1.2)
    assert np.isnan(intensity[inside]).all(), "the masked ring must be a gap"
    assert not np.isnan(intensity[~inside]).any(), "and nothing else may be touched"
    assert (intensity[~inside] == 100.0).all(), "a zero here would be a trench, not a gap"


def test_a_sector_average_uses_only_the_chosen_azimuth(tmp_path):
    """The phi window turns the same control into a sector average."""

    root = tmp_path / "cms" / "p" / "Results" / "giwaxs"
    (root / "qphi").mkdir(parents=True)
    (root / "cir_avg").mkdir()
    q = np.linspace(0.05, 3.0, 60)
    phi = np.linspace(-179, 179, 72)
    # Broadcast explicitly: phi[:, None] alone gives an (nphi, 1) map, which
    # is not a q–φ map at all.
    caked = np.where(np.broadcast_to(phi[:, None], (phi.size, q.size)) >= 0, 200.0, 100.0)
    np.savez(root / "qphi" / "qphi_sampleA.tif.npz", q=q, phi=phi, qphi=caked)
    import pandas as pd

    pd.DataFrame({"q_ca": q, "iq_ca": np.exp(-q)}).to_csv(
        root / "cir_avg" / "Cir_Avg_sampleA.tif.csv", index=False
    )

    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=300)
    app.session_state["pyscattviz_active_root"] = str(root)
    app.session_state["pyscattviz_giwaxs_hot_enabled"] = False
    app.session_state["pyscattviz_giwaxs_reint_phi_lo"] = 0.0
    app.session_state["pyscattviz_giwaxs_reint_phi_hi"] = 179.0

    _q_axis, intensity = _reintegrated(app)
    kept = intensity[np.isfinite(intensity)]
    assert kept.size
    assert np.allclose(kept, 200.0), "the upper half only, not the average of both"


def test_a_wrongly_shaped_map_skips_the_cut_instead_of_killing_the_page():
    """A product written with the wrong shape is a real thing to meet."""

    from pyscattviz.app.components.scattering import band_profile

    q = np.linspace(0.05, 3.0, 60)
    phi = np.linspace(-179, 179, 72)
    good = np.full((phi.size, q.size), 5.0)
    assert band_profile(good, phi, q, 1.0, 0.2) is not None

    # (nphi, 1) — what an accidental broadcast produces.
    assert band_profile(np.full((phi.size, 1), 5.0), phi, q, 1.0, 0.2) is None
    assert band_profile(np.full(q.size, 5.0), phi, q, 1.0, 0.2) is None


def test_the_batch_uses_the_same_cleaning_as_the_panels():
    """One implementation, so a batch cannot drift from what was on screen."""

    from pyscattviz.app.components.cleaning import Cleaning
    from pyscattviz.app.components.hotpixels import HotPixelSettings

    q = np.linspace(0.05, 3.0, 60)
    phi = np.linspace(-179, 179, 72)
    caked = np.full((phi.size, q.size), 100.0)

    cleaning = Cleaning(
        hot=HotPixelSettings(enabled=False),
        mask=MaskSet("s", [MaskRegion("ring", coords=(1.0, 1.2))]),
    )
    cleaned = cleaning.clean(caked, q, phi, "qphi")
    inside = (q >= 1.0) & (q <= 1.2)
    assert np.isnan(cleaned[:, inside]).all()
    assert (cleaned[:, ~inside] == 100.0).all()


def test_iphi_averages_across_q_and_iq_averages_across_phi():
    """The two reductions the four techniques between them ask for."""

    from pyscattviz.app.components.cleaning import Cleaning
    from pyscattviz.app.components.hotpixels import HotPixelSettings

    q = np.linspace(0.05, 3.0, 60)
    phi = np.linspace(-179, 179, 72)
    # Intensity that depends only on phi, so the two reductions are tellable.
    caked = np.broadcast_to(np.where(phi[:, None] >= 0, 200.0, 100.0), (phi.size, q.size))

    cleaning = Cleaning(hot=HotPixelSettings(enabled=False), mask=MaskSet("e"))
    row = {"qphi": "unused", "has_qphi": True}

    # Patch the loader so this stays a unit test.
    import pyscattviz.app.components.cleaning as module

    original = module.load_qphi
    module.load_qphi = lambda _path: (q, phi, np.array(caked), None)
    try:
        q_axis, iq, _info = cleaning.curve(row)
        phi_axis, iphi, _info2 = cleaning.profile(row)
        upper, _iq_upper, _i = cleaning.curve(row, (0.0, 179.0))
    finally:
        module.load_qphi = original

    assert q_axis.size == q.size
    assert np.allclose(iq, 150.0), "averaging over the whole azimuth mixes both halves"
    assert phi_axis.size == phi.size
    assert np.allclose(iphi[phi >= 0], 200.0) and np.allclose(iphi[phi < 0], 100.0)
    assert upper is not None
