"""Build shim that clears a stale ``build/`` directory first.

The project is configured entirely in ``pyproject.toml``; this file exists for
one reason.

pip builds a local directory in place, and setuptools copies ``src/`` into
``build/lib/`` without removing files that have since been deleted or renamed.
So after a rename — pages went from ``1_Data_Sources_and_Mounts.py`` to
``01_Data_Sources_and_Mounts.py`` in 0.7.0 — a plain ``pip install --upgrade .``
in a clone that had been installed before produces a wheel containing *both*
names. Streamlit then refuses to start, because two pages infer the same URL:

    StreamlitAPIException: Multiple Pages specified with URL pathname
    Data_Sources_and_Mounts. URL pathnames must be unique.

Asking every collaborator to remember ``rm -rf build`` before upgrading is not a
fix. Clearing the directory here is, and it costs a few seconds of recompilation
on a package this size.
"""

import shutil
from pathlib import Path

from setuptools import setup

_STALE_BUILD = Path(__file__).parent / "build" / "lib"
if _STALE_BUILD.is_dir():
    shutil.rmtree(_STALE_BUILD, ignore_errors=True)

setup()
