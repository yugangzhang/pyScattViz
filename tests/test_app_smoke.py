from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def test_all_streamlit_pages_start_without_local_data():
    app_dir = Path(__file__).parents[1] / "src" / "pyscattviz" / "app"
    pages = [app_dir / "Home.py", *sorted((app_dir / "pages").glob("[1-5]_*.py"))]

    for page in pages:
        app = AppTest.from_file(str(page), default_timeout=10).run()
        assert not app.exception, f"{page.name}: {[item.message for item in app.exception]}"


def test_file_selection_accepts_original_nsls2_path_through_mount_mapping(tmp_path):
    mounted_root = tmp_path / "mounted"
    result_root = mounted_root / "2026-2" / "pass-319371" / "Results" / "giwaxs"
    (result_root / "q_image").mkdir(parents=True)
    (result_root / "q_image" / "qimg_frame.tif.npz").touch()
    remote_root = "/nsls2/data/smi/proposals"
    remote_result = remote_root + "/2026-2/pass-319371/Results/giwaxs"

    page = (
        Path(__file__).parents[1]
        / "src"
        / "pyscattviz"
        / "app"
        / "pages"
        / "2_File_Selection.py"
    )
    app = AppTest.from_file(str(page), default_timeout=10)
    app.session_state["pyscattviz_path_mappings"] = [
        {"remote_root": remote_root, "local_root": str(mounted_root)}
    ]
    app.session_state["pyscattviz_file_root"] = remote_result
    app.run()

    assert not app.exception
    assert app.session_state["pyscattviz_active_root"] == str(result_root)
    assert app.multiselect[0].options == ["q-image"]


def test_file_selection_accepts_unmounted_globus_path_for_remote_workflow():
    page = (
        Path(__file__).parents[1]
        / "src"
        / "pyscattviz"
        / "app"
        / "pages"
        / "2_File_Selection.py"
    )
    app = AppTest.from_file(str(page), default_timeout=10)
    app.session_state["pyscattviz_file_root"] = (
        "/nsls2/data/smi/proposals/2026-2/pass-319371/"
        "projects/microbeam_Kim/Results/giwaxs"
    )
    app.session_state["pyscattviz_path_mappings"] = []
    app.run()

    assert not app.exception
    assert any(button.label == "Find remote product folders" for button in app.button)


def test_globus_current_folder_handoff_does_not_rewrite_widget_state():
    page = (
        Path(__file__).parents[1]
        / "src"
        / "pyscattviz"
        / "app"
        / "pages"
        / "1_Globus_and_Data_Sources.py"
    )
    remote_root = (
        "/nsls2/data/smi/proposals/2026-2/pass-319371/"
        "projects/microbeam_Kim/Results/giwaxs"
    )
    app = AppTest.from_file(str(page), default_timeout=10)
    app.session_state["pyscattviz_globus_path"] = remote_root
    app.session_state["pyscattviz_globus_collection_id"] = (
        "819379a8-47db-439d-a5ba-a2387b79add9"
    )
    app.run()
    handoff = next(
        button
        for button in app.button
        if button.label == "Use current remote folder in File Selection"
    )

    # AppTest runs this page outside Home.py's multipage registry, so mock only
    # the navigation call while still exercising Streamlit's real widget state.
    with patch("streamlit.switch_page") as switch_page:
        handoff.click().run()

    assert not app.exception
    assert app.session_state["pyscattviz_file_root"] == remote_root
    switch_page.assert_called_once_with("pages/2_File_Selection.py")
