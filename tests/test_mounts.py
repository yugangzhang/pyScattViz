import pytest

from pyscattviz.mounts import (
    PLATFORMS,
    SFTP_HOST,
    gvfs_hint,
    make_mount_folder_command,
    method_by_label,
    method_labels,
    mount_methods,
    mount_remote_path,
    posix_quote,
    proposal_path,
    rclone_config_command,
    rclone_copy_command,
    rclone_install_command,
    rclone_mount_command,
    rclone_unmount_command,
    sftp_download_command,
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
        "fusermount3 -u '/home/a user/mount' || fusermount -u '/home/a user/mount'"
    )
    assert unmount_command(local, "macOS") == "umount '/home/a user/mount'"
    with pytest.raises(ValueError):
        unmount_command(local, "Windows")


# ---------------------------------------------------------------------------
# Free cross-platform access routes added in 0.7.0
# ---------------------------------------------------------------------------
def test_posix_quote_leaves_a_leading_tilde_expandable():
    assert posix_quote("~/data/my giwaxs") == "~/'data/my giwaxs'"
    assert posix_quote("~") == "~"
    assert posix_quote("/plain/path") == "/plain/path"


def test_mount_methods_are_platform_specific():
    windows = {method["key"] for method in mount_methods("Windows")}
    macos = {method["key"] for method in mount_methods("macOS")}
    linux = {method["key"] for method in mount_methods("Linux")}

    # RaiDrive is Windows-only; macOS and Linux get SSHFS instead.
    assert "raidrive" in windows and "raidrive" not in macos | linux
    assert "sshfs" in macos and "sshfs" in linux and "sshfs" not in windows
    assert "gvfs" in linux and "gvfs" not in windows | macos
    # rclone, a subset copy, and a local folder work everywhere.
    for shared in ("rclone", "download", "local"):
        assert shared in windows and shared in macos and shared in linux


def test_every_platform_offers_at_least_one_mount_and_one_copy_route():
    for platform in PLATFORMS:
        kinds = {method["kind"] for method in mount_methods(platform)}
        assert {"mount", "copy", "local"} <= kinds


def test_method_lookup_by_label_and_unknown_platform():
    label = method_labels("Windows")[0]
    assert method_by_label("Windows", label)["key"] == "raidrive"
    with pytest.raises(ValueError):
        method_by_label("Windows", "Nothing like this")
    with pytest.raises(ValueError):
        mount_methods("Solaris")


def test_rclone_config_command_keeps_the_password_out_of_the_config_file():
    command = rclone_config_command("nsls2", "yuzhang")
    assert command == (
        "rclone config create nsls2 sftp host sftp.nsls2.bnl.gov "
        "user yuzhang port 22 ask_password true"
    )
    with pytest.raises(ValueError):
        rclone_config_command("nsls2", "  ")
    with pytest.raises(ValueError):
        rclone_config_command("2bad name", "yuzhang")


def test_rclone_mount_command_is_read_only_and_platform_aware():
    remote = "/nsls2/data/smi/proposals/2026-2/pass-319371"
    windows = rclone_mount_command("nsls2", remote, "Z:", "Windows")
    linux = rclone_mount_command("nsls2", remote, "~/NSLS_II_Link/smi", "Linux")

    assert windows.startswith(f"rclone mount nsls2:{remote} Z: --read-only")
    assert "--network-mode" in windows and "--daemon" not in windows
    assert "--daemon" in linux and "--network-mode" not in linux
    assert "--read-only" not in rclone_mount_command(
        "nsls2", remote, "Z:", "Windows", read_only=False
    )


def test_rclone_copy_command_can_narrow_to_one_sample():
    command = rclone_copy_command("nsls2", "/nsls2/data/x", "/home/me/data", "Linux", "*Kim*")
    assert command.endswith("--progress --include '*Kim*'")
    assert "--include" not in rclone_copy_command(
        "nsls2", "/nsls2/data/x", "/home/me/data", "Linux"
    )


def test_rclone_unmount_explains_the_windows_case():
    assert "Ctrl+C" in rclone_unmount_command("Z:", "Windows")
    assert rclone_unmount_command("/home/me/m", "macOS") == "umount /home/me/m"


def test_rclone_install_command_includes_the_fuse_driver():
    assert "WinFsp" in rclone_install_command("Windows")
    assert "macfuse" in rclone_install_command("macOS")
    assert "fuse3" in rclone_install_command("Linux")


def test_sftp_download_command_creates_the_target_and_recurses():
    remote = "/nsls2/data/smi/proposals/2026-2/pass-319371/Results/giwaxs"
    linux = sftp_download_command("yuzhang", remote, "~/data/giwaxs", "Linux")
    windows = sftp_download_command("yuzhang", remote, r"C:\data\giwaxs", "Windows")

    assert linux.splitlines()[0] == "mkdir -p ~/data/giwaxs"
    assert linux.splitlines()[1] == f"sftp -r yuzhang@{SFTP_HOST}:{remote} ~/data/giwaxs"
    assert windows.splitlines()[0].startswith("New-Item -ItemType Directory")
    with pytest.raises(ValueError):
        sftp_download_command("", remote, "~/data", "Linux")


def test_gvfs_hint_shows_the_address_and_the_resulting_local_path():
    hint = gvfs_hint("yuzhang")
    assert hint.startswith(f"sftp://yuzhang@{SFTP_HOST}/")
    assert "/run/user/$(id -u)/gvfs/sftp:host=" in hint
