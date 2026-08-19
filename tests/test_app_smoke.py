from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app"
PAGES_DIR = APP_DIR / "pages"


def test_all_streamlit_pages_start_without_local_data():
    pages = [APP_DIR / "Home.py", *sorted(PAGES_DIR.glob("[0-9][0-9]_*.py"))]

    for page in pages:
        app = AppTest.from_file(str(page), default_timeout=10).run()
        assert not app.exception, f"{page.name}: {[item.message for item in app.exception]}"


def test_mount_page_generates_proposal_specific_sshfs_command():
    app = AppTest.from_file(
        str(PAGES_DIR / "01_Data_Sources_and_Mounts.py"), default_timeout=10
    ).run()
    next(item for item in app.text_input if item.label == "Six-digit proposal").set_value("319371")
    next(item for item in app.text_input if item.label == "BNL username").set_value("yuzhang")
    app.run()

    assert not app.exception
    mounted_path = next(
        item for item in app.text_input if item.label == "Mounted path on this computer"
    )
    assert mounted_path.value.endswith("smi-pass-319371")
    assert any(
        "yuzhang@sftp.nsls2.bnl.gov:/nsls2/data/smi/proposals/2026-2/pass-319371/" in code.value
        for code in app.code
    )


def test_mount_page_supports_broad_nsls2_scope_and_raidrive():
    app = AppTest.from_file(
        str(PAGES_DIR / "01_Data_Sources_and_Mounts.py"), default_timeout=10
    ).run()
    next(item for item in app.selectbox if item.label == "Remote mount scope").set_value(
        "NSLS-II data"
    )
    next(item for item in app.selectbox if item.label == "Instructions for").set_value("Windows")
    app.run()

    assert not app.exception
    assert any(code.value == "/nsls2/data" for code in app.code)
    assert any("OpenBoxLab.RaiDrive" in code.value for code in app.code)
    assert any("RaiDrive has been verified" in item.value for item in app.success)


def test_file_selection_accepts_original_nsls2_path_through_mount_mapping(tmp_path):
    mounted_root = tmp_path / "mounted"
    result_root = mounted_root / "2026-2" / "pass-319371" / "Results" / "giwaxs"
    (result_root / "q_image").mkdir(parents=True)
    (result_root / "q_image" / "qimg_frame.tif.npz").touch()
    remote_root = "/nsls2/data/smi/proposals"
    remote_result = remote_root + "/2026-2/pass-319371/Results/giwaxs"

    app = AppTest.from_file(str(PAGES_DIR / "03_File_Selection.py"), default_timeout=10)
    app.session_state["pyscattviz_path_mappings"] = [
        {"remote_root": remote_root, "local_root": str(mounted_root)}
    ]
    app.session_state["pyscattviz_file_root"] = remote_result
    app.run()

    assert not app.exception
    assert app.session_state["pyscattviz_active_root"] == str(result_root)
    assert app.multiselect[0].options == ["q-image"]


def test_file_selection_requires_mount_for_original_nsls2_path():
    remote_root = (
        "/nsls2/data/smi/proposals/2026-2/pass-319371/projects/microbeam_Kim/Results/giwaxs"
    )
    app = AppTest.from_file(str(PAGES_DIR / "03_File_Selection.py"), default_timeout=10)
    app.session_state["pyscattviz_file_root"] = remote_root
    app.session_state["pyscattviz_path_mappings"] = []
    app.run()

    assert not app.exception
    assert any("not mounted" in warning.value for warning in app.warning)
    assert not any(button.label == "Scan filenames" for button in app.button)


def test_file_selection_ignores_unavailable_saved_drive_mapping():
    remote_root = (
        "/nsls2/data/smi/proposals/2026-2/pass-319371/projects/microbeam_Kim/Results/giwaxs"
    )
    app = AppTest.from_file(str(PAGES_DIR / "03_File_Selection.py"), default_timeout=10)
    app.session_state["pyscattviz_file_root"] = remote_root
    app.session_state["pyscattviz_path_mappings"] = [
        {
            "remote_root": "/nsls2/data/smi/proposals/2026-2/pass-319371",
            "local_root": "Z:\\",
        }
    ]
    app.run()

    assert not app.exception
    assert any("not mounted" in warning.value for warning in app.warning)
    assert any("unavailable" in warning.value for warning in app.warning)


