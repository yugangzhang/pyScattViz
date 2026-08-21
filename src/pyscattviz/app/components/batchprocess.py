"""Apply what is set up on one frame to every frame that passed the filter.

The workflow this exists for: point at a folder, filter it down to the frames of
interest, open one of them, get the cleaning right — mask out the hot pixels,
draw over the substrate peak — and then apply exactly that to the other 755 and
write out whatever you need.

"Exactly that" is the part worth being careful about. The batch takes the same
:class:`~pyscattviz.app.components.cleaning.Cleaning` object the panels used, so
there is no second implementation to drift: if the curve on screen has a gap
where the mask is, so does every curve in the batch.

What gets written is a set of tick boxes rather than a mode, because these are
not alternatives — a run usually wants the curves *and* a picture *and* a record
of what was done:

``I(q)``
    the q–φ map averaged down φ. The whole azimuth, or one CSV per φ band.
``I(φ)``
    the same map averaged across q — the orientation profile. The whole q range,
    or one CSV per q band. This is the one for a transmission anisotropy or a
    GIWAXS texture.
``Panels``
    the figures as they appear on screen, one file per frame per panel.
``Arrays``
    the cleaned 2D products as NPZ, for anyone who wants to carry on in their
    own code.
``Manifest``
    one CSV describing the run: every frame, what was written for it, and how
    much of it was masked away. Without this a folder of 756 curves is a folder
    of 756 curves whose provenance is a memory.
"""

from __future__ import annotations

import time
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
from pyscattviz.app.state import action_key
from pyscattviz.exporting import (
    ExportError,
    resolve_output_dir,
    safe_component,
    save_arrays,
    save_plotly_figure,
    save_table,
)

__all__ = ["render_batch_process"]

MAX_BATCH_FRAMES = 5000

# Every output this panel can write. Availability depends on the products the
# folder actually has, so a q-image-only folder does not offer I(q).
OUTPUTS = {
    "iq": ("I(q) — q–φ averaged over φ (CSV)", "qphi"),
    "iphi": ("I(φ) — q–φ averaged over q (CSV)", "qphi"),
    "panels": ("Panel figures (one file per frame)", None),
    "arrays": ("Cleaned 2D arrays (NPZ)", None),
    "manifest": ("Manifest of the run (CSV)", None),
}


def _target(tab_name: str, subfolder: str) -> Path:
    parts = [tab_name] if st.session_state.get(SUBFOLDER_KEY, True) else []
    if subfolder.strip():
        parts.append(subfolder.strip())
    return resolve_output_dir(
        output_root(),
        *parts,
        create=True,
        date_subfolder=bool(st.session_state.get(DATE_KEY, False)),
    )


def _bands(text: str, width: float):
    """Parse "1.0, 1.4" + a width into ``[(name, (lo, hi)), ...]``.

    Empty means one band covering everything, which is the plain average.
    """

    centers = []
    for chunk in str(text or "").replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            centers.append(float(chunk))
        except ValueError:
            continue
    if not centers:
        return [("", None)]
    half = abs(float(width)) / 2.0
    return [(f"_{c:g}", (c - half, c + half)) for c in centers]


