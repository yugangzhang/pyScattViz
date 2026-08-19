"""Independent GIWAXS workflow."""

from __future__ import annotations

import runpy

runpy.run_module(
    "pyscattviz.app.components.grazing_explorer_page",
    init_globals={"EXPLORER_MODE": "giwaxs"},
)
