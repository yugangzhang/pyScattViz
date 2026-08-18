from pathlib import Path

from pyscattviz.browser import _split_command, directory_size, list_directory, run_browser_command


def test_listing_and_navigation_commands(tmp_path):
    folder = tmp_path / "folder with spaces"
    folder.mkdir()
    (folder / "frame.npz").write_bytes(b"1234")

    rows, truncated = list_directory(tmp_path)
    assert not truncated
    assert rows[0]["name"].startswith("folder with spaces")

    result = run_browser_command('cd "folder with spaces"', tmp_path)
    assert result["error"] is None
    assert Path(result["cwd"]) == folder
    assert result["rows"][0]["name"] == "frame.npz"

    result = run_browser_command("pwd", folder)
    assert result["output"] == str(folder)


def test_du_and_unsupported_commands(tmp_path):
    (tmp_path / "a.dat").write_bytes(b"123")
    (tmp_path / "b.dat").write_bytes(b"45678")
    assert directory_size(tmp_path) == (8, 2, False)
    assert "8 B" in run_browser_command("du", tmp_path)["output"]
    assert "Unsupported command" in run_browser_command("rm anything", tmp_path)["error"]


def test_windows_command_split_preserves_backslashes_and_removes_quotes():
    assert _split_command(r'cd "Z:\proposal data\Results"', windows=True) == [
        "cd",
        r"Z:\proposal data\Results",
    ]


def test_cd_translates_a_remote_path_mapping(tmp_path):
    mounted = tmp_path / "2026-2" / "pass-319371"
    mounted.mkdir(parents=True)
    mappings = [
        {
            "remote_root": "/nsls2/data/smi/proposals",
            "local_root": str(tmp_path),
        }
    ]
    result = run_browser_command(
        "cd /nsls2/data/smi/proposals/2026-2/pass-319371",
        tmp_path,
        mappings,
    )
    assert result["error"] is None
    assert Path(result["cwd"]) == mounted