def render_batch_process(
    frames: pd.DataFrame,
    available_panels,
    tab_name: str,
    *,
    key: str,
    cleaning,
    panel_options: dict,
    defaults: dict | None = None,
    expanded: bool = False,
) -> None:
    """Draw the batch panel and, when asked, run it.

    ``defaults`` lets a page tick the outputs its technique usually wants —
    a grazing page opens on I(q), a transmission page on I(q) and I(φ) — without
    the panel needing to know which technique it is on.
    """

    if frames.empty:
        return

    panels = [item for item in available_panels if item in BATCH_PANELS]
    has_qphi = bool("has_qphi" in frames and frames["has_qphi"].any())
    defaults = defaults or {}

    with st.expander(f"⚙️ Batch process · {len(frames):,} frame(s)", expanded=expanded):
        st.caption(
            "Applies the hot-pixel settings and the exclusion mask above to every "
            "frame that passed the filter, and writes what you tick. It is the "
            "same cleaning the panels are using, not a second copy of it — set it "
            "up on one frame, check it, then run it over the rest."
        )
        described = cleaning.describe()
        if described:
            st.success("Will be applied to every frame: " + ", ".join(described))
        else:
            st.info("No cleaning is switched on — this writes the products as they are.")

        st.markdown("**What to write**")
        chosen = {}
        columns = st.columns(len(OUTPUTS))
        for column, (name, (label, needs)) in zip(columns, OUTPUTS.items()):
            available = needs is None or (needs == "qphi" and has_qphi)
            chosen[name] = column.checkbox(
                label,
                value=bool(st.session_state.get(f"{key}_bp_{name}", defaults.get(name, False)))
                and available,
                key=f"{key}_bp_{name}",
                disabled=not available,
                help=None if available else "This folder has no q–φ maps.",
            )

        # --- per-output settings -------------------------------------------
        if chosen["iq"]:
            row = st.columns([2, 1])
            phi_text = row[0].text_input(
                "I(q): φ band centres (blank = whole azimuth)",
                key=f"{key}_bp_phi_centres",
                placeholder="0, 90",
                help="One CSV per centre. Blank averages every azimuth into one curve.",
            )
            phi_width = row[1].number_input(
                "φ band width", 0.1, 360.0, 20.0, 5.0, key=f"{key}_bp_phi_width"
            )
        if chosen["iphi"]:
            row = st.columns([2, 1])
            q_text = row[0].text_input(
                "I(φ): q band centres (blank = whole q range)",
                key=f"{key}_bp_q_centres",
                placeholder="1.4, 1.9",
                help="One CSV per centre — the orientation profile in that q band.",
            )
            q_width = row[1].number_input(
                "q band width", 0.0001, 100.0, 0.05, 0.01, format="%.4f", key=f"{key}_bp_q_width"
            )
        if chosen["panels"] and panels:
            row = st.columns([2, 1])
            wanted_panels = row[0].multiselect(
                "Panels",
                panels,
                default=[panels[0]],
                format_func=lambda item: BATCH_PANELS[item],
                key=f"{key}_bp_panel_list",
            )
            panel_fmt = row[1].selectbox(
                "Format", ["png", "svg", "pdf", "html"], key=f"{key}_bp_panel_fmt"
            )
        elif chosen["panels"]:
            st.warning("No panels are available to write for this folder.")

        row = st.columns([2, 1])
        subfolder = row[0].text_input("Subfolder", value="batch", key=f"{key}_bp_subfolder")
        limit = int(
            row[1].number_input(
                "Maximum frames",
                1,
                MAX_BATCH_FRAMES,
                min(len(frames), MAX_BATCH_FRAMES),
                10,
                key=f"{key}_bp_limit",
            )
        )

        selected = frames.head(limit)
        st.caption(f"Writing into `{_target(tab_name, subfolder)}`")
        if len(selected) < len(frames):
            st.info(
                f"Only the first {len(selected):,} of {len(frames):,} frames — "
                "raise the maximum to take the rest."
            )
        if not any(chosen.values()):
            st.caption("Nothing ticked yet.")
            return

        if not st.button(
            f"Run over {len(selected):,} frame(s)",
            type="primary",
            key=action_key(st.session_state, f"{key}_bp_run"),
        ):
            return

        try:
            folder = _target(tab_name, subfolder)
        except ExportError as exc:
            st.error(str(exc))
            return

        overwrite = bool(st.session_state.get(OVERWRITE_KEY, False))
        progress = st.progress(0.0, text="Starting …")
        written, failed, rows = [], [], []
        started = time.time()

        for position, (_index, frame) in enumerate(selected.iterrows(), start=1):
            stem = str(frame["stem"])
            elapsed = time.time() - started
            rate = position / elapsed if elapsed > 0 else 0.0
            eta = (len(selected) - position) / rate if rate > 0 else 0.0
            progress.progress(
                position / len(selected),
                text=(
                    f"{position}/{len(selected)} · {stem[:48]} · "
                    f"{rate:.1f} frame/s · ETA {eta / 60:.1f} min"
                ),
            )
            record = {"stem": stem, "written": 0}
            try:
                if chosen["iq"] and frame.get("has_qphi"):
                    for tag, span in _bands(phi_text, phi_width):
                        q_axis, intensity, info = cleaning.curve(frame, span)
                        if q_axis is None:
                            continue
                        table = pd.DataFrame({"q": q_axis, "I": intensity})
                        written.append(
                            str(save_table(table, folder, f"{stem}_Iq{tag}", overwrite=overwrite))
                        )
                        record["written"] += 1
                        record.setdefault("masked_pixels", info.get("blanked", 0))
                        record.setdefault("empty_q_bins", info.get("empty", 0))

                if chosen["iphi"] and frame.get("has_qphi"):
                    for tag, span in _bands(q_text, q_width):
                        phi_axis, intensity, info = cleaning.profile(frame, span)
                        if phi_axis is None:
                            continue
                        table = pd.DataFrame({"phi": phi_axis, "I": intensity})
                        written.append(
                            str(save_table(table, folder, f"{stem}_Iphi{tag}", overwrite=overwrite))
                        )
                        record["written"] += 1

                if chosen["arrays"]:
                    payload = {}
                    if frame.get("has_qphi"):
                        q_axis, phi_axis, cleaned, _info = cleaning.clean_qphi(frame)
                        if cleaned is not None:
                            payload.update(q=q_axis, phi=phi_axis, qphi=cleaned)
                    if frame.get("has_qimg"):
                        z, x_axis, y_axis, _label, _info = cleaning.clean_qimage(
                            frame, panel_options.get("b_mode", "qx")
                        )
                        if z is not None:
                            payload.update(qimg=z, qx=x_axis, qz=y_axis)
                    if payload:
                        written.append(
                            str(
                                save_arrays(payload, folder, f"{stem}_cleaned", overwrite=overwrite)
                            )
                        )
                        record["written"] += 1

                if chosen["panels"] and panels and wanted_panels:
                    for panel in wanted_panels:
                        # Returns (figure, table, arrays); a frame without that
                        # product returns None rather than an empty picture.
                        built = frame_panel_figure(frame, panel, title=stem, **panel_options)
                        if built is None:
                            continue
                        figure = built[0]
                        written.append(
                            str(
                                save_plotly_figure(
                                    figure,
                                    folder,
                                    f"{stem}_{safe_component(panel)}",
                                    fmt=panel_fmt,
                                    overwrite=overwrite,
                                )
                            )
                        )
                        record["written"] += 1
            except (ExportError, OSError, ValueError, KeyError) as exc:
                failed.append(f"{stem}: {exc}")
                record["error"] = str(exc)
            rows.append(record)

        progress.empty()

        if chosen["manifest"] and rows:
            manifest = pd.DataFrame(rows)
            manifest["cleaning"] = ", ".join(cleaning.describe()) or "none"
            manifest["mask"] = cleaning.mask.name if cleaning.mask.enabled_regions() else ""
            try:
                path = save_table(manifest, folder, "batch_manifest", overwrite=True)
                written.append(str(path))
            except (ExportError, OSError) as exc:
                failed.append(f"manifest: {exc}")

        if written:
            record_saved(Path(written[-1]))
            st.success(
                f"Wrote {len(written):,} file(s) from {len(selected):,} frame(s) "
                f"in {time.time() - started:.0f} s → {folder}"
            )
            st.code("\n".join(Path(item).name for item in written[:10]), language=None)
            if len(written) > 10:
                st.caption(f"… and {len(written) - 10:,} more")
        else:
            st.warning("Nothing was written — check the ticks and the products available.")

        for message in failed[:5]:
            st.error(message)
        if len(failed) > 5:
            st.error(f"… and {len(failed) - 5:,} more failure(s)")
