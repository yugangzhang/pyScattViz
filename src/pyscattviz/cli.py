"""Command-line launcher for the local pyScattViz web application."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

# Pages were renumbered with zero-padded prefixes in 0.7.0 so the sidebar stays
# in order past nine pages. Upgrading a clone in place does not remove the old
# files from its ``build/lib`` directory, setuptools folds them back into the
# new wheel, and Streamlit then refuses to start at all:
#
#   StreamlitAPIException: Multiple Pages specified with URL pathname
#   Data_Sources_and_Mounts. URL pathnames must be unique.
#
# The crash happens inside Streamlit before any of our code runs, so a warning
# is no use — the stale files have to go before Streamlit is launched. These are
# the exact names shipped up to 0.7.0; nothing else is touched.
LEGACY_PAGE_FILES = (
    "1_Data_Sources_and_Mounts.py",
    "2_File_Selection.py",
    "3_GISAXS_Explorer.py",
    "4_GIWAXS_Explorer.py",
    "5_Transmission_SAXS.py",
    "6_Transmission_WAXS.py",
    "7_Publication_Plot.py",
    "8_Plotting_Studio.py",
)


def remove_legacy_pages(pages_dir: Path) -> list[str]:
    """Delete pages left behind by a version before 0.7.0.

    Only the exact filenames :data:`LEGACY_PAGE_FILES` are removed, and only
    from the installed package's own ``pages`` folder. Returns the names that
    were removed so the caller can report them.
    """

    removed: list[str] = []
    for name in LEGACY_PAGE_FILES:
        stale = pages_dir / name
        try:
            if not stale.is_file():
                continue
            stale.unlink()
        except OSError:
            continue
        removed.append(name)
        # A stale .pyc would not confuse Streamlit, but leaving it behind is
        # untidy and confuses anyone reading the folder afterwards.
        for cached in (pages_dir / "__pycache__").glob(f"{stale.stem}.*.pyc"):
            try:
                cached.unlink()
            except OSError:
                pass
    return removed


def _repair_installation(pages_dir: Path) -> None:
    removed = remove_legacy_pages(pages_dir)
    if not removed:
        return
    print(
        "pyScattViz: removed "
        f"{len(removed)} page file(s) left over from a version before 0.7.0 "
        f"({', '.join(removed)}).\n"
        "They came from a stale build folder in the repository. To stop it "
        "happening again, delete that folder before the next upgrade:\n"
        "  Windows:      Remove-Item -Recurse -Force build\n"
        "  macOS/Linux:  rm -rf build",
        file=sys.stderr,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pyscattviz",
        description="Launch pyScattViz in a local web browser.",
    )
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument(
        "--address",
        default="127.0.0.1",
        help="Listening address (default: local computer only).",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    home = files("pyscattviz.app").joinpath("Home.py")
    _repair_installation(Path(str(home)).parent / "pages")
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(home),
        "--server.headless=true",
        f"--server.port={args.port}",
        f"--server.address={args.address}",
        "--browser.gatherUsageStats=false",
    ]
    environment = os.environ.copy()
    environment.setdefault("MPLBACKEND", "Agg")
    try:
        return_code = subprocess.call(command, env=environment)
    except KeyboardInterrupt:
        return
    raise SystemExit(return_code)
