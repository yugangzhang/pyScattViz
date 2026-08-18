"""Tests for the cross-platform command-line entry point."""

from __future__ import annotations

import subprocess
import sys


def test_python_module_entry_point_displays_help() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "pyscattviz", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert "Launch pyScattViz" in completed.stdout
    assert "--port" in completed.stdout
