"""Independent transmission SAXS workflow."""

from __future__ import annotations

import runpy

runpy.run_module(
    "pyscattviz.app.components.transmission_explorer_page",
    init_globals={"EXPLORER_MODE": "tsaxs"},
)
