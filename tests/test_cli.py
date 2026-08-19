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


def test_a_stale_page_from_an_earlier_version_is_reported(tmp_path, capsys) -> None:
    from pyscattviz.cli import _warn_about_legacy_pages

    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "01_Data_Sources_and_Mounts.py").touch()
    (pages / "2_File_Selection.py").touch()

    _warn_about_legacy_pages(pages)
    message = capsys.readouterr().err
    assert "2_File_Selection.py" in message
    assert "Remove-Item -Recurse -Force build" in message


def test_a_clean_installation_prints_nothing(tmp_path, capsys) -> None:
    from pyscattviz.cli import _warn_about_legacy_pages

    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "01_Data_Sources_and_Mounts.py").touch()
    (pages / "11_Output_Folder.py").touch()
    (pages / "__init__.py").touch()

    _warn_about_legacy_pages(pages)
    assert capsys.readouterr().err == ""


def test_a_missing_pages_folder_is_not_an_error(tmp_path, capsys) -> None:
    from pyscattviz.cli import _warn_about_legacy_pages

    _warn_about_legacy_pages(tmp_path / "nothing_here")
    assert capsys.readouterr().err == ""
