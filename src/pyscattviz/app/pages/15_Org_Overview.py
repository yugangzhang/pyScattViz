"""Org overview: what is measured, what is reduced, and the newest frames.

Counted from the folder listings of the open org (or data folder) — no file
is opened but the newest QC images — and re-read on a timer with *Live*,
so a beamtime can be followed from here.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from pyscattviz.app.auth import require_password
from pyscattviz.app.state import keep_widget_state

keep_widget_state(st.session_state)
require_password()

from pyscattviz.app.components.org import controls, state  # noqa: E402
from pyscattviz.org import cms  # noqa: E402

state.on_page()
state.require_source()

st.title(f"🛰️ {state.title()}")
st.caption(
    "Counted from the folders, re-read every "
    f"{state.REFRESH_S} s; nothing is opened but the newest QC images."
)

every = controls.live("svorg_ov")


def ago(stamp) -> str:
    if stamp is None or pd.isna(stamp):
        return "—"
    seconds = (pd.Timestamp.now() - stamp).total_seconds()
    if seconds < 90:
        return f"{seconds:.0f} s ago"
    if seconds < 5400:
        return f"{seconds / 60:.0f} min ago"
    if seconds < 2 * 86400:
        return f"{seconds / 3600:.1f} h ago"
    return stamp.strftime("%Y-%m-%d %H:%M")


@st.fragment(run_every=f"{every}s" if every else None)
def body() -> None:
    if every:
        state.rescan()
        state.sync_org()
    table = state.progress()
    frames = state.frames()
    if table.empty and frames.empty:
        st.info("Nothing measured yet: no detector or product folders.")
        return

    if not table.empty:
        cols = st.columns(4)
        cols[0].metric("raw frames", int(table["raw"].sum()))
        cols[1].metric("stitched", int(table["stitched"].sum()))
        cols[2].metric("reduced (I(q))", int(table["cir"].sum()))
        cols[3].metric("still to reduce", int(table["to_reduce"].sum()))

        show = table.copy()
        show["raw written"] = show.pop("raw_changed").map(ago)
        show["reduced written"] = show.pop("reduced_changed").map(ago)
        show = show.rename(
            columns={
                "det_folder": "detector",
                "cir": "I(q)",
                "qimg": "q-image",
                "qphi": "q–φ",
                "qc": "QC",
            }
        )
        st.dataframe(show, hide_index=True, width="stretch")
        st.caption(
            "*still to reduce*: stitched frames (raw frames, where nothing "
            "is stitched) with no I(q) yet. A detector folder with raw frames "
            "and no products has not been reduced at all."
        )
    else:
        st.metric("reduced frames", len(frames))

    if frames.empty:
        return
    st.subheader("Newest reduced frames")
    newest = (
        frames.dropna(subset=["scan"])
        .sort_values("scan")
        .groupby(["folder", "det_folder"], sort=True)
        .tail(1)
    )
    if newest.empty:
        newest = frames.groupby(["folder", "det_folder"], sort=True).tail(1)
    cols = st.columns(min(3, len(newest)) or 1)
    for i, (_, row) in enumerate(newest.iterrows()):
        with cols[i % len(cols)]:
            st.markdown(f"**{row['folder']} · {row['det_folder']}** — {row['sample']}")
            st.caption(cms.frame_label(row.to_dict()))
            if isinstance(row["qc"], str) and Path(row["qc"]).is_file():
                st.image(row["qc"], width="stretch")
            else:
                st.caption("no QC image for this frame")

    samples = state.samples()
    st.subheader("Samples")
    counts = samples.groupby(["folder", "kind"]).size().unstack(fill_value=0).reset_index()
    st.dataframe(counts, hide_index=True)


body()

st.subheader("The pages")
for page, label, text in [
    ("pages/14_Org.py", "🗂️ Org", "open or make an org; its samples; keep it"),
    (
        "pages/16_Org_Sample.py",
        "🖼️ One sample",
        "q-image, q–φ, I(q) and QC of one frame; every angle of a spot",
    ),
    (
        "pages/17_Org_Compare.py",
        "📈 Compare samples",
        "I(q) of many samples at one angle, overlaid and as a map; a peak in each",
    ),
    (
        "pages/18_Org_In_situ.py",
        "⏱️ In-situ",
        "a run as a waterfall against time, RH or T; the cell's readings; a peak along it",
    ),
    ("pages/19_Ask_AI.py", "💬 Ask AI", "questions about the org, answered by your model"),
]:
    a, b = st.columns([1, 3])
    with a:
        state.page_link(page, label)
    b.caption(text)
