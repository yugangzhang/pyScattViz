import json

import pytest

from pyscattviz.data_sources import (
    add_path_mapping,
    load_path_mappings,
    save_path_mappings,
    sshfs_windows_unc,
    translate_remote_path,
)

REMOTE_ROOT = "/nsls2/data/smi/proposals"


def test_remote_path_maps_to_windows_drive():
    mappings = add_path_mapping([], REMOTE_ROOT, "Z:\\")
    translated, mapping = translate_remote_path(
        REMOTE_ROOT + "/2026-2/pass-319371/projects/microbeam_Kim", mappings
    )
    assert translated == r"Z:\2026-2\pass-319371\projects\microbeam_Kim"
    assert mapping["remote_root"] == REMOTE_ROOT


def test_remote_path_maps_to_posix_mount(tmp_path):
    mappings = add_path_mapping([], REMOTE_ROOT, str(tmp_path))
    translated, _mapping = translate_remote_path(
        REMOTE_ROOT + "/2026-2/pass-319371", mappings
    )
    assert translated == str(tmp_path / "2026-2" / "pass-319371")


def test_longest_mapping_wins():
    mappings = add_path_mapping([], "/nsls2/data", "/broad")
    mappings = add_path_mapping(mappings, REMOTE_ROOT, "/proposals")
    translated, _mapping = translate_remote_path(REMOTE_ROOT + "/2026-2", mappings)
    assert translated == "/proposals/2026-2"


def test_mapping_round_trip(tmp_path):
    config = tmp_path / "mapping.json"
    mappings = add_path_mapping([], REMOTE_ROOT, "/mounted")
    assert save_path_mappings(mappings, config) == config
    assert load_path_mappings(config) == mappings
    assert json.loads(config.read_text())[0]["remote_root"] == REMOTE_ROOT


def test_windows_sshfs_unc_and_username_validation():
    assert sshfs_windows_unc("yuzhang", REMOTE_ROOT) == (
        r"\\sshfs.r\yuzhang@sftp.nsls2.bnl.gov\nsls2\data\smi\proposals"
    )
    with pytest.raises(ValueError):
        sshfs_windows_unc("domain/user", REMOTE_ROOT)
