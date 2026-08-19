"""The read-only terminal, and the list it builds for the plotting tabs."""

from pathlib import Path

import pytest

from pyscattviz.datasets import load_collection
from pyscattviz.shell import run_shell_command


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config")))


@pytest.fixture
def tree(tmp_path):
    cir = tmp_path / "giwaxs" / "cir_avg"
    cir.mkdir(parents=True)
    for name in ("UV_20_A", "UV_30_A", "UV_40_A", "AgBH_cal"):
        (cir / f"Cir_Avg_{name}.tif.csv").write_text("q_ca,iq_ca\n0.01,10\n0.1,2\n0.5,1\n")
    arrays = tmp_path / "giwaxs" / "q_image"
    arrays.mkdir()
    (arrays / "qimg_UV_20_A.tif.npz").write_bytes(b"PK\x03\x04\0\0binary")
    return tmp_path


def test_navigation_and_listing(tree):
    result = run_shell_command("cd giwaxs/cir_avg", tree)
    assert result.error is None
    assert Path(result.cwd).name == "cir_avg"
    assert len(result.rows) == 4

    result = run_shell_command("pwd", result.cwd)
    assert result.output.endswith("cir_avg")


def test_ls_accepts_a_glob(tree):
    cir = tree / "giwaxs" / "cir_avg"
    result = run_shell_command("ls *UV_2*", cir)
    assert [row["name"] for row in result.rows] == ["Cir_Avg_UV_20_A.tif.csv"]


def test_select_unions_several_patterns(tree):
    """The case that had no answer before: either UV_20 or UV_30."""

    cir = tree / "giwaxs" / "cir_avg"
    result = run_shell_command("select *UV_20* *UV_30*", cir)

    assert result.selection_changed
    assert sorted(Path(item).name for item in result.selection) == [
        "Cir_Avg_UV_20_A.tif.csv",
        "Cir_Avg_UV_30_A.tif.csv",
    ]


def test_select_then_unselect_removes_the_calibration(tree):
    cir = tree / "giwaxs" / "cir_avg"
    added = run_shell_command("select *", cir)
    assert len(added.selection) == 4

    trimmed = run_shell_command("unselect *AgBH*", cir, selection=added.selection)
    assert len(trimmed.selection) == 3
    assert all("AgBH" not in item for item in trimmed.selection)


def test_select_never_duplicates(tree):
    cir = tree / "giwaxs" / "cir_avg"
    once = run_shell_command("select *UV_20*", cir)
    twice = run_shell_command("select *UV_20*", cir, selection=once.selection)

    assert len(twice.selection) == 1
    assert not twice.selection_changed


def test_a_list_can_be_saved_and_loaded_by_name(tree):
    cir = tree / "giwaxs" / "cir_avg"
    chosen = run_shell_command("select *UV_2* *UV_3*", cir)

    saved = run_shell_command("save uv_series", cir, selection=chosen.selection)
    assert saved.error is None
    assert load_collection("uv_series")["paths"] == list(chosen.selection)

    listed = run_shell_command("lists", cir)
    assert [row["name"] for row in listed.rows] == ["uv_series"]

    reloaded = run_shell_command("load uv_series", cir, selection=())
    assert reloaded.selection == chosen.selection
    assert reloaded.selection_changed


def test_saving_an_empty_list_is_refused(tree):
    result = run_shell_command("save nothing", tree, selection=())
    assert "nothing to save" in result.error


def test_clear_empties_the_list(tree):
    cir = tree / "giwaxs" / "cir_avg"
    chosen = run_shell_command("select *", cir)
    cleared = run_shell_command("clear", cir, selection=chosen.selection)
    assert cleared.selection == ()
    assert cleared.selection_changed


def test_cat_shows_a_bounded_head_of_a_text_file(tree):
    cir = tree / "giwaxs" / "cir_avg"
    result = run_shell_command("cat Cir_Avg_UV_20_A.tif.csv -n 2", cir)

    assert result.error is None
    body = result.output.splitlines()
    assert body[1] == "q_ca,iq_ca"
    assert len(body) == 3  # header line plus the two requested rows


def test_tail_shows_the_end(tree):
    cir = tree / "giwaxs" / "cir_avg"
    result = run_shell_command("tail Cir_Avg_UV_20_A.tif.csv -n 1", cir)
    assert result.output.splitlines()[-1] == "0.5,1"


def test_cat_refuses_a_binary_file(tree):
    result = run_shell_command("cat qimg_UV_20_A.tif.npz", tree / "giwaxs" / "q_image")
    assert "not a text file" in result.error


def test_wc_counts_lines_and_matches(tree):
    cir = tree / "giwaxs" / "cir_avg"
    assert "4 lines" in run_shell_command("wc Cir_Avg_UV_20_A.tif.csv", cir).output
    assert "3 file(s)" in run_shell_command("wc *UV_*", cir).output


def test_find_searches_below_the_current_folder(tree):
    result = run_shell_command("find *UV_30*", tree)
    assert [row["name"] for row in result.rows] == ["Cir_Avg_UV_30_A.tif.csv"]


def test_du_reports_a_bounded_size(tree):
    result = run_shell_command("du", tree)
    assert result.error is None
    assert "files" in result.output


def test_help_lists_the_commands(tree):
    result = run_shell_command("help", tree)
    assert "select <pattern>" in result.output
    assert "save <name>" in result.output


@pytest.mark.parametrize(
    "command",
    ["rm -rf /", "mv a b", "cp a b", "chmod 777 a", "python evil.py", "!ls", "sudo ls"],
)
def test_nothing_that_could_change_data_is_accepted(command, tree):
    """There is no system shell behind this; unknown verbs simply do not run."""

    result = run_shell_command(command, tree)
    assert result.error is not None
    assert "Unsupported command" in result.error or "needs" in result.error


def test_an_empty_command_and_a_bad_quote_are_reported(tree):
    assert run_shell_command("", tree).error
    assert run_shell_command('cat "unclosed', tree).error


def test_cd_to_a_missing_folder_keeps_the_current_one(tree):
    result = run_shell_command("cd nowhere", tree)
    assert result.error is not None
    assert Path(result.cwd) == tree.resolve()


def test_a_remote_path_is_translated_through_a_mount(tree):
    mappings = [{"remote_root": "/nsls2/data/xxx/proposals", "local_root": str(tree)}]
    result = run_shell_command(
        "cd /nsls2/data/xxx/proposals/giwaxs/cir_avg", tree, path_mappings=mappings
    )
    assert result.error is None
    assert Path(result.cwd).name == "cir_avg"
