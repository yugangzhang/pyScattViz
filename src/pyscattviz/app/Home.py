"""Home page for pyScattViz."""

from __future__ import annotations

import streamlit as st

from pyscattviz import __version__

st.set_page_config(
    page_title="pyScattViz",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔬 pyScattViz")
st.subheader("Review NSLS-II GISAXS, GIWAXS, SAXS, and WAXS data locally")

st.markdown(
    """
We developed pyScattViz for collaborators who need a direct route from an
NSLS-II proposal to interactive scattering-data review. The application runs
on the local computer and opens data only when a frame is selected.

### Recommended workflow

1. Open **Data Sources & Mounts**, choose the mount scope, and register the mounted drive.
2. On Windows, use the verified free RaiDrive SFTP route; Linux/macOS use SSHFS.
3. Open **File Selection** to filter thousands of filenames without loading arrays.
4. Open the geometry-specific **GISAXS**, **GIWAXS**, **Transmission SAXS**, or
   **Transmission WAXS** explorer.
5. Use **Plotting Studio** for 1D, 2D, 3D, and multi-axes figures, or
   **Publication Plot** for selected I(q) overlays.

The package also includes Yugang's reusable plotting tools under
`pyscattviz.plotting`: publication themes, custom scattering colormaps,
1D/2D/3D/N-D plots, layouts, overlays, transforms, and figure export. The
Plotting Studio exposes the principal 1D, 2D, 3D, and multi-axes tools directly
in the web interface.

I welcome [issue reports](https://github.com/yugangzhang/pyScattViz/issues).
Scientific-use questions can be sent to Yugang Zhang at
[yuzhang@bnl.gov](mailto:yuzhang@bnl.gov).
"""
)

left, middle, right = st.columns(3)
left.metric("Version", __version__)
middle.metric("Data loading", "Selected frame only")
right.metric("Platforms", "Windows · macOS · Linux")

st.info(
    "The application listens on 127.0.0.1 by default, so proposal data remain "
    "on the local computer unless a different address is explicitly selected."
)
