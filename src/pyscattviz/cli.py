"""Command-line launcher for the local pyScattViz web application."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

# Pages were renumbered with zero-padded prefixes in 0.7.0. A clone that was
# installed in place before the update can keep a stale ``build/lib`` copy of
# the old single-digit files, which setuptools then folds back into the new
# wheel and Streamlit shows twice in the sidebar.
_LEGACY_PAGE = re.compile(r"^[1-9]_[A-Za-z]")


def _warn_about_legacy_pages(pages_dir: Path) -> None:
    try:
        stale = sorted(
            item.name for item in pages_dir.iterdir() if _LEGACY_PAGE.match(item.name)
        )
    except OSError:
        return
    if not stale:
        return
    print(
        "pyScattViz: this installation still contains pages from an earlier "
        f"version ({', '.join(stale)}), so the sidebar will list some pages "
        "twice.\n"
        "Fix it by deleting the stale build folder in the repository and "
        "installing again:\n"
        "  Windows:      Remove-Item -Recurse -Force build; "
        ".\\.venv\\Scripts\\python.exe -m pip install --upgrade .\n"
        "  macOS/Linux:  rm -rf build && ./.venv/bin/python -m pip install --upgrade .",
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
    _warn_about_legacy_pages(Path(str(home)).parent / "pages")
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
