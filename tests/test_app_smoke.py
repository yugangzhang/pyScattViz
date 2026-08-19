from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app"
PAGES_DIR = APP_DIR / "pages"


def test_all_streamlit_pages_start_without_local_data():
    pages = [APP_DIR / "Home.py", *sorted(PAGES_DIR.glob("[1-5]_*.py"))]

    for page in pages:
        app = AppTest.from_file(str(page), default_timeout=10).run()
        assert not app.exception, f"{page.name}: {[item.message for item in app.exception]}"


def test_mount_page_generates_proposal_specific_sshfs_command():
    app = AppTest.from_file(
        str(PAGES_DIR / "1_Data_Sources_and_Mounts.py"), default_timeout=10
    ).run()
    next(item for item in app.text_input if item.label == "Six-digit proposal").set_value(
        "319371"
    )
    next(item for item in app.text_input if item.label == "BNL username").set_value(
        "yuzhang"
    )
    app.run()

    assert not app.exception
    mounted_path = next(
        item for item in app.text_input if item.label == "Mounted path on this computer"
    )
    assert mounted_path.value.endswith("smi-pass-319371")
    assert any(
        "yuzhang@sftp.nsls2.bnl.gov:/nsls2/data/smi/proposals/2026-2/pass-319371/"
        in code.value
        for code in app.code
    )


def test_file_selection_accepts_original_nsls2_path_through_mount_mapping(tmp_path):
    mounted_root = tmp_path / "mounted"
    result_root = mounted_root / "2026-2" / "pass-319371" / "Results" / "giwaxs"
    (result_root / "q_image").mkdir(parents=True)
    (result_root / "q_image" / "qimg_frame.tif.npz").touch()
    remote_root = "/nsls2/data/smi/proposals"
    remote_result = remote_root + "/2026-2/pass-319371/Results/giwaxs"

    app = AppTest.from_file(str(PAGES_DIR / "2_File_Selection.py"), default_timeout=10)
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
        "/nsls2/data/smi/proposals/2026-2/pass-319371/"
        "projects/microbeam_Kim/Results/giwaxs"
    )
    app = AppTest.from_file(str(PAGES_DIR / "2_File_Selection.py"), default_timeout=10)
    app.session_state["pyscattviz_file_root"] = remote_root
    app.session_state["pyscattviz_path_mappings"] = []
    app.run()

    assert not app.exception
    assert any("not mounted" in warning.value for warning in app.warning)
    assert not any(button.label == "Scan filenames" for button in app.button)


def test_file_selection_ignores_unavailable_saved_drive_mapping():
    remote_root = (
        "/nsls2/data/smi/proposals/2026-2/pass-319371/"
        "projects/microbeam_Kim/Results/giwaxs"
    )
    app = AppTest.from_file(str(PAGES_DIR / "2_File_Selection.py"), default_timeout=10)
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
        "/nsls2/data/smi/proposals/2026-2/pass-319371/"
        "projects/microbeam_Kim/Results/giwaxs"
    )
    for filename in (
        "3_GISAXS_GIWAXS_Explorer.py",
        "4_Transmission_SAXS_WAXS.py",
    ):
        app = AppTest.from_file(str(PAGES_DIR / filename), default_timeout=10)
        app.session_state["pyscattviz_file_root"] = remote_root
        app.session_state["pyscattviz_active_root"] = "Z:\\projects\\missing"
        app.run()

        assert not app.exception
        assert any("not mounted" in warning.value for warning in app.warning)
        assert "pyscattviz_active_root" not in app.session_state.filtered_state
