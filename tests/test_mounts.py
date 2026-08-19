import pytest

from pyscattviz.mounts import (
    SFTP_HOST,
    make_mount_folder_command,
    mount_remote_path,
    proposal_path,
    sftp_test_command,
    sshfs_mount_command,
    suggested_mount_folder,
    unmount_command,
)


@pytest.mark.parametrize(
    ("beamline", "cycle", "proposal", "expected"),
    [
        (
            "SMI",
            "2026-2",
            "319371",
            "/nsls2/data/smi/proposals/2026-2/pass-319371",
        ),
        (
            "cms",
            "2025-3",
            "pass-123456",
            "/nsls2/data/cms/proposals/2025-3/pass-123456",
        ),
    ],
)
def test_proposal_path(beamline, cycle, proposal, expected):
    assert proposal_path(beamline, cycle, proposal) == expected


@pytest.mark.parametrize(
    ("beamline", "cycle", "proposal"),
    [
        ("other", "2026-2", "319371"),
        ("SMI", "2026-4", "319371"),
        ("SMI", "2026-2", "31937"),
    ],
)
def test_proposal_path_rejects_invalid_values(beamline, cycle, proposal):
    with pytest.raises(ValueError):
        proposal_path(beamline, cycle, proposal)


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        ("Proposal", "/nsls2/data/smi/proposals/2026-2/pass-319371"),
        ("Beamline proposals", "/nsls2/data/smi/proposals"),
        ("NSLS-II data", "/nsls2/data"),
        ("Custom", "/nsls2/data/smi/proposals"),
    ],
)
def test_mount_remote_path_scopes(scope, expected):
    assert (
        mount_remote_path(
            scope,
            "SMI",
            "2026-2",
            "319371",
            "/nsls2/data/smi/proposals/",
        )
        == expected
    )


def test_custom_mount_path_stays_inside_nsls2_data():
    with pytest.raises(ValueError):
        mount_remote_path("Custom", "SMI", custom_path="/etc")
    with pytest.raises(ValueError):
        mount_remote_path("Custom", "SMI", custom_path="/nsls2/data/../users")


def test_suggested_mount_folder_matches_scope():
    assert suggested_mount_folder("SMI", "319371").name == "smi-pass-319371"
    assert suggested_mount_folder("CMS", "", "Beamline proposals").name == "cms-proposals"
    assert suggested_mount_folder("SMI", "", "NSLS-II data").name == "nsls2-data"


def test_sftp_and_sshfs_commands_are_copy_pasteable_and_quote_spaces():
    remote = "/nsls2/data/smi/proposals/2026-2/pass-319371"
    local = "/home/a user/NSLS II/pass-319371"

    assert sftp_test_command("yuzhang") == f"sftp yuzhang@{SFTP_HOST}"
    assert make_mount_folder_command(local) == "mkdir -p '/home/a user/NSLS II/pass-319371'"
    command = sshfs_mount_command("yuzhang", remote, local)
    assert f"yuzhang@{SFTP_HOST}:{remote}/" in command
    assert command.endswith("'/home/a user/NSLS II/pass-319371'")
    assert "reconnect" in command


def test_unmount_commands():
    local = "/home/a user/mount"
    assert unmount_command(local, "Linux") == (
        "fusermount3 -u '/home/a user/mount' || "
        "fusermount -u '/home/a user/mount'"
    )
    assert unmount_command(local, "macOS") == "umount '/home/a user/mount'"
    with pytest.raises(ValueError):
        unmount_command(local, "Windows")