def test_scattering_viewers_request_mount_for_nsls2_path():
    remote_root = (
        "/nsls2/data/smi/proposals/2026-2/pass-319371/projects/microbeam_Kim/Results/giwaxs"
    )
    for filename in (
        "04_GISAXS_Explorer.py",
        "05_GIWAXS_Explorer.py",
        "06_Transmission_SAXS.py",
        "07_Transmission_WAXS.py",
    ):
        app = AppTest.from_file(str(PAGES_DIR / filename), default_timeout=10)
        app.session_state["pyscattviz_file_root"] = remote_root
        app.session_state["pyscattviz_active_root"] = "Z:\\projects\\missing"
        app.run()

        assert not app.exception
        assert any("not mounted" in warning.value for warning in app.warning)
        assert "pyscattviz_active_root" not in app.session_state.filtered_state


def test_explorers_start_with_auto_axis_limits(tmp_path):
    """A fixed q maximum clipped real data, so the boxes now start blank.

    A CMS GIWAXS q–φ map reaches 3 A^-1 and an SMI one reaches 7; the old 3.0
    default silently cut the second in half. Blank means the panel scales to the
    frame it is showing.
    """

    expectations = [
        ("04_GISAXS_Explorer.py", "GISAXS Explorer", True),
        ("05_GIWAXS_Explorer.py", "GIWAXS Explorer", False),
        ("06_Transmission_SAXS.py", "Transmission SAXS Explorer", True),
        ("07_Transmission_WAXS.py", "Transmission WAXS Explorer", False),
    ]
    for index, (filename, title, log_q) in enumerate(expectations):
        root = tmp_path / f"result-{index}"
        cir = root / "cir_avg"
        cir.mkdir(parents=True)
        (cir / "Cir_Avg_sample.tif.csv").write_text(
            "q_ca,iq_ca\n0.01,10\n0.1,2\n", encoding="utf-8"
        )
        app = AppTest.from_file(str(PAGES_DIR / filename), default_timeout=10)
        app.session_state["pyscattviz_active_root"] = str(root)
        app.run()

        assert not app.exception
        assert app.title[0].value.endswith(title)
        limits = [item.value for item in app.number_input if item.label in ("q min", "q max")]
        assert limits and all(value is None for value in limits)
        # The geometries stay decoupled in the things that are genuinely theirs.
        log_widget = next(item for item in app.checkbox if item.label == "log q (1D)")
        assert log_widget.value is log_q


def test_the_geometry_preset_still_fills_mode_specific_limits(tmp_path):
    for filename, state, q_max in (
        ("04_GISAXS_Explorer.py", "gisaxs", 0.5),
        ("05_GIWAXS_Explorer.py", "giwaxs", 3.0),
        ("06_Transmission_SAXS.py", "tsaxs", 0.5),
        ("07_Transmission_WAXS.py", "twaxs", 3.5),
    ):
        root = tmp_path / state
        (root / "cir_avg").mkdir(parents=True)
        (root / "cir_avg" / "Cir_Avg_sample.tif.csv").write_text(
            "q_ca,iq_ca\n0.01,10\n0.1,2\n", encoding="utf-8"
        )
        app = AppTest.from_file(str(PAGES_DIR / filename), default_timeout=15)
        app.session_state["pyscattviz_active_root"] = str(root)
        app.run()

        next(
            item for item in app.button if item.key == f"pyscattviz_{state}_preset_ranges"
        ).click().run()

        assert not app.exception
        assert app.session_state[f"pyscattviz_{state}_d_q_hi"] == q_max
        # The preset also restores the historical 0 … 180 phi window.
        assert app.session_state[f"pyscattviz_{state}_c_phi_hi"] == 180.0


