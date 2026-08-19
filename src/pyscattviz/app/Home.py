"""Home page for pyScattViz."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from pyscattviz import __version__
from pyscattviz.app.components.saving import ensure_output_settings, output_root
from pyscattviz.app.state import keep_widget_state

st.set_page_config(
    page_title="pyScattViz",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Streamlit forgets a page's widgets as soon as another page is opened. Keep them.
keep_widget_state(st.session_state)

st.title("🔬 pyScattViz")
st.subheader("Explore your scattering data — mounted, downloaded, or already local")

st.markdown(
    """
I wrote pyScattViz for collaborators who need a direct route from an NSLS-II
proposal, or from a folder on their own disk, to interactive scattering-data
review. The application runs locally and opens a file only when it is selected.

### The short version

1. **Data Sources & Mounts** — mount the proposal (RaiDrive on Windows, SSHFS on
   macOS/Linux, rclone on all three), copy a subset with `sftp -r`, or just point
   at a local folder. Nothing needs to be paid for.
2. **Data Selection** — find the folders you care about with *must contain* /
   *may contain* / *must not contain* term lists, or paste a list of full paths.
   Keep them in a dataset basket and save it under a name.
3. **File Selection** — filter thousands of reduced filenames without opening a
   single array.
4. **GISAXS · GIWAXS · Transmission SAXS · Transmission WAXS** — the geometry
   you actually measured, each with its own q defaults and line cuts.
5. **Quick Plot** — hand it any list of paths and get 1D overlays, a stacked
   intensity map, or 2D images.
6. **Publication Plot** and **Plotting Studio** — export-ready figures using the
   same `pyscattviz.plotting` API available in notebooks.

Everything that draws something can write it straight to a folder you name, in a
subfolder named after the page it came from. Set that folder on
**Output Folder**.
"""
)

left, middle, right = st.columns(3)
left.metric("Version", __version__)
middle.metric("Data loading", "Selected file only")
right.metric("Platforms", "Windows · macOS · Linux")

ensure_output_settings()
current_root = Path(output_root())
active = st.session_state.get("pyscattviz_active_root", "")
basket = st.session_state.get("pyscattviz_dataset_paths", [])

status_left, status_right = st.columns(2)
with status_left:
    st.markdown("**Active data folder**")
    if active and Path(active).expanduser().is_dir():
        st.code(active, language=None)
    else:
        st.info("None yet — start on Data Sources & Mounts or Data Selection.")
    if basket:
        st.caption(f"{len(basket):,} path(s) in the dataset basket.")
with status_right:
    st.markdown("**Saved figures go to**")
    st.code(str(current_root), language=None)
    st.caption("Created on demand, with one subfolder per page. Change it on Output Folder.")

st.markdown(
    """
The package also includes my reusable plotting tools under `pyscattviz.plotting`:
publication themes, custom scattering colormaps, 1D/2D/3D/N-D plots, layouts,
overlays, transforms, and figure export.

I welcome [issue reports](https://github.com/yugangzhang/pyScattViz/issues).
Scientific-use questions can be sent to Yugang Zhang at
[yuzhang@bnl.gov](mailto:yuzhang@bnl.gov).
"""
)

st.info(
    "The application listens on 127.0.0.1 by default, so proposal data remain "
    "on the local computer unless a different address is explicitly selected. "
    "pyScattViz never asks for, receives, or stores a BNL password or Duo response."
)
