"""Export one product panel for every frame that survives the filters.

Reviewing a beamtime frame by frame is fine for finding the interesting sample
and hopeless for showing a collaborator what happened over ninety exposures.
This renders the same panel for each filtered frame and writes it into one
folder — a contact sheet on disk, in whatever format the user asked for.

The work is bounded and interruptible: a hard cap on frames, a progress bar, and
per-frame errors that are reported rather than aborting the run.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from pyscattviz.app.components.hotpixels import render_hot_pixel_controls
from pyscattviz.app.components.saving import (
    DATE_KEY,
    OVERWRITE_KEY,
    SUBFOLDER_KEY,
    output_root,
    record_saved,
)
from pyscattviz.app.components.scattering import (
    BATCH_PANELS,
    apply_mask,
    frame_panel_figure,
    load_qphi,
)
from pyscattviz.app.state import action_key, coerce_choice
from pyscattviz.dataio import DataReadError
from pyscattviz.despike import azimuthal_average, find_hot_pixels_stack
from pyscattviz.exporting import (
    PLOTLY_FORMATS,
    ExportError,
    resolve_output_dir,
    save_arrays,
    save_plotly_figure,
    save_table,
)
from pyscattviz.masking import build_mask

__all__ = ["render_batch_export"]

MAX_BATCH_FRAMES = 500


def _target_folder(tab_name: str, subfolder: str) -> Path:
    parts = []
    if st.session_state.get(SUBFOLDER_KEY, True):
        parts.append(tab_name)
    if subfolder.strip():
        parts.append(subfolder)
    return resolve_output_dir(
        output_root(),
        *parts,
        create=True,
        date_subfolder=bool(st.session_state.get(DATE_KEY, False)),
    )


def _build_defect_mask(frames: pd.DataFrame, hot, sample_size: int):
    """Vote for the pixels that are hot across a spread of the selection.

    The frames are sampled evenly rather than taken from the front: the first
    24 files of a folder are usually one sample at six incident angles, and a
    vote over one sample flags that sample's own Bragg spots as defects.
    """

    total = len(frames)
    if total < 2:
        return None, {}
    count = max(2, min(int(sample_size), total))
    positions = np.unique(np.linspace(0, total - 1, count).round().astype(int))

    def _images():
        for position in positions:
            row = frames.iloc[int(position)]
            try:
                _q, _phi, caked, mask = load_qphi(str(row["qphi"]))
            except (DataReadError, OSError, ValueError):
                continue
            usable = mask if getattr(mask, "shape", None) == getattr(caked, "shape", None) else None
            yield apply_mask(caked, usable)

    mask, info = find_hot_pixels_stack(_images(), persist_frac=hot.persist_frac, **hot.kwargs)
    if not info.get("frames"):
        return None, {}
    return mask, info


def _render_curve_batch(frames: pd.DataFrame, tab_name: str, *, key: str, user_mask=None) -> None:
    """Re-integrate every filtered frame's q–φ map into a despiked 1D curve.

    The reduction's own circular average is computed before anyone has looked at
    the data, so a hot pixel is baked into it. Re-integrating here, after the
    spikes are blanked, is the point of doing this in a viewer at all.
    """

    with_qphi = frames[frames["has_qphi"]] if "has_qphi" in frames else frames.iloc[0:0]
    if with_qphi.empty:
        st.info("No q–φ maps in this selection, so there is nothing to re-integrate.")
        return

    row = st.columns(3)
    phi_low = row[0].number_input("φ from", -180.0, 180.0, 0.0, 5.0, key=f"{key}_curve_phi_lo")
    phi_high = row[1].number_input("φ to", -180.0, 180.0, 180.0, 5.0, key=f"{key}_curve_phi_hi")
    limit = row[2].number_input(
        "Maximum frames",
        1,
        MAX_BATCH_FRAMES,
        min(100, len(with_qphi)),
        10,
        key=f"{key}_curve_limit",
    )

    if user_mask is not None and user_mask.enabled_regions():
        st.caption(
            f"The exclusion mask “{user_mask.name}” "
            f"({len(user_mask.enabled_regions())} region(s)) is applied to every frame."
        )
    hot = render_hot_pixel_controls(
        f"{key}_curve_hot",
        show_persistence=True,
        label="Remove hot pixels before integrating",
    )
    despike = hot.enabled
    shared_mask = st.checkbox(
        "Build one defect mask from the whole selection",
        value=bool(st.session_state.get(f"{key}_curve_shared_mask", False)),
        key=f"{key}_curve_shared_mask",
        disabled=not despike,
        help=(
            "A first pass over a sample of the frames keeps only the pixels that "
            "recur, then that one mask is applied to every frame. This is the "
            "test that separates a detector defect from a sharp reflection, so "
            "it is the honest way to do a batch — at the cost of reading a "
            "sample of the frames twice. Sample frames from *different* samples."
        ),
    )
    mask_frames = 0
    if despike and shared_mask:
        mask_frames = int(
            st.number_input(
                "Frames sampled to build the mask",
                2,
                200,
                int(st.session_state.get(f"{key}_curve_mask_frames", 24)),
                1,
                key=f"{key}_curve_mask_frames",
                help="Spread evenly across the selection, so the sample spans it.",
            )
        )

    subfolder_key = f"{key}_curve_subfolder"
    st.session_state.setdefault(subfolder_key, "curves_1d")
    subfolder = st.text_input("Subfolder for this batch", key=subfolder_key)
    st.caption(f"{len(with_qphi):,} frame(s) carry a q–φ map. Will be written to")
    st.code(str(_target_folder(tab_name, subfolder)), language=None)

    selected = with_qphi.head(int(limit))
    if len(with_qphi) > len(selected):
        st.info(f"Only the first {len(selected):,} of {len(with_qphi):,} will be written.")

    if not st.button(
        "Export the curves", type="primary", key=action_key(st.session_state, f"{key}_curve_run")
    ):
        return

    try:
        folder = _target_folder(tab_name, subfolder)
    except ExportError as exc:
        st.error(str(exc))
        return

    overwrite = bool(st.session_state.get(OVERWRITE_KEY, False))

    defect_mask = None
    if despike and shared_mask:
        defect_mask, mask_info = _build_defect_mask(with_qphi, hot, mask_frames)
        if defect_mask is None:
            st.warning("Could not read enough frames to build a shared mask; using per-frame.")
        else:
            st.info(
                f"Shared mask: {mask_info['n_hot']:,} pixel(s) hot in at least "
                f"{mask_info['needed']} of {mask_info['frames']} sampled frames."
            )

    progress = st.progress(0.0, text="Starting …")
    written, failed, removed_total = [], [], 0

    for position, (_index, frame) in enumerate(selected.iterrows(), start=1):
        stem = str(frame["stem"])
        progress.progress(position / len(selected), text=f"{position}/{len(selected)} · {stem}")
        try:
            q_axis, phi_axis, caked, mask = load_qphi(str(frame["qphi"]))
        except (DataReadError, OSError, ValueError) as exc:
            failed.append(f"{stem}: {exc}")
            continue
        usable = mask if getattr(mask, "shape", None) == getattr(caked, "shape", None) else None
        image = apply_mask(caked, usable)
        flags = build_mask(user_mask, q_axis, phi_axis, "qphi")
        if flags is not None and flags.shape == image.shape:
            image = np.asarray(image, dtype=float).copy()
            image[flags] = np.nan
        if despike:
            usable_mask = (
                defect_mask
                if defect_mask is not None
                and getattr(defect_mask, "shape", None) == getattr(image, "shape", None)
                else None
            )
            image, removed = hot.clean_and_count(image, usable_mask)
            removed_total += removed
        try:
            q_out, intensity = azimuthal_average(image, q_axis, phi_axis, (phi_low, phi_high))
            table = pd.DataFrame({"q": q_out, "I": intensity}).dropna()
            written.append(str(save_table(table, folder, f"{stem}_cir", overwrite=overwrite)))
        except (ExportError, ValueError) as exc:
            failed.append(f"{stem}: {exc}")
            break

    progress.empty()
    if written:
        record_saved(Path(written[-1]))
        st.success(f"Wrote {len(written):,} curve(s) into {folder}")
        if despike:
            st.caption(f"{removed_total:,} hot pixel(s) blanked across the batch.")
        st.code("\n".join(Path(item).name for item in written[:8]), language=None)
    for message in failed[:5]:
        st.error(message)


def render_batch_export(
    frames: pd.DataFrame,
    available_panels,
    tab_name: str,
    *,
    key: str,
    panel_options: dict,
    expanded: bool = False,
    user_mask=None,
) -> None:
    """Render the batch-export controls for the currently filtered frames.

    Parameters
    ----------
    frames
        The filtered frame table; one file is written per row.
    available_panels
        Product keys the page is currently showing, in display order.
    tab_name
        Page name, used for the output subfolder.
    panel_options
        Display settings forwarded to
        :func:`pyscattviz.app.components.scattering.frame_panel_figure`, so a
        batch matches what is on screen.
    """

    panels = [panel for panel in available_panels if panel in BATCH_PANELS]
    if frames.empty or not panels:
        return

    with st.expander("🗂️ Export every filtered frame", expanded=expanded):
        st.caption(
            f"{len(frames):,} frame(s) pass the current filters. Each one is written "
            "as a separate file using the display settings above. Line-cut bands are "
            "not drawn on a batch."
        )
        mode = st.radio(
            "What to export",
            ["Panel figure", "1D curve from q–φ (CSV)"],
            horizontal=True,
            key=f"{key}_batch_mode",
            help=(
                "The 1D option re-integrates the q–φ map over an azimuthal "
                "window with the hot pixels removed, and writes one CSV per "
                "frame — the reduced curve without the spikes."
            ),
        )
        if mode.startswith("1D"):
            _render_curve_batch(frames, tab_name, key=key, user_mask=user_mask)
            return

        controls = st.columns([1.4, 1, 1, 1])
        coerce_choice(st.session_state, f"{key}_batch_panel", panels)
        panel = controls[0].selectbox(
            "Panel",
            panels,
            format_func=lambda item: BATCH_PANELS[item],
            key=f"{key}_batch_panel",
        )
        fmt = controls[1].selectbox("Format", list(PLOTLY_FORMATS), key=f"{key}_batch_format")
        limit = controls[2].number_input(
            "Maximum frames",
            1,
            MAX_BATCH_FRAMES,
            min(50, max(1, len(frames))),
            10,
            key=f"{key}_batch_limit",
        )
        also_data = controls[3].checkbox(
            "Also write the data",
            value=False,
            key=f"{key}_batch_data",
            help="CSV beside a 1D panel, NPZ beside a 2D panel.",
        )

        # Follow the panel unless the user has typed a name of their own; a
        # cir_avg batch landing in a folder called batch_q_image is a trap.
        subfolder_key = f"{key}_batch_subfolder"
        suggested = f"batch_{panel}"
        previous = st.session_state.get(f"{subfolder_key}__suggested")
        if subfolder_key not in st.session_state or st.session_state[subfolder_key] == previous:
            st.session_state[subfolder_key] = suggested
        st.session_state[f"{subfolder_key}__suggested"] = suggested
        subfolder = st.text_input(
            "Subfolder for this batch",
            key=subfolder_key,
            help="Keeps a contact sheet out of the single-figure folder.",
        )
        preview = _target_folder(tab_name, subfolder) if subfolder.strip() else None
        if preview is not None:
            st.caption("Will be written to")
            st.code(str(preview), language=None)

        selected = frames.head(int(limit))
        if len(frames) > len(selected):
            st.info(
                f"Only the first {len(selected):,} of {len(frames):,} frames will be "
                "written. Raise the maximum or narrow the filter."
            )

        if not st.button(
            "Export the batch", type="primary", key=action_key(st.session_state, f"{key}_batch_run")
        ):
            return

        try:
            folder = _target_folder(tab_name, subfolder)
        except ExportError as exc:
            st.error(str(exc))
            return

        overwrite = bool(st.session_state.get(OVERWRITE_KEY, False))
        progress = st.progress(0.0, text="Starting …")
        written: list[str] = []
        missing: list[str] = []
        failed: list[str] = []

        for position, (_index, row) in enumerate(selected.iterrows(), start=1):
            stem = str(row["stem"])
            progress.progress(position / len(selected), text=f"{position}/{len(selected)} · {stem}")
            try:
                built = frame_panel_figure(row, panel, title=stem, **panel_options)
            except (OSError, ValueError, KeyError) as exc:
                failed.append(f"{stem}: {exc}")
                continue
            if built is None:
                missing.append(stem)
                continue
            figure, table, arrays = built
            try:
                path = save_plotly_figure(
                    figure, folder, f"{stem}_{panel}", fmt=fmt, overwrite=overwrite
                )
                written.append(str(path))
                if also_data and table is not None:
                    save_table(table, folder, f"{stem}_{panel}", overwrite=overwrite)
                elif also_data and arrays is not None:
                    save_arrays(arrays, folder, f"{stem}_{panel}", overwrite=overwrite)
            except ExportError as exc:
                failed.append(f"{stem}: {exc}")
                # A missing kaleido or a full disk fails identically for every
                # remaining frame, so stop rather than repeat it a hundred times.
                break

        progress.empty()
        if written:
            record_saved(Path(written[-1]))
            st.success(f"Wrote {len(written):,} file(s) into {folder}")
            st.code("\n".join(Path(item).name for item in written[:10]), language=None)
        if missing:
            st.info(
                f"{len(missing):,} frame(s) have no {BATCH_PANELS[panel]} and were "
                f"skipped: {', '.join(missing[:5])}" + (" …" if len(missing) > 5 else "")
            )
        for message in failed[:5]:
            st.error(message)
        if not written and not missing and not failed:
            st.warning("Nothing was written.")
