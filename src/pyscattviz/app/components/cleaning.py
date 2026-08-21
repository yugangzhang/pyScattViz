"""One place that decides what a frame looks like after cleaning.

Three things can remove data from a reduced product, and they answer different
questions:

* the reduction's own mask — chip gaps, the beamstop, what the detector never saw;
* **hot pixels** — is this a detector defect? (:mod:`pyscattviz.despike`);
* an **exclusion mask** — do I want this region in my average? (:mod:`pyscattviz.masking`).

They have to be applied in that order, consistently, in every place a number
comes out: the 2D panels, the line cuts, the 1D curve on screen, and every frame
of a batch. Doing that separately per page is how a batch quietly stops matching
what was on screen when it was set up, so it is done once here and the same
:class:`Cleaning` object is handed to the panels and to the batch.

Everything writes **NaN**, never zero. Each average is a ``nanmean``, so a
removed pixel drops out of its bin instead of dragging the bin towards zero: an
excluded ring becomes a gap in the curve rather than a trench that looks like
data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import streamlit as st

from pyscattviz.app.components.hotpixels import HotPixelSettings, render_hot_pixel_controls
from pyscattviz.app.components.maskeditor import draw_mode, render_mask_editor
from pyscattviz.app.components.scattering import (
    apply_mask,
    load_qimg,
    load_qphi,
    resolve_qimage,
)
from pyscattviz.dataio import DataReadError
from pyscattviz.despike import find_hot_pixels_stack
from pyscattviz.masking import MaskSet, build_mask

__all__ = ["Cleaning", "render_cleaning_controls"]


@dataclass
class Cleaning:
    """The cleaning a page has configured, ready to apply to any frame."""

    hot: HotPixelSettings
    mask: MaskSet
    drawing: bool = False
    use_defect_mask: bool = False
    defect_frames: int = 24
    paths: dict = field(default_factory=dict)

    # -- description ------------------------------------------------------
    def describe(self) -> list:
        """What is switched on, for a caption the user can check."""

        bits = []
        if self.hot.enabled:
            bits.append(
                "hot pixels" + (" (recurring only)" if self.use_defect_mask else " (per frame)")
            )
        if self.mask.enabled_regions():
            bits.append(f"{len(self.mask.enabled_regions())} masked region(s)")
        return bits

    @property
    def active(self) -> bool:
        return bool(self.describe())

    # -- the defect vote --------------------------------------------------
    def defect_mask(self, product: str):
        """Pixels hot across the selection, or None when that is switched off."""

        if not (self.hot.enabled and self.use_defect_mask):
            return None
        paths = self.paths.get(product) or ()
        if len(paths) < 2:
            return None
        mask, _info = _vote_defects(
            tuple(paths),
            product,
            self.defect_frames,
            self.hot.window,
            self.hot.zmax,
            self.hot.ratio_min,
            self.hot.abs_min,
            self.hot.persist_frac,
        )
        return mask

    # -- applying ---------------------------------------------------------
    def clean(self, z, x_axis, y_axis, space: str, product: str | None = None):
        """Blank the hot pixels and the excluded regions on one 2D product."""

        if z is None:
            return None
        out = self.hot.clean(z, self.defect_mask(product or space))
        flags = build_mask(self.mask, x_axis, y_axis, space)
        if flags is not None and flags.shape == np.asarray(out).shape:
            out = np.asarray(out, dtype=float).copy()
            out[flags] = np.nan
        return out

    def clean_qphi(self, row):
        """Load and clean a frame's q–φ map. Returns ``(q, phi, cleaned, info)``."""

        try:
            q_axis, phi_axis, caked, pmask = load_qphi(row["qphi"])
        except (DataReadError, KeyError, TypeError):
            return None, None, None, {}
        usable = pmask if getattr(pmask, "shape", None) == getattr(caked, "shape", None) else None
        image = _apply(caked, usable)
        before = int(np.isfinite(image).sum())
        cleaned = self.clean(image, q_axis, phi_axis, "qphi", "qphi")
        info = {
            "total": before,
            "blanked": before - int(np.isfinite(cleaned).sum()),
        }
        return q_axis, phi_axis, cleaned, info

    def clean_qimage(self, row, mode: str = "qx"):
        """Load and clean a frame's q-image. Returns ``(z, x, y, label, info)``."""

        try:
            data = load_qimg(row["qimg"])
        except (DataReadError, KeyError, TypeError):
            return None, None, None, "", {}
        z, x_axis, y_axis, qmask, label = resolve_qimage(data, mode)
        if z is None:
            return None, None, None, "", {}
        usable = qmask if getattr(qmask, "shape", None) == getattr(z, "shape", None) else None
        image = _apply(z, usable)
        before = int(np.isfinite(image).sum())
        cleaned = self.clean(image, x_axis, y_axis, "qimage", "qimg")
        info = {"total": before, "blanked": before - int(np.isfinite(cleaned).sum())}
        return cleaned, x_axis, y_axis, label, info

    # -- the two reductions -----------------------------------------------
    def curve(self, row, phi_range=None):
        """I(q): the cleaned q–φ map averaged down φ.

        ``phi_range`` narrows the azimuth, which turns the same call into a
        sector average. Returns ``(q, I, info)``.
        """

        q_axis, phi_axis, cleaned, info = self.clean_qphi(row)
        if cleaned is None:
            return None, None, {}
        rows = _in_range(phi_axis, phi_range)
        if not rows.any():
            return None, None, {}
        intensity = _nanmean(cleaned[rows, :], axis=0)
        info.update(bins=int(rows.sum()), empty=int(np.isnan(intensity).sum()))
        return np.asarray(q_axis, dtype=float), intensity, info

    def profile(self, row, q_range=None):
        """I(φ): the cleaned q–φ map averaged across q.

        The orientation profile — for a transmission SAXS anisotropy or a
        GIWAXS texture, this is the one that matters. ``q_range`` restricts it
        to a q band, which is what a q-cut is. Returns ``(phi, I, info)``.
        """

        q_axis, phi_axis, cleaned, info = self.clean_qphi(row)
        if cleaned is None:
            return None, None, {}
        columns = _in_range(q_axis, q_range)
        if not columns.any():
            return None, None, {}
        intensity = _nanmean(cleaned[:, columns], axis=1)
        info.update(bins=int(columns.sum()), empty=int(np.isnan(intensity).sum()))
        return np.asarray(phi_axis, dtype=float), intensity, info


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _apply(z, mask):
    """The reduction's "no data" → NaN, so it drops out of every average.

    Delegates to :func:`pyscattviz.app.components.scattering.apply_mask`, which
    already knows the two ways a reduction marks it and — importantly — infers
    which way round a boolean mask is written, from its overlap with the
    positive pixels. Some products use True for *valid*; assuming True meant
    *masked* would blank the data and keep the gaps.

    It also blanks exact zeros, which is the convention that matters most here:
    a caked map marks the (q, φ) bins the detector never reached with 0, and on
    a real CMS GIWAXS map that is 64% of it. Averaging those in as intensity
    put the re-integrated curve at 0.43x the reduction's own.
    """

    return apply_mask(z, mask)


