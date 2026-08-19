import json

import pytest

from pyscattviz.datasets import (
    collection_file,
    collections_dir,
    delete_collection,
    list_collections,
    load_collection,
    normalize_paths,
    safe_collection_name,
    save_collection,
)


@pytest.fixture
def config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path / "config"))
    return tmp_path


def test_safe_collection_name_sanitizes_and_rejects_empty_names():
    assert safe_collection_name("  microbeam Kim / giwaxs ") == "microbeam_Kim_giwaxs"
    assert safe_collection_name("2026-2_pass-319371") == "2026-2_pass-319371"
    with pytest.raises(ValueError):
        safe_collection_name("///")


def test_collections_live_under_the_configuration_folder(config_home):
    assert collections_dir() == config_home / "config" / "collections"
    assert collection_file("a b").name == "a_b.json"


def test_normalize_paths_keeps_order_and_drops_duplicates_and_comments():
    result = normalize_paths(
        ["/a/b", ' "/a/b" ', "# note", "", "/c/d"],
    )
    assert result == ["/a/b", "/c/d"]


def test_normalize_paths_translates_a_remote_path_through_a_mapping():
    mappings = [{"remote_root": "/nsls2/data/smi/proposals", "local_root": "/mnt/smi"}]
    result = normalize_paths(
        ["/nsls2/data/smi/proposals/2026-2/pass-319371/Results/giwaxs"], mappings
    )
    assert result == ["/mnt/smi/2026-2/pass-319371/Results/giwaxs"]


def test_save_and_load_a_collection_round_trip(config_home):
    written = save_collection(
        "microbeam Kim", ["/mnt/a", "/mnt/b"], "0.10 and 0.15 deg"
    )
    assert written.name == "microbeam_Kim.json"

    payload = load_collection("microbeam Kim")
    assert payload["paths"] == ["/mnt/a", "/mnt/b"]
    assert payload["note"] == "0.10 and 0.15 deg"
    assert payload["saved"].endswith("UTC")


def test_saving_the_same_name_replaces_the_earlier_collection(config_home):
    save_collection("set", ["/a"])
    save_collection("set", ["/a", "/b"])
    assert load_collection("set")["paths"] == ["/a", "/b"]
    assert len(list_collections()) == 1


def test_list_collections_reports_counts_and_skips_broken_files(config_home):
    save_collection("good", ["/a", "/b"])
    broken = collections_dir() / "broken.json"
    broken.write_text("{not json")
    wrong_shape = collections_dir() / "wrong.json"
    wrong_shape.write_text(json.dumps({"name": "wrong"}))

    summaries = list_collections()
    assert [item["name"] for item in summaries] == ["good"]
    assert summaries[0]["count"] == 2


def test_loading_a_missing_or_invalid_collection_raises(config_home):
    with pytest.raises(ValueError):
        load_collection("nothing_here")
    bad = collections_dir()
    bad.mkdir(parents=True, exist_ok=True)
    (bad / "bad.json").write_text("[]")
    with pytest.raises(ValueError):
        load_collection("bad")


def test_delete_collection_reports_whether_it_removed_anything(config_home):
    save_collection("temporary", ["/a"])
    assert delete_collection("temporary") is True
    assert delete_collection("temporary") is False


def test_list_collections_on_a_fresh_installation_is_empty(config_home):
    assert list_collections() == []
