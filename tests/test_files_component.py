import numpy as np
import pytest

from pyscattviz.app.components.files import collect_files, file_signature


@pytest.fixture
def tree(tmp_path):
    cir = tmp_path / "giwaxs" / "cir_avg"
    cir.mkdir(parents=True)
    for name in ("Cir_Avg_Kim_A.tif.csv", "Cir_Avg_Kim_B.tif.csv", "Cir_Avg_AgBH.tif.csv"):
        (cir / name).write_text("q,I\n1,2\n")
    arrays = tmp_path / "giwaxs" / "q_image"
    arrays.mkdir()
    np.savez(arrays / "qimg_Kim_A.tif.npz", qimg=np.ones((2, 2)))
    (tmp_path / "giwaxs" / "notes.md").write_text("not data")
    return tmp_path


def test_collect_files_expands_a_folder_and_ignores_unreadable_types(tree):
    files, truncated = collect_files([tree])
    assert not truncated
    assert len(files) == 4
    assert all(not path.endswith(".md") for path in files)


def test_collect_files_applies_the_term_lists(tree):
    files, _truncated = collect_files([tree], and_list=["Kim"], no_list=["AgBH"])
    assert len(files) == 3
    files, _truncated = collect_files([tree], or_list=["_A."])
    assert len(files) == 2


def test_collect_files_respects_an_extension_allow_list(tree):
    files, _truncated = collect_files([tree], extensions=[".npz"])
    assert len(files) == 1 and files[0].endswith(".npz")
    files, _truncated = collect_files([tree], extensions=["csv"])
    assert len(files) == 3


def test_collect_files_keeps_explicit_files_and_drops_duplicates(tree):
    one = str(tree / "giwaxs" / "cir_avg" / "Cir_Avg_Kim_A.tif.csv")
    files, _truncated = collect_files([one, one, tree / "giwaxs" / "cir_avg"])
    assert files[0] == one
    assert len(files) == 3


def test_collect_files_reports_truncation(tree):
    files, truncated = collect_files([tree], max_files=2)
    assert len(files) == 2
    assert truncated


def test_collect_files_skips_a_missing_path(tree):
    files, _truncated = collect_files(["/no/such/folder", tree / "giwaxs" / "q_image"])
    assert len(files) == 1


def test_file_signature_changes_when_the_file_changes(tmp_path):
    path = tmp_path / "curve.csv"
    path.write_text("q,I\n1,2\n")
    first = file_signature(path)
    path.write_text("q,I\n1,2\n3,4\n")
    assert file_signature(path) != first
    assert file_signature(tmp_path / "missing.csv")[2] == -1
