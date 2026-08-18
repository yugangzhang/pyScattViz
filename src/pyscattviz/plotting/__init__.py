"""Publication-quality scientific plotting included with pyScattViz.

This API consolidates Yugang Zhang's earlier ``pyViz`` package under the
single supported namespace::

    import pyscattviz.plotting as pv

    pv.set_theme("science")
    pv.plot1d(intensity, x=q, logx=True, logy=True)
"""

from pyscattviz.plotting.io import fig_to_base64, fig_to_bytes, save_fig
from pyscattviz.plotting.labels import (
    disable_auto_sanitize,
    enable_auto_sanitize,
    sanitize_label,
)
from pyscattviz.plotting.layout import (
    create_axes,
    create_axes_inset,
    create_axes_mosaic,
    create_axes_ratio,
)
from pyscattviz.plotting.overlays import (
    add_hlines,
    add_patches,
    add_region_patches,
    add_text_box,
    add_vlines,
    overlay_mask,
    overlay_mask_on_image,
)
from pyscattviz.plotting.plot1d import plot1d, plot1d_multi, plot1d_with_fit
from pyscattviz.plotting.plot2d import heatmap, imshow, imshow_z
from pyscattviz.plotting.plot3d import (
    contour,
    make_demo_data,
    scatter3d,
    surface,
    surface_contour,
    wireframe,
)
from pyscattviz.plotting.plotnd import (
    correlation_matrix,
    multi_hue_pairplot,
    pairplot,
    parallel_coords,
)
from pyscattviz.plotting.style import (
    CMAP_ALBULA,
    CMAP_CYCLIC,
    CMAP_HDR_ALBULA,
    CMAP_HDR_GOLDISH,
    CMAP_JET_EXT,
    CMAP_VGE,
    CMAP_VGE_HDR,
    COLORS,
    COLORS_10,
    MARKERS,
    MARKERS_MATH,
    get_color_cycle,
    get_marker_cycle,
    list_cmaps,
    set_theme,
    show_cmaps,
    theme_context,
)
from pyscattviz.plotting.transforms import radial_map, z_range, z_transform
from pyscattviz.plotting.utils import create_meshgrid, find_nearest, smart_delimiter

__all__ = [
    "CMAP_ALBULA",
    "CMAP_CYCLIC",
    "CMAP_HDR_ALBULA",
    "CMAP_HDR_GOLDISH",
    "CMAP_JET_EXT",
    "CMAP_VGE",
    "CMAP_VGE_HDR",
    "COLORS",
    "COLORS_10",
    "MARKERS",
    "MARKERS_MATH",
    "add_hlines",
    "add_patches",
    "add_region_patches",
    "add_text_box",
    "add_vlines",
    "contour",
    "correlation_matrix",
    "create_axes",
    "create_axes_inset",
    "create_axes_mosaic",
    "create_axes_ratio",
    "create_meshgrid",
    "disable_auto_sanitize",
    "enable_auto_sanitize",
    "fig_to_base64",
    "fig_to_bytes",
    "find_nearest",
    "get_color_cycle",
    "get_marker_cycle",
    "heatmap",
    "imshow",
    "imshow_z",
    "list_cmaps",
    "make_demo_data",
    "multi_hue_pairplot",
    "overlay_mask",
    "overlay_mask_on_image",
    "pairplot",
    "parallel_coords",
    "plot1d",
    "plot1d_multi",
    "plot1d_with_fit",
    "radial_map",
    "sanitize_label",
    "save_fig",
    "scatter3d",
    "set_theme",
    "show_cmaps",
    "smart_delimiter",
    "surface",
    "surface_contour",
    "theme_context",
    "wireframe",
    "z_range",
    "z_transform",
]