def _in_range(axis, span):
    values = np.asarray(axis, dtype=float)
    if span is None:
        return np.ones(values.shape, dtype=bool)
    low, high = float(span[0]), float(span[1])
    if low > high:
        low, high = high, low
    return (values >= low) & (values <= high)


def _nanmean(block, axis):
    """Mean ignoring NaN, answering NaN — not zero — where there is nothing."""

    import warnings

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", "Mean of empty slice", RuntimeWarning)
        with np.errstate(invalid="ignore"):
            return np.where(
                np.isfinite(block).any(axis=axis),
                np.nanmean(np.where(np.isfinite(block), block, np.nan), axis=axis),
                np.nan,
            )


@st.cache_data(show_spinner="Voting for the recurring hot pixels…")
def _vote_defects(paths, product, count, window, zmax, ratio, abs_min, persist):
    """Pixels hot in ``persist`` of an evenly spread sample of ``paths``.

    Sampled across the selection rather than from the front: the first frames of
    a folder are usually one sample at several angles, and a vote over one
    sample flags that sample's own Bragg peaks as defects.
    """

    chosen = list(paths)
    take = max(2, min(int(count), len(chosen)))
    picks = np.unique(np.linspace(0, len(chosen) - 1, take).round().astype(int))

    def _frames():
        for index in picks:
            path = chosen[int(index)]
            try:
                if product == "qphi":
                    yield load_qphi(path)[2]
                else:
                    yield resolve_qimage(load_qimg(path), "qx")[0]
            except (DataReadError, KeyError, TypeError, ValueError):
                continue

    return find_hot_pixels_stack(
        _frames(),
        window=window,
        zmax=zmax,
        ratio_min=ratio,
        abs_min=abs_min,
        persist_frac=persist,
    )


def render_cleaning_controls(
    prefix: str,
    frames=None,
    *,
    preview_image=None,
    container=None,
) -> Cleaning:
    """Draw the hot-pixel and exclusion-mask controls; return what they mean.

    ``frames`` is the filtered frame table, used only to sample frames for the
    across-frames defect vote — and to give the batch the same list, so a batch
    cleans exactly what the panels did.
    """

    host = container if container is not None else st

    hot = render_hot_pixel_controls(f"{prefix}_hot", container=host, preview_image=preview_image)

    # A single frame cannot tell a stuck pixel from a sharp reflection, and on
    # real CMS data it mostly gets it wrong: one MAXS frame flags 36 pixels of
    # which only 4 recur, and the brightest six are a Bragg peak. Voting across
    # frames is the test that separates them.
    columns = host.columns([2.2, 1])
    use_defect = columns[0].checkbox(
        "Blank only pixels that recur across the selection",
        value=bool(st.session_state.get(f"{prefix}_use_defect_mask", False)),
        key=f"{prefix}_use_defect_mask",
        disabled=not hot.enabled,
        help=(
            "One pass over an evenly spread sample of the filtered frames, "
            "keeping only the pixels hot in nearly all of them. A detector "
            "defect is; a reflection from one sample is not."
        ),
    )
    defect_frames = int(
        columns[1].number_input(
            "frames sampled",
            2,
            200,
            int(st.session_state.get(f"{prefix}_defect_frames", 24)),
            1,
            key=f"{prefix}_defect_frames",
            disabled=not (hot.enabled and use_defect),
        )
    )

    mask = render_mask_editor(prefix, container=host)

    paths = {}
    if frames is not None and len(frames):
        for product, column, flag in (("qphi", "qphi", "has_qphi"), ("qimg", "qimg", "has_qimg")):
            if flag in frames and column in frames:
                paths[product] = tuple(
                    str(item) for item in frames[frames[flag]][column].tolist() if item
                )

    return Cleaning(
        hot=hot,
        mask=mask,
        drawing=draw_mode(prefix),
        use_defect_mask=use_defect,
        defect_frames=defect_frames,
        paths=paths,
    )