def test_clearing_the_limits_returns_every_box_to_auto(tmp_path):
    root = tmp_path / "giwaxs"
    (root / "cir_avg").mkdir(parents=True)
    (root / "cir_avg" / "Cir_Avg_sample.tif.csv").write_text(
        "q_ca,iq_ca\n0.01,10\n0.1,2\n", encoding="utf-8"
    )
    app = AppTest.from_file(str(PAGES_DIR / "05_GIWAXS_Explorer.py"), default_timeout=15)
    app.session_state["pyscattviz_active_root"] = str(root)
    app.run()
    next(item for item in app.button if item.key == "pyscattviz_giwaxs_preset_ranges").click().run()
    assert app.session_state["pyscattviz_giwaxs_d_q_hi"] == 3.0

    next(item for item in app.button if item.key == "pyscattviz_giwaxs_clear_ranges").click().run()

    assert not app.exception
    assert app.session_state["pyscattviz_giwaxs_d_q_hi"] is None


def test_mount_page_offers_free_alternatives_on_every_platform():
    for platform, expected in (
        ("Windows", "RaiDrive (mount a drive letter)"),
        ("macOS", "SSHFS (mount a folder)"),
        ("Linux", "SSHFS (mount a folder)"),
    ):
        app = AppTest.from_file(
            str(PAGES_DIR / "01_Data_Sources_and_Mounts.py"), default_timeout=15
        ).run()
        next(item for item in app.selectbox if item.label == "Instructions for").set_value(platform)
        app.run()

        methods = next(item for item in app.selectbox if item.label == "Access method")
        assert methods.options[0] == expected
        assert any("rclone" in option for option in methods.options)
        assert any("Copy a subset" in option for option in methods.options)
        assert any("already on this computer" in option for option in methods.options)
        assert not app.exception


def test_mount_page_generates_the_rclone_commands():
    app = AppTest.from_file(
        str(PAGES_DIR / "01_Data_Sources_and_Mounts.py"), default_timeout=15
    ).run()
    next(item for item in app.text_input if item.label == "Six-digit proposal").set_value("319371")
    next(item for item in app.text_input if item.label == "BNL username").set_value("yuzhang")
    app.run()
    next(item for item in app.selectbox if item.label == "Access method").set_value(
        "rclone (mount, all three platforms)"
    )
    app.run()

    assert not app.exception
    codes = [item.value for item in app.code]
    assert any("rclone config create nsls2 sftp" in code for code in codes)
    assert any("rclone mount nsls2:/nsls2/data/smi/proposals" in code for code in codes)
    assert any("--read-only" in code for code in codes)


def test_mount_page_generates_a_subset_download_command():
    app = AppTest.from_file(
        str(PAGES_DIR / "01_Data_Sources_and_Mounts.py"), default_timeout=15
    ).run()
    next(item for item in app.text_input if item.label == "Six-digit proposal").set_value("319371")
    next(item for item in app.text_input if item.label == "BNL username").set_value("yuzhang")
    app.run()
    next(item for item in app.selectbox if item.label == "Access method").set_value(
        "Copy a subset to the local disk"
    )
    app.run()

    assert not app.exception
    assert any(
        "sftp -r yuzhang@sftp.nsls2.bnl.gov:/nsls2/data/smi/proposals/2026-2/pass-319371"
        in item.value
        for item in app.code
    )


def test_local_folder_method_registers_without_a_proposal(tmp_path):
    app = AppTest.from_file(
        str(PAGES_DIR / "01_Data_Sources_and_Mounts.py"), default_timeout=15
    ).run()
    next(item for item in app.selectbox if item.label == "Access method").set_value(
        "Data already on this computer"
    )
    app.run()
    next(item for item in app.text_input if item.label == "Folder on this computer").set_value(
        str(tmp_path)
    )
    app.run()
    next(
        item for item in app.button if item.label == "Register folder for the other pages"
    ).click().run()

    assert not app.exception
    assert app.session_state["pyscattviz_active_root"] == str(tmp_path)
    assert str(tmp_path) in app.session_state["pyscattviz_roots"]
