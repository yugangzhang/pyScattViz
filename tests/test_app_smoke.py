from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_all_streamlit_pages_start_without_local_data():
    app_dir = Path(__file__).parents[1] / "src" / "pyscattviz" / "app"
    pages = [app_dir / "Home.py", *sorted((app_dir / "pages").glob("[1-5]_*.py"))]

    for page in pages:
        app = AppTest.from_file(str(page), default_timeout=10).run()
        assert not app.exception, f"{page.name}: {[item.message for item in app.exception]}"
