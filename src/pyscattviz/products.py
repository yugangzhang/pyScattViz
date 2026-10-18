"""The reduction's product folders and the frame each file belongs to.

Names only, no Streamlit: what the explorers, the Org layouts and a notebook
share — which folder holds which product (``SCATTERING_PRODUCTS``,
``product_folders``), and the frame stem a product file is named after
(``stem_of``).
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

from pyscattviz.discovery import fold_folder_name

# Reduction products are deliberately described as data, not as a fixed page
# layout.  The explorer can therefore show a new reduction folder (for
# example ``qc``) without making every page assume that every other product is
# present too.
#
# ``folders`` lists the directory names one product is written under. The CMS
# auto-reduction uses the lower-case names on the left; SMI's stitching pipeline
# writes the same five products under ``Raw_Plot``, ``Stitch_Data``,
# ``Stitch_Image``, ``Check_Stitch`` and ``Cir_Avg``. Matching is
# case-insensitive, so ``Cir_Avg`` needs no alias of its own. A folder that is
# not listed here is not a product and is left alone.
SCATTERING_PRODUCTS = {
    "stitched": {
        "label": "Raw / stitched image",
        "folders": ("stitched", "Stitch_Image"),
        "patterns": ("*.tif", "*.tiff", "*.png", "*.jpg", "*.jpeg"),
    },
    "raw_plot": {
        "label": "Raw detector plot",
        "folders": ("raw_plot",),
        "patterns": ("*.png", "*.jpg", "*.jpeg", "*.tif", "*.tiff"),
    },
    "qc": {
        "label": "QC image",
        "folders": ("qc", "Check_Stitch"),
        "patterns": ("*.png", "*.jpg", "*.jpeg", "*.tif", "*.tiff"),
    },
    "q_image": {
        "label": "q-image",
        # SMI writes the stitched q-map as a float TIFF with its qx and qz axes
        # beside it in CSVs, and so does the CMS `Qimage` folder; the older CMS
        # `q_image` folder writes one npz holding all three.
        "folders": ("q_image", "Qimage", "Stitch_Data"),
        "patterns": ("*.npz", "*.tif", "*.tiff"),
    },
    "qphi": {
        "label": "q–φ map",
        "folders": ("qphi",),
        "patterns": ("*.npz",),
    },
    "cir_avg": {
        "label": "Circular average I(q)",
        "folders": ("cir_avg",),
        "patterns": ("*.csv",),
    },
}


def product_key_for_folder(name) -> str | None:
    """Return the product key a folder name belongs to, or None."""

    folded = fold_folder_name(name)
    for key, spec in SCATTERING_PRODUCTS.items():
        if any(folded == fold_folder_name(alias) for alias in spec["folders"]):
            return key
    return None


def product_folders(root) -> dict:
    """Map each product present below ``root`` to the folder holding it.

    One directory listing answers for every product, which matters over a
    mounted proposal. Only names are read.
    """

    try:
        with os.scandir(Path(root)) as entries:
            present = {}
            for entry in entries:
                try:
                    if entry.is_dir():
                        present.setdefault(fold_folder_name(entry.name), entry.name)
                except OSError:
                    continue
    except OSError:
        return {}

    found = {}
    for key, spec in SCATTERING_PRODUCTS.items():
        for alias in spec["folders"]:
            name = present.get(fold_folder_name(alias))
            if name is not None:
                found[key] = Path(root) / name
                break
    return found


# CMS QC layout tags that sit between the ``qc_`` prefix and the frame name.
_QC_LAYOUT_RE = re.compile(r"^(?:\d+panel_)?(?:autoelevate_)?", re.IGNORECASE)


# Product filename prefixes, longest first so ``Stitch_Data_qx_`` is recognised
# before ``Stitch_Data_``. The axis and check tags are part of the prefix: an
# axis CSV and the map it belongs to are one frame, not three.
_PRODUCT_PREFIXES = (
    "Check_Stitch_q_iq_",
    "Check_Stitch_",
    "Stitch_Data_qx_",
    "Stitch_Data_qz_",
    "Stitch_Data_",
    "Stitch_Image_",
    "Qimage_qx_",
    "Qimage_qz_",
    "Qimage_",
    "Raw_Plot_",
    "Cir_Avg_",
    "qphi_",
    "qimg_",
    "qc_",
)


def stem_of(fname: str) -> str:
    """Shared ``<name>`` stem: strip known prefixes / extensions from a name.

    Handles the mixed conventions used by the auto-reduction, e.g.
    ``stitched/<name>.tiff``, ``q_image/qimg_<name>.tiff.npz`` and
    ``cir_avg/Cir_Avg_<name>.tiff.csv`` all reduce to the same ``<name>``. So do
    SMI's stitched products — ``Stitch_Data_<name>.tif.tiff``,
    ``Stitch_Data_qx_<name>.tif.csv``, ``Stitch_Image_<name>.tif.png``,
    ``Raw_Plot_<name>.tif.png`` and ``Check_Stitch_q_iq_<name>.tif.png``.

    CMS writes several QC layouts for one frame — ``qc_<name>``,
    ``qc_1panel_<name>`` … ``qc_4panel_autoelevate_<name>``. Those layout tags
    are part of the QC filename, not of the frame, so they are stripped too;
    otherwise each variant becomes its own frame with no other product attached.
    """
    s = Path(fname).name
    for pref in _PRODUCT_PREFIXES:
        if s.lower().startswith(pref.lower()):
            s = s[len(pref) :]
            if pref == "qc_":
                s = _QC_LAYOUT_RE.sub("", s, count=1)
            break
    # Peel trailing extensions repeatedly (e.g. ".tiff.npz" → ".tiff" → "").
    # ``tif`` covers SMI, whose products are named ``<name>.tif.{csv,npz}``.
    while True:
        new = re.sub(r"\.(npz|csv|png|tiff|tif)$", "", s)
        if new == s:
            return s
        s = new


def _iter_product_files(folder: Path, patterns):
    """Yield matching direct children while holding at most one entry."""

    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                try:
                    if entry.is_file() and any(
                        fnmatch.fnmatch(entry.name.lower(), pattern.lower()) for pattern in patterns
                    ):
                        yield entry.name, entry.path
                except OSError:
                    continue
    except OSError:
        return
