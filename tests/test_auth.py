"""Tests for the optional launch password."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from pyscattviz.app.auth import PASSWORD_ENV, password_matches

APP_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app"
PAGES = [APP_DIR / "Home.py", *sorted((APP_DIR / "pages").glob("[0-9][0-9]_*.py"))]


def test_password_comparison_is_exact() -> None:
    assert password_matches("asdf", "asdf")
    assert not password_matches("asd", "asdf")
    assert not password_matches("", "asdf")


def test_no_password_means_no_login_form(monkeypatch) -> None:
    monkeypatch.delenv(PASSWORD_ENV, raising=False)
    app = AppTest.from_file(str(APP_DIR / "Home.py"), default_timeout=10).run()

    assert not app.exception
    assert not any(item.label == "Password" for item in app.text_input)


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.name)
def test_every_page_is_hidden_until_the_password_is_given(monkeypatch, page) -> None:
    monkeypatch.setenv(PASSWORD_ENV, "asdf")
    app = AppTest.from_file(str(page), default_timeout=10).run()

    assert not app.exception
    assert [item.label for item in app.text_input] == ["Password"]
    assert [item.value for item in app.title] == ["🔒 pyScattViz"]


def test_a_wrong_password_is_refused_and_the_right_one_admitted(monkeypatch) -> None:
    monkeypatch.setenv(PASSWORD_ENV, "asdf")
    app = AppTest.from_file(str(APP_DIR / "Home.py"), default_timeout=10).run()

    app.text_input[0].set_value("nope")
    app.button[0].click().run()
    assert any("Wrong password" in item.value for item in app.error)
    assert [item.value for item in app.title] == ["🔒 pyScattViz"]

    app.text_input[0].set_value("asdf")
    app.button[0].click().run()
    assert not app.exception
    assert [item.value for item in app.title] == ["🔬 pyScattViz"]
