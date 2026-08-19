"""Axis limits come from the frame, not from a constant I guessed once.

The q a reduction covers depends on the detector, its distance, and the photon
energy. Measuring real CMS and SMI output showed the old fixed defaults clipped
most of it: a GIWAXS q–φ map that reaches 7 A^-1 was cut at 3, transmission WAXS
reaches 9 and was cut at 3.5, every q-image has negative qz that a 0-based
minimum hid, and phi runs -179 … +179 rather than 0 … 180.
"""

from pathlib import Path

import numpy as np
import pytest

from pyscattviz.app.components.scattering import frame_axis_ranges, index_frames


@pytest.fixture
def frame(tmp_path):
    """One frame carrying the axis conventions the real reduction writes."""

    root = tmp_path / "giwaxs"
    (root / "q_image").mkdir(parents=True)
    (root / "qphi").mkdir()
    (root / "cir_avg").mkdir()
    stem = "sample_th0.1000deg"

    rng = np.random.default_rng(0)
    np.savez(
        root / "q_image" / f"qimg_{stem}.tif.npz",
        qimg=np.abs(rng.normal(10, 2, (24, 30))),
        # Negative qz is normal and a 0-based default used to hide it.
        qx=np.linspace(-1.6, 4.3, 30),
        qz=np.linspace(-1.2, 5.5, 24),
    )
    np.savez(
        root / "qphi" / f"qphi_{stem}.tif.npz",
        q=np.linspace(0.002, 7.0, 20),
        phi=np.linspace(-179.7, 179.8, 16),
        qphi=np.abs(rng.normal(5, 1, (16, 20))),
    )
    q = np.logspace(-2, np.log10(6.585), 40)
    (root / "cir_avg" / f"Cir_Avg_{stem}.tif.csv").write_text(
        "q_ca,iq_ca\n" + "\n".join(f"{a:.6g},{b:.6g}" for a, b in zip(q, q**-2))
    )
    index_frames.clear()
    return index_frames(str(root)).iloc[0]


def test_measured_ranges_cover_the_whole_axis(frame):
    ranges = frame_axis_ranges(frame)

    assert ranges["qx"] == pytest.approx((-1.6, 4.3))
    assert ranges["qz"] == pytest.approx((-1.2, 5.5))
    assert ranges["qphi_q"] == pytest.approx((0.002, 7.0))
    assert ranges["phi"] == pytest.approx((-179.7, 179.8))
    assert ranges["cir_q"][1] == pytest.approx(6.585, rel=1e-3)


def test_the_measured_ranges_are_the_ones_a_fixed_window_would_clip(frame):
    ranges = frame_axis_ranges(frame)

    # This frame is filled everywhere, so the data box is the whole axis.
    assert ranges["qx"][1] > 3.0, "qx reaches past a +3 limit"
    assert ranges["qz"][0] < 0.0, "qz goes negative; a 0 minimum would hide it"
    assert ranges["qz"][1] > 3.0
    assert ranges["qphi_q"][1] > 3.0
    assert ranges["phi"][0] < 0.0, "phi goes negative; a 0…180 window hides half"


def test_a_missing_or_unreadable_product_is_simply_absent(tmp_path):
    root = tmp_path / "giwaxs"
    (root / "cir_avg").mkdir(parents=True)
    (root / "q_image").mkdir()
    (root / "cir_avg" / "Cir_Avg_only.tif.csv").write_text("q_ca,iq_ca\n0.01,5\n0.4,1\n")
    (root / "q_image" / "qimg_only.tif.npz").write_bytes(b"not an archive")
    index_frames.clear()
    row = index_frames(str(root)).iloc[0]

    ranges = frame_axis_ranges(row)
    assert ranges["cir_q"] == pytest.approx((0.01, 0.4))
    assert "qx" not in ranges and "qphi_q" not in ranges


def test_the_qr_axis_is_reported_when_that_view_is_selected(tmp_path):
    root = tmp_path / "giwaxs"
    (root / "q_image").mkdir(parents=True)
    np.savez(
        root / "q_image" / "qimg_sample.tif.npz",
        qimg=np.ones((5, 7)),
        qx=np.linspace(-1, 1, 7),
        qr=np.linspace(0, 2, 7),
        qz=np.linspace(0, 1, 5),
    )
    index_frames.clear()
    row = index_frames(str(root)).iloc[0]

    assert frame_axis_ranges(row, "qx")["qx"] == pytest.approx((-1.0, 1.0))
    assert frame_axis_ranges(row, "qr")["qr"] == pytest.approx((0.0, 2.0))


# ---------------------------------------------------------------------------
# The same check against the real CMS/SMI products, when they are present.
# ---------------------------------------------------------------------------
REAL_RESULTS = Path.home() / "Repos" / "pySAXSAI" / "results"
REAL_CASES = [
    ("cms/gisaxs/2026C1_Murray", 0.5),
    ("cms/giwaxs/2026C1_QYu", 3.0),
    ("smi/giwaxs/2026C1_FLu", 3.0),
    ("smi/twaxs/2026C1_FLu", 3.5),
]


@pytest.mark.parametrize(("dataset", "old_q_max"), REAL_CASES)
def test_real_beamline_output_needs_more_than_the_old_defaults(dataset, old_q_max):
    folder = REAL_RESULTS / dataset
    if not folder.is_dir():
        pytest.skip(f"{folder} is not on this computer")

    index_frames.clear()
    table = index_frames(str(folder))
    if table.empty:
        pytest.skip(f"{folder} holds no indexable frame")
    row = table.iloc[0]
    ranges = frame_axis_ranges(row)

    # The reduction writes phi over -179 … +179. frame_axis_ranges reports where
    # the data actually is, which can be a subset, so check the axis itself.
    if row.get("qphi"):
        with np.load(row["qphi"]) as archive:
            if "phi" in archive.files:
                assert float(archive["phi"].min()) < -90, (
                    f"{dataset}: the reduction writes phi negative; 0…180 hides half"
                )
    covered = max(span[1] for key, span in ranges.items() if key in {"qphi_q", "cir_q", "qz"})
    if "giwaxs" in dataset or "twaxs" in dataset:
        assert covered > old_q_max, (
            f"{dataset}: reaches q={covered:.3g}, the old default stopped at {old_q_max}"
        )
