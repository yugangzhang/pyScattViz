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
I developed pyScattViz for collaborators who need a direct route from an
NSLS-II proposal to interactive scattering-data review. The application runs
on the local computer and opens data only when a frame is selected.

### Recommended workflow

1. Open **Globus & Data Sources** and build the NSLS-II proposal path.
2. Transfer the required proposal or result folders with Globus Connect Personal.
3. Open **File Selection** to filter thousands of filenames without loading arrays.
4. Open **GISAXS / GIWAXS Explorer** or **Transmission SAXS / WAXS**.

The first release focuses on reduced scattering products: QC images, q-images,
q–φ maps, circular averages, and line cuts. It does not include Data Manager or
UV-Vis tools.
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
