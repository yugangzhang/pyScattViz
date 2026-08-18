"""Command-line launcher for the local pyScattViz web application."""

from __future__ import annotations

import argparse
import subprocess
import sys
from importlib.resources import files


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
    try:
        return_code = subprocess.call(command)
    except KeyboardInterrupt:
        return
    raise SystemExit(return_code)
