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


def test_a_stale_page_from_an_earlier_version_is_removed(tmp_path, capsys) -> None:
    """Streamlit refuses to start when two pages infer the same URL.

    The crash happens inside Streamlit before any of our code runs, so warning
    about it is no use — the file has to go.
    """

    from pyscattviz.cli import remove_legacy_pages

    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "01_Data_Sources_and_Mounts.py").touch()
    (pages / "1_Data_Sources_and_Mounts.py").touch()
    (pages / "8_Plotting_Studio.py").touch()

    removed = remove_legacy_pages(pages)

    assert removed == ["1_Data_Sources_and_Mounts.py", "8_Plotting_Studio.py"]
    assert not (pages / "1_Data_Sources_and_Mounts.py").exists()
    assert (pages / "01_Data_Sources_and_Mounts.py").exists()


def test_removing_stale_pages_is_idempotent(tmp_path) -> None:
    from pyscattviz.cli import remove_legacy_pages

    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "2_File_Selection.py").touch()

    assert remove_legacy_pages(pages) == ["2_File_Selection.py"]
    assert remove_legacy_pages(pages) == []


def test_only_the_known_legacy_names_are_touched(tmp_path) -> None:
    """A wildcard would be a licence to delete a user's own file."""

    from pyscattviz.cli import remove_legacy_pages

    pages = tmp_path / "pages"
    pages.mkdir()
    for name in ("01_Data_Sources_and_Mounts.py", "9_My_Own_Page.py", "notes.txt"):
        (pages / name).touch()

    assert remove_legacy_pages(pages) == []
    assert len(list(pages.iterdir())) == 3


def test_a_clean_installation_removes_nothing(tmp_path) -> None:
    from pyscattviz.cli import remove_legacy_pages

    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "01_Data_Sources_and_Mounts.py").touch()
    (pages / "11_Output_Folder.py").touch()
    (pages / "__init__.py").touch()

    assert remove_legacy_pages(pages) == []


def test_a_missing_pages_folder_is_not_an_error(tmp_path) -> None:
    from pyscattviz.cli import remove_legacy_pages

    assert remove_legacy_pages(tmp_path / "nothing_here") == []


def test_the_shipped_pages_folder_has_no_legacy_names() -> None:
    """Guards the rename itself, not just the repair for old installations."""

    from pathlib import Path

    from pyscattviz.cli import LEGACY_PAGE_FILES

    pages = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"
    shipped = {item.name for item in pages.glob("*.py")}
    assert shipped.isdisjoint(LEGACY_PAGE_FILES)
    # Every page is zero-padded, so the sidebar order survives past nine.
    numbered = sorted(name for name in shipped if name[0].isdigit())
    assert all(name[:2].isdigit() and name[2] == "_" for name in numbered)


def test_a_stale_build_directory_is_cleared_before_packaging() -> None:
    """setup.py exists only for this; without it a rename ships both names."""

    from pathlib import Path

    shim = (Path(__file__).parents[1] / "setup.py").read_text()
    assert 'Path(__file__).parent / "build" / "lib"' in shim
    assert "rmtree" in shim


def _launch(monkeypatch, *argv: str) -> dict:
    """What the launcher hands Streamlit: its environment (nothing is run)."""

    from pyscattviz import cli

    seen = {}

    def call(command, env):
        seen.update(env)
        return 0

    monkeypatch.setattr(cli.subprocess, "call", call)
    monkeypatch.setattr(sys, "argv", ["pyscattviz", *argv])
    for name in ("PYSCATTVIZ_ORG", "PYSCATTVIZ_ASK"):
        monkeypatch.delenv(name, raising=False)
    try:
        cli.main()
    except SystemExit as stop:
        assert stop.code == 0
    return seen


def test_org_and_ask_reach_the_pages(monkeypatch, tmp_path) -> None:
    org = tmp_path / "Org"
    org.mkdir()
    env = _launch(monkeypatch, "--org", str(org), "--ask")
    assert env["PYSCATTVIZ_ORG"] == str(org.resolve())
    assert env["PYSCATTVIZ_ASK"] == "on"
    env = _launch(monkeypatch)
    assert "PYSCATTVIZ_ORG" not in env and "PYSCATTVIZ_ASK" not in env


def test_an_org_that_is_not_there_stops_the_launch(monkeypatch, tmp_path, capsys) -> None:
    from pyscattviz import cli

    monkeypatch.setattr(sys, "argv", ["pyscattviz", "--org", str(tmp_path / "missing")])
    try:
        cli.main()
    except SystemExit as stop:
        assert stop.code == 2
    assert "--org: no file or folder" in capsys.readouterr().err


def test_a_pydataorg_clone_beside_this_one_is_used(monkeypatch, tmp_path) -> None:
    from pyscattviz import cli

    clone = tmp_path / "pyScattViz"
    (clone / "src" / "pyscattviz").mkdir(parents=True)
    (clone / "pyproject.toml").touch()
    here = clone / "src" / "pyscattviz" / "cli.py"
    monkeypatch.setattr(cli.importlib.util, "find_spec", lambda name: None)
    assert cli.sibling_pydataorg(here) is None
    (tmp_path / "pyDataOrg" / "pyDataOrg").mkdir(parents=True)
    (tmp_path / "pyDataOrg" / "pyDataOrg" / "__init__.py").touch()
    assert cli.sibling_pydataorg(here) == tmp_path / "pyDataOrg"
    (clone / "pyproject.toml").unlink()  # an installed copy, not a clone
    assert cli.sibling_pydataorg(here) is None
