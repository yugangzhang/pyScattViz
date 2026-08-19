"""Safe data adapters and deterministic demos for the plotting studio."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image


def read_numeric_table(payload: bytes, filename: str) -> pd.DataFrame:
    """Read a CSV/TXT payload and retain columns containing numeric data."""

    suffix = Path(filename).suffix.lower()
    separator = "," if suffix == ".csv" else None
    try:
        table = pd.read_csv(
            io.BytesIO(payload),
            sep=separator,
            engine="python" if separator is None else "c",
        )
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise ValueError(f"Could not read {filename} as a numeric table.") from exc
    numeric = table.apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
    if numeric.empty:
        raise ValueError(f"{filename} contains no numeric columns.")
    return numeric


def read_array_bundle(payload: bytes, filename: str) -> dict[str, np.ndarray]:
    """Read a non-pickled NPY/NPZ, table, or image into named arrays."""

    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".npy":
            array = np.load(io.BytesIO(payload), allow_pickle=False)
            return {Path(filename).stem: np.asarray(array)}
        if suffix == ".npz":
            with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
                return {name: np.asarray(archive[name]) for name in archive.files}
        if suffix in {".csv", ".txt", ".dat"}:
            return {Path(filename).stem: read_numeric_table(payload, filename).to_numpy()}
        with Image.open(io.BytesIO(payload)) as image:
            array = np.asarray(image, dtype=float)
        if array.ndim == 3:
            array = array[..., :3].mean(axis=2)
        return {Path(filename).stem: array}
    except (OSError, ValueError, KeyError) as exc:
        raise ValueError(f"Could not read a numeric array from {filename}.") from exc


def two_dimensional_arrays(bundle: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Return numeric two-dimensional arrays from a bundle."""

    return {
        name: np.asarray(value, dtype=float)
        for name, value in bundle.items()
        if np.asarray(value).ndim == 2
    }


def demo_curve_table(points: int = 500) -> pd.DataFrame:
    """Return deterministic scattering-like curves for an immediate preview."""

    q = np.logspace(-3, 0, points)
    return pd.DataFrame(
        {
            "q": q,
            "power_law": 2.5e-2 * q**-2.2 + 0.2,
            "broad_peak": 30 * np.exp(-(((q - 0.18) / 0.045) ** 2)) + 0.8,
            "structure_factor": 6 + 3 * np.sin(55 * q) ** 2 * np.exp(-2 * q),
        }
    )


def demo_image(size: int = 220) -> np.ndarray:
    """Return a deterministic reciprocal-space-like intensity image."""

    x = np.linspace(-1.2, 1.2, size)
    y = np.linspace(0.0, 1.8, int(size * 0.8))
    xx, yy = np.meshgrid(x, y)
    ring = np.exp(-(((np.sqrt(xx**2 + (yy - 0.15) ** 2) - 0.72) / 0.045) ** 2))
    horizon = np.exp(-(((yy - 0.12) / 0.035) ** 2)) * np.exp(-((xx / 0.65) ** 2))
    lobes = np.exp(-((xx / 0.12) ** 2 + ((yy - 0.9) / 0.42) ** 2))
    return 1.0 + 1200 * ring + 700 * horizon + 400 * lobes
