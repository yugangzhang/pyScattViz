"""Find and remove hot pixels in the reduced 2D products.

Every CMS and SMI detector carries a few pixels that read absurdly high
regardless of what the sample is doing. They survive the chip and beamstop
mask, and because the azimuthal average is a *mean*, one pixel reading 500,000
against a background of 100 moves a whole q bin. A 1D curve built from such a
map has a spike in it that looks like a peak.

pyScattViz is a viewer, so this works on the products it already reads — the
``q_image`` and ``qphi`` arrays — not on raw detector frames. Re-reducing from
raw belongs in pySAXSAI, whose ``codes/hot_pixels.py`` does the same job one
step earlier. Cleaning here is what lets the viewer's own line cuts, azimuthal
averages, and batch 1D export come out without the spikes.

Two tests, and the second is the one that matters:

**Local outlier.** A hot pixel is far above its own neighbourhood; a real
feature is locally smooth. The excess must be significant against counting
statistics *and* be a multiple of the local median, so neither a bright-but-
smooth beam centre nor a steep gradient at a module edge is flagged.

**Persistence.** A detector defect is hot in every frame; a sharp Bragg spot
from an oriented substrate is hot in one. On real CMS data a single-frame test
flags both — the permanently stuck pixel *and* the MXene reflections. Only
requiring a candidate to recur across frames separates them, so prefer
:func:`find_hot_pixels_stack` whenever more than one frame is to hand.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "apply_hot_mask",
    "azimuthal_average",
    "find_hot_pixels",
    "find_hot_pixels_stack",
    "hot_pixel_summary",
    "remove_hot_pixels",
]

DEFAULT_WINDOW = 5
DEFAULT_ZMAX = 8.0
DEFAULT_RATIO = 3.0
# Build the mask from frames of *different* samples and demand near-unanimity.
# A sharp reflection recurs through one sample's whole angle series, so a
# majority vote over a single sample flags it as a defect; over a stack that
# spans the beamtime it does not.
DEFAULT_PERSIST = 0.9


def _median_filter(image: np.ndarray, size: int) -> np.ndarray:
    """Local median, ignoring NaN, with a SciPy fast path."""

    try:
        from scipy.ndimage import median_filter
    except ImportError:  # pragma: no cover - SciPy is a declared dependency
        return _median_filter_numpy(image, size)
    filled = np.where(np.isfinite(image), image, np.nanmedian(image))
    return median_filter(filled, size=size, mode="nearest")


def _median_filter_numpy(image: np.ndarray, size: int) -> np.ndarray:
    half = size // 2
    padded = np.pad(image, half, mode="edge")
    out = np.empty_like(image)
    for row in range(image.shape[0]):
        for col in range(image.shape[1]):
            window = padded[row : row + size, col : col + size]
            out[row, col] = np.nanmedian(window)
    return out


def find_hot_pixels(
    image,
    *,
    window: int = DEFAULT_WINDOW,
    zmax: float = DEFAULT_ZMAX,
    ratio_min: float = DEFAULT_RATIO,
    abs_min: float | None = None,
) -> np.ndarray:
    """Flag isolated pixels far above their own neighbourhood.

    Two conditions, and a pixel must meet both:

    ``zmax``
        The excess over the local median must be significant against counting
        statistics, ``residual > zmax * sqrt(local_median)``. A single global
        threshold does not work here — a scattering pattern spans orders of
        magnitude, so the noise in a bright region dwarfs a real spike in a dim
        one.
    ``ratio_min``
        The pixel must also be at least this many times its local median. This
        is what stops a steep gradient — near the beamstop, or at a module edge
        — from being read as a spike. On real CMS data the significance test
        alone flagged a pixel sitting at 1.0x its neighbours.

    Returns a boolean array, True where the pixel looks hot. Non-finite pixels
    are never flagged; they are already excluded from every average.

    On a single frame this cannot tell a stuck pixel from a genuinely sharp
    reflection. Use :func:`find_hot_pixels_stack` when several frames exist.
    """

    array = np.asarray(image, dtype=float)
    if array.ndim != 2 or array.size == 0:
        return np.zeros(array.shape, dtype=bool)

    valid = np.isfinite(array)
    if not valid.any():
        return np.zeros(array.shape, dtype=bool)

    local = _median_filter(array, max(3, int(window)))
    residual = array - local
    scale = np.sqrt(np.maximum(np.abs(local), 1.0))

    hot = valid & (residual > float(zmax) * scale)
    if ratio_min:
        hot &= array > float(ratio_min) * np.maximum(local, np.finfo(float).eps)
    if abs_min is not None:
        hot &= array > float(abs_min)
    return hot


def find_hot_pixels_stack(
    images,
    *,
    window: int = DEFAULT_WINDOW,
    zmax: float = DEFAULT_ZMAX,
    ratio_min: float = DEFAULT_RATIO,
    abs_min: float | None = None,
    persist_frac: float = DEFAULT_PERSIST,
) -> tuple[np.ndarray, dict]:
    """Flag pixels that are hot in at least ``persist_frac`` of the frames.

    This is the test that separates a detector defect from a sharp reflection:
    the defect recurs at the same pixel whatever the sample, the reflection does
    not. Returns ``(mask, info)``; ``info`` carries ``frames``, ``votes`` (the
    per-pixel count), ``n_hot``, and ``per_frame``.
    """

    stack = [np.asarray(item, dtype=float) for item in images]
    stack = [item for item in stack if item.ndim == 2 and item.size]
    if not stack:
        return np.zeros((0, 0), dtype=bool), {"frames": 0, "n_hot": 0, "per_frame": []}
    shape = stack[0].shape
    stack = [item for item in stack if item.shape == shape]

    votes = np.zeros(shape, dtype=int)
    per_frame = []
    for frame in stack:
        hot = find_hot_pixels(frame, window=window, zmax=zmax, ratio_min=ratio_min, abs_min=abs_min)
        votes += hot
        per_frame.append(int(hot.sum()))

    needed = max(1, int(np.ceil(float(persist_frac) * len(stack))))
    mask = votes >= needed
    return mask, {
        "frames": len(stack),
        "votes": votes,
        "n_hot": int(mask.sum()),
        "per_frame": per_frame,
        "needed": needed,
    }


def apply_hot_mask(image, mask) -> np.ndarray:
    """Return a copy of ``image`` with the masked pixels set to NaN.

    NaN rather than zero: every average in this package uses ``nanmean``, so a
    NaN drops out of the calculation instead of pulling the bin towards zero.
    """

    array = np.asarray(image, dtype=float).copy()
    flags = np.asarray(mask, dtype=bool)
    if flags.shape == array.shape:
        array[flags] = np.nan
    return array


def remove_hot_pixels(
    image,
    *,
    window: int = DEFAULT_WINDOW,
    zmax: float = DEFAULT_ZMAX,
    ratio_min: float = DEFAULT_RATIO,
    abs_min: float | None = None,
    mask=None,
) -> np.ndarray:
    """Blank the hot pixels of one 2D product and return the cleaned copy.

    Pass ``mask`` to apply a defect mask worked out from a whole stack, which
    is the safer choice; without one the pixels are found in this frame alone.
    """

    array = np.asarray(image, dtype=float)
    flags = (
        np.asarray(mask, dtype=bool)
        if mask is not None
        else find_hot_pixels(array, window=window, zmax=zmax, ratio_min=ratio_min, abs_min=abs_min)
    )
    return apply_hot_mask(array, flags)


def hot_pixel_summary(image, mask) -> dict:
    """Describe what was removed, for a caption the user can judge."""

    array = np.asarray(image, dtype=float)
    flags = np.asarray(mask, dtype=bool)
    if flags.shape != array.shape or not flags.any():
        return {"count": 0, "max_removed": None, "fraction": 0.0}
    removed = array[flags]
    finite = array[np.isfinite(array)]
    return {
        "count": int(flags.sum()),
        "max_removed": float(np.nanmax(removed)) if removed.size else None,
        "median_kept": float(np.nanmedian(finite)) if finite.size else None,
        "fraction": float(flags.sum() / max(array.size, 1)),
    }


def azimuthal_average(caked, q, phi=None, phi_range=None) -> tuple[np.ndarray, np.ndarray]:
    """Average a q–φ map over an azimuthal window into a 1D I(q).

    ``caked`` is ``(n_phi, n_q)`` as the reduction writes it. NaN pixels — which
    is what a removed hot pixel becomes — are excluded from the mean rather than
    counted as zero. Returns ``(q, I)``.
    """

    array = np.asarray(caked, dtype=float)
    q_axis = np.asarray(q, dtype=float)
    if array.ndim != 2 or q_axis.size != array.shape[1]:
        raise ValueError("caked must be (n_phi, n_q) matching the q axis")

    rows = np.ones(array.shape[0], dtype=bool)
    if phi is not None and phi_range is not None:
        phi_axis = np.asarray(phi, dtype=float)
        if phi_axis.size == array.shape[0]:
            low, high = float(phi_range[0]), float(phi_range[1])
            rows = (phi_axis >= low) & (phi_axis <= high)
            if not rows.any():
                rows = np.ones(array.shape[0], dtype=bool)

    selected = array[rows, :]
    with np.errstate(invalid="ignore"):
        intensity = np.where(
            np.isfinite(selected).any(axis=0),
            np.nanmean(np.where(np.isfinite(selected), selected, np.nan), axis=0),
            np.nan,
        )
    return q_axis, intensity
