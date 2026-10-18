"""A small CMS experiment on disk, laid out as the beamline and the
reduction write it, for the Org tests.

    demo_run/1_Static/waxs_temp/    static GIWAXS, pos1/pos2 raw, stitched + products
    demo_run/1_Static/saxs/         one raw AgBH, nothing reduced
    demo_run/2_Humidity/maxs/       two humidity runs (``…_70C`` and ``…_70C_2nd``),
                                    one frame not reduced yet, a dead T sensor
    demo_run/3_spincoating/maxs/    one spin: one scan, 5 frames
    demo_run/3_spincoating/spin_D/maxs/raw/   the spin's own raw folder (not a product)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import PIL.Image

Q = np.linspace(0.05, 3.0, 60)

STATIC = [
    # sample, pos, x, th, scan
    ("film_A1", 2, "+0.000", "+0.080", 1000600),
    ("film_A1", 2, "+0.000", "+0.100", 1000601),
    ("film_A1", 2, "+0.000", "+0.100", 1000605),  # a repeat
    ("film_A10", 2, "+0.000", "+0.100", 1000700),
    ("film_B1", 2, "-3.001", "+0.100", 1000800),
]
HUMID = [
    # series, idx, elapsed, th, RH, T, scan
    ("film_C_humid_70C", 1, "10.0", "+0.100", "40.100", "70.010", 1002001),
    ("film_C_humid_70C", 2, "70.0", "+0.100", "45.200", "70.020", 1002002),
    ("film_C_humid_70C", 3, "130.0", "+0.100", "50.300", "70.000", 1002003),
    ("film_C_humid_70C", 4, "190.0", "+0.500", "55.400", "-273.150", 1002004),
    ("film_C_humid_70C_2nd", 1, "15.0", "+0.100", "661.095", "70.000", 1002101),
    ("film_C_humid_70C_2nd", 2, "75.0", "+0.100", "38.000", "70.000", 1002102),
]
SPIN = ("spin_D", "1786.0", "28.800", "0.500", "0.29", 1003176, 5)


def static_name(sample, pos, x, th, scan, *, stitched=True):
    tag = "_stitched" if stitched else ""
    return f"{sample}_pos{pos}_x{x}_th{th}_10.00s{tag}_{scan}_000000_waxs_temp.tiff"


def humid_name(series, idx, elapsed, th, rh, t, scan):
    return f"{series}_{idx}_{elapsed}s_x+0.000_th{th}_1.00s_RH{rh}_T{t}C_{scan}_000000_maxs.tiff"


def spin_name(frame):
    series, start, x, th, exposure, scan, _ = SPIN
    return f"{series}_{start}s_x{x}_th{th}_{exposure}s_{scan}_{frame:06d}_maxs.tiff"


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def write_products(analysis: Path, frame: str, scale: float, *, qc: bool = True) -> None:
    """The four products of one frame, small but real."""
    for sub in ("cir_avg", "q_image", "qphi", "qc"):
        (analysis / sub).mkdir(parents=True, exist_ok=True)
    iq = scale * (1.0 / Q**2 + 50 * np.exp(-(((Q - 1.4) / 0.05) ** 2)))
    lines = [",q_ca,iq_ca"] + [f"{i},{q!r},{v!r}" for i, (q, v) in enumerate(zip(Q, iq))]
    (analysis / "cir_avg" / f"Cir_Avg_{frame}.csv").write_text("\n".join(lines) + "\n")
    qx, qz = np.linspace(-0.2, 2.3, 30), np.linspace(-0.05, 3.0, 40)
    qimg = scale * (1 + np.add.outer(qz, qx) ** 2).astype(np.float32)
    np.savez(
        analysis / "q_image" / f"qimg_{frame}.npz",
        qimg=qimg,
        qx=qx,
        qz=qz,
        qimg_mask=np.ones(qimg.shape, bool),
    )
    phi = np.linspace(-179, 179, 36)
    np.savez(
        analysis / "qphi" / f"qphi_{frame}.npz",
        q=Q,
        phi=phi,
        qphi=scale * np.ones((phi.size, Q.size), np.float32),
        qphi_mask=np.ones((40, 30), bool),
    )
    if qc:
        PIL.Image.new("RGB", (40, 20), (200, 100, 50)).save(analysis / "qc" / f"qc_{frame}.png")


def make_experiment(base) -> Path:
    """Write the experiment under *base*; returns ``base/demo_run``."""
    root = Path(base) / "demo_run"
    waxs = root / "1_Static" / "waxs_temp"
    for k, (sample, pos, x, th, scan) in enumerate(STATIC):
        for raw_pos, shift in ((1, 0), (2, 6)):
            _touch(waxs / "raw" / static_name(sample, raw_pos, x, th, scan - shift, stitched=False))
        stitched = static_name(sample, pos, x, th, scan)
        _touch(waxs / "analysis" / "stitched" / stitched)
        if sample != "film_B1":  # the newest frame is not reduced yet
            write_products(waxs / "analysis", stitched, 1.0 + k)
    _touch(
        root
        / "1_Static"
        / "saxs"
        / "raw"
        / "AgBH_cali_5m_13.5kev_x-0.000_th+0.000_10.00s_1000110_000000_saxs.tiff"
    )

    maxs = root / "2_Humidity" / "maxs"
    for k, fields in enumerate(HUMID):
        name = humid_name(*fields)
        _touch(maxs / "raw" / name)
        if k != 3:  # one frame still to reduce
            write_products(maxs / "analysis", name, 1.0 + 0.1 * k)

    spin = root / "3_spincoating" / "maxs"
    for frame in range(SPIN[-1]):
        name = spin_name(frame)
        _touch(root / "3_spincoating" / SPIN[0] / "maxs" / "raw" / name)
        _touch(spin / "raw" / name)
        write_products(spin / "analysis", name, 1.0 + frame, qc=frame == 0)
    return root
