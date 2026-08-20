"""One shared hot-pixel panel, with the thresholds exposed.

A hot pixel is not a well-defined object. Whether a given pixel is a detector
defect or the brightest point of a sharp reflection depends on a threshold, and
the right threshold depends on the detector, the exposure, and how oriented the
sample is. Hiding that behind a single "Remove hot pixels" checkbox makes the
decision for the user and gives them no way to see or change it, which is the
wrong trade for something that edits the data before it is plotted.

So the checkbox stays — the defaults are good for CMS and SMI — but every
threshold is on screen next to it, together with a count of what was removed
from the frame on display, so a setting can be judged rather than trusted.

The two criteria are described in :mod:`pyscattviz.despike`. In short a pixel
must be *significant* against counting statistics and a *multiple* of its local
neighbourhood; both, because either alone flags real data.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import streamlit as st

from pyscattviz.app.state import action_key
from pyscattviz.despike import (
    DEFAULT_PERSIST,
    DEFAULT_RATIO,
    DEFAULT_WINDOW,
    DEFAULT_ZMAX,
    apply_hot_mask,
    find_hot_pixels,
)

__all__ = ["HotPixelSettings", "PRESETS", "render_hot_pixel_controls"]

# Named starting points. "Strict" is for an oriented sample whose sharp
# reflections must survive; "Loose" is for a detector known to be speckled.
PRESETS: dict[str, dict[str, float]] = {
    "Default": {"window": DEFAULT_WINDOW, "zmax": DEFAULT_ZMAX, "ratio": DEFAULT_RATIO},
    "Strict (keep sharp peaks)": {"window": 5, "zmax": 15.0, "ratio": 10.0},
    "Loose (noisy detector)": {"window": 5, "zmax": 5.0, "ratio": 2.0},
}


@dataclass(frozen=True)
class HotPixelSettings:
    """The thresholds chosen on screen, plus the cleaning they imply."""

    enabled: bool = True
    window: int = DEFAULT_WINDOW
    zmax: float = DEFAULT_ZMAX
    ratio_min: float = DEFAULT_RATIO
    abs_min: float | None = None
    persist_frac: float = DEFAULT_PERSIST

    @property
    def kwargs(self) -> dict:
        """The keyword arguments for the :mod:`pyscattviz.despike` functions."""

        return {
            "window": int(self.window),
            "zmax": float(self.zmax),
            "ratio_min": float(self.ratio_min),
            "abs_min": self.abs_min,
        }

    def find(self, image):
        """Return the hot-pixel mask for one 2D product."""

        return find_hot_pixels(image, **self.kwargs)

    def clean(self, image, mask=None):
        """Return ``image`` with the hot pixels blanked, or unchanged if disabled.

        Pass ``mask`` to apply a defect mask worked out from several frames,
        which is the more reliable test — see :mod:`pyscattviz.despike`.
        """

        if not self.enabled or image is None:
            return image
        flags = mask if mask is not None else self.find(image)
        return apply_hot_mask(image, flags)

    def clean_and_count(self, image, mask=None) -> tuple[object, int]:
        """Clean one product and report how many pixels that cost."""

        if not self.enabled or image is None:
            return image, 0
        flags = np.asarray(mask if mask is not None else self.find(image), dtype=bool)
        return apply_hot_mask(image, flags), int(flags.sum())


def _preset_defaults(prefix: str, name: str) -> None:
    values = PRESETS[name]
    st.session_state[f"{prefix}_window"] = int(values["window"])
    st.session_state[f"{prefix}_zmax"] = float(values["zmax"])
    st.session_state[f"{prefix}_ratio"] = float(values["ratio"])


def render_hot_pixel_controls(
    prefix: str,
    *,
    container=None,
    default_enabled: bool = True,
    preview_image=None,
    show_persistence: bool = False,
    label: str = "Remove hot pixels from the 2D maps",
) -> HotPixelSettings:
    """Draw the toggle and its thresholds; return the chosen settings.

    Parameters
    ----------
    prefix
        Widget-key prefix, so each page keeps its own thresholds.
    preview_image
        The 2D product currently on display. When given, the panel reports how
        many pixels the present settings would blank and how bright the worst
        one was — which is the only way to tell a good threshold from a bad one
        without leaving the application.
    show_persistence
        Offer the across-frames persistence fraction. Only meaningful where
        several frames are processed together, so it is off in the explorers and
        on in batch export.
    """

    host = container if container is not None else st
    enabled = host.checkbox(
        label,
        value=bool(st.session_state.get(f"{prefix}_enabled", default_enabled)),
        key=f"{prefix}_enabled",
        help=(
            "A pixel reading 500,000 against a background of 100 moves a whole q "
            "bin, because the azimuthal average is a mean — so the 1-D curve "
            "grows a peak that is not there. Thresholds are below."
        ),
    )

    with host.expander("🔥 Hot-pixel thresholds", expanded=False):
        st.caption(
            "A pixel is removed only if it is **both** significant against "
            "counting statistics **and** a multiple of its own neighbourhood. "
            "Either test alone flags real data: significance alone once flagged "
            "a pixel sitting at 1.0× its neighbours on a steep gradient, and a "
            "plain ratio flags the tip of every sharp reflection."
        )

        preset_columns = st.columns(len(PRESETS))
        for index, (column, name) in enumerate(zip(preset_columns, PRESETS)):
            if column.button(
                name,
                key=action_key(st.session_state, f"{prefix}_preset_{index}"),
                use_container_width=True,
            ):
                _preset_defaults(prefix, name)
                st.rerun()

        controls = st.columns(4)
        window = controls[0].slider(
            "Neighbourhood (px)",
            3,
            15,
            int(st.session_state.get(f"{prefix}_window", DEFAULT_WINDOW)),
            2,
            key=f"{prefix}_window",
            help="Side of the median window the pixel is compared against.",
        )
        zmax = controls[1].slider(
            "Significance (σ)",
            2.0,
            30.0,
            float(st.session_state.get(f"{prefix}_zmax", DEFAULT_ZMAX)),
            0.5,
            key=f"{prefix}_zmax",
            help=(
                "Excess over the local median in units of √(local median). "
                "Higher removes fewer pixels."
            ),
        )
        ratio = controls[2].slider(
            "× local median",
            1.0,
            50.0,
            float(st.session_state.get(f"{prefix}_ratio", DEFAULT_RATIO)),
            0.5,
            key=f"{prefix}_ratio",
            help=(
                "The pixel must also be at least this many times its "
                "neighbourhood. This is what protects a steep gradient near the "
                "beamstop or a module edge."
            ),
        )
        floor = controls[3].number_input(
            "Minimum counts",
            min_value=0.0,
            value=float(st.session_state.get(f"{prefix}_absmin", 0.0)),
            step=100.0,
            key=f"{prefix}_absmin",
            help="Ignore anything dimmer than this. 0 turns the floor off.",
        )

        persist = float(st.session_state.get(f"{prefix}_persist", DEFAULT_PERSIST))
        if show_persistence:
            persist = st.slider(
                "Must recur in this fraction of frames",
                0.0,
                1.0,
                persist,
                0.05,
                key=f"{prefix}_persist",
                help=(
                    "A detector defect is hot in every frame; a Bragg spot from "
                    "an oriented sample is hot in one. Build the mask from "
                    "frames of *different* samples — over a single sample's "
                    "angle series a majority vote flags that sample's own peaks."
                ),
            )

        settings = HotPixelSettings(
            enabled=enabled,
            window=int(window),
            zmax=float(zmax),
            ratio_min=float(ratio),
            abs_min=float(floor) if floor > 0 else None,
            persist_frac=persist,
        )

        if preview_image is not None:
            _render_preview(settings, preview_image)

    return settings


def _render_preview(settings: HotPixelSettings, image) -> None:
    """Say what these thresholds do to the frame on display."""

    array = np.asarray(image, dtype=float)
    if array.ndim != 2 or not array.size:
        return
    if not settings.enabled:
        st.caption("Removal is off — the maps below are unedited.")
        return

    flags = settings.find(array)
    count = int(flags.sum())
    if not count:
        st.success("Nothing flagged in the frame on display.")
        return

    removed = array[flags]
    local = np.nanmedian(array[np.isfinite(array)])
    st.warning(
        f"**{count:,} pixel(s)** would be blanked in the frame on display — "
        f"brightest {np.nanmax(removed):,.0f} counts against a frame median of "
        f"{local:,.0f}. That is {100 * count / array.size:.4f}% of the map."
    )
    rows, cols = np.nonzero(flags)
    order = np.argsort(removed)[::-1][:6]
    listed = ", ".join(f"({rows[i]}, {cols[i]}) = {removed[i]:,.0f}" for i in order)
    st.caption(f"Brightest removed: {listed}")
