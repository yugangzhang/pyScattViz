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

import pandas as pd
import streamlit as st

from pyscattviz.app.components.saving import (
    DATE_KEY,
    OVERWRITE_KEY,
    SUBFOLDER_KEY,
    output_root,
    record_saved,
)
from pyscattviz.app.components.scattering import BATCH_PANELS, frame_panel_figure
from pyscattviz.exporting import (
    PLOTLY_FORMATS,
    ExportError,
    resolve_output_dir,
    save_arrays,
    save_plotly_figure,
    save_table,
)

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


def render_batch_export(
    frames: pd.DataFrame,
    available_panels,
    tab_name: str,
    *,
    key: str,
    panel_options: dict,
    expanded: bool = False,
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
        controls = st.columns([1.4, 1, 1, 1])
        panel = controls[0].selectbox(
            "Panel",
            panels,
            format_func=lambda item: BATCH_PANELS[item],
            key=f"{key}_batch_panel",
        )
        fmt = controls[1].selectbox(
            "Format", list(PLOTLY_FORMATS), key=f"{key}_batch_format"
        )
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

        if not st.button("Export the batch", type="primary", key=f"{key}_batch_run"):
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
                f"skipped: {', '.join(missing[:5])}"
                + (" …" if len(missing) > 5 else "")
            )
        for message in failed[:5]:
            st.error(message)
        if not written and not missing and not failed:
            st.warning("Nothing was written.")
