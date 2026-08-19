"""The Python console: notebook-like execution, and the guard on it."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from pyscattviz.console import STARTER_SNIPPETS, is_local_only, run_snippet

PAGES_DIR = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"


@pytest.fixture(autouse=True)
def isolated_config(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path_factory.mktemp("pyscattviz_config")))
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(tmp_path_factory.mktemp("pyscattviz_output")))


@pytest.fixture
def curves(tmp_path):
    folder = tmp_path / "cir_avg"
    folder.mkdir()
    q = np.logspace(-2, 0.4, 40)
    paths = []
    for index, name in enumerate(("sampleA", "sampleB")):
        target = folder / f"Cir_Avg_{name}.tif.csv"
        pd.DataFrame({"q_ca": q, "iq_ca": (index + 1) * q**-2}).to_csv(target, index=False)
        paths.append(str(target))
    return paths


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------
def test_a_trailing_expression_is_echoed_like_a_notebook():
    namespace = {}
    result = run_snippet("a = 2\nb = 3\na * b", namespace)

    assert result.has_value
    assert result.value == 6
    assert not result.failed


def test_names_survive_between_snippets():
    namespace = {}
    run_snippet("total = 41", namespace)
    result = run_snippet("total + 1", namespace)
    assert result.value == 42


def test_printed_output_is_captured():
    result = run_snippet("print('two'); print('lines')", {})
    assert result.stdout == "two\nlines\n"
    assert not result.has_value


def test_a_statement_only_snippet_has_no_value():
    result = run_snippet("x = 1", {})
    assert not result.has_value
    assert not result.failed


def test_an_expression_evaluating_to_none_is_not_shown():
    result = run_snippet("print('hi')", {})
    assert not result.has_value


def test_an_error_is_reported_without_this_module_s_frames():
    result = run_snippet("def boom():\n    raise ValueError('bad q range')\nboom()", {})

    assert result.failed
    assert "ValueError: bad q range" in result.error
    assert "console.py" not in result.error
    # The user's own line is what they need to see.
    assert "boom" in result.error


def test_a_syntax_error_is_reported_plainly():
    result = run_snippet("def f(:", {})
    assert "SyntaxError" in result.error


def test_an_empty_snippet_says_so():
    assert run_snippet("   \n  ", {}).error == "Nothing to run."


def test_output_is_captured_even_when_the_snippet_then_fails():
    result = run_snippet("print('got here')\n1 / 0", {})
    assert result.stdout == "got here\n"
    assert "ZeroDivisionError" in result.error


@pytest.mark.parametrize("address", [None, "", "127.0.0.1", "localhost", "::1", "127.0.1.1"])
def test_loopback_addresses_are_local(address):
    assert is_local_only(address)


@pytest.mark.parametrize("address", ["0.0.0.0", "192.168.1.10", "10.0.0.2", "example.org"])
def test_anything_reachable_is_not_local(address):
    assert not is_local_only(address)


def test_every_starter_snippet_is_valid_python():
    for name, snippet in STARTER_SNIPPETS.items():
        compile(snippet, f"<{name}>", "exec")


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------
def test_the_page_starts_with_the_session_data_loaded(curves):
    app = AppTest.from_file(str(PAGES_DIR / "13_Python_Console.py"), default_timeout=300)
    app.session_state["pyscattviz_dataset_paths"] = curves
    app.run()

    assert not app.exception
    app.text_area[0].set_value("len(basket)")
    app.run()
    next(item for item in app.button if item.label == "▶ Run").click().run()

    assert app.session_state["pyscattviz_console_result"]["value"] == 2


def test_a_snippet_can_read_and_plot_the_basket(curves):
    app = AppTest.from_file(str(PAGES_DIR / "13_Python_Console.py"), default_timeout=300)
    app.session_state["pyscattviz_dataset_paths"] = curves
    app.run()

    app.text_area[0].set_value(
        "curves = [read_curve(p) for p in basket]\n"
        "fig, ax = plt.subplots()\n"
        "for c in curves:\n"
        "    ax.loglog(c['x'], c['y'])\n"
        "fig"
    )
    app.run()
    next(item for item in app.button if item.label == "▶ Run").click().run()

    assert not app.exception
    result = app.session_state["pyscattviz_console_result"]
    assert not result["error"]
    assert isinstance(result["value"], matplotlib.figure.Figure)


def test_a_failing_snippet_does_not_break_the_page(curves):
    app = AppTest.from_file(str(PAGES_DIR / "13_Python_Console.py"), default_timeout=300)
    app.session_state["pyscattviz_dataset_paths"] = curves
    app.run()

    app.text_area[0].set_value("read_curve('/no/such/file.csv')")
    app.run()
    next(item for item in app.button if item.label == "▶ Run").click().run()

    assert not app.exception
    assert app.session_state["pyscattviz_console_result"]["error"]
    assert any("raised an error" in item.value for item in app.error)


def test_the_console_refuses_to_run_on_a_reachable_address(curves, monkeypatch):
    """Typing code into a browser must not run it for the whole network."""

    import streamlit as st

    real_get_option = st.get_option
    monkeypatch.setattr(
        st,
        "get_option",
        lambda name: "0.0.0.0" if name == "server.address" else real_get_option(name),
    )

    app = AppTest.from_file(str(PAGES_DIR / "13_Python_Console.py"), default_timeout=300)
    app.session_state["pyscattviz_dataset_paths"] = curves
    app.run()

    assert not app.exception
    assert any("disabled" in item.value for item in app.error)
    assert not app.text_area


def test_code_handed_over_from_another_page_lands_in_the_editor(curves):
    app = AppTest.from_file(str(PAGES_DIR / "13_Python_Console.py"), default_timeout=300)
    app.session_state["pyscattviz_console_handoff"] = "# from Quick Plot\nlen(basket)"
    app.session_state["pyscattviz_dataset_paths"] = curves
    app.run()

    assert not app.exception
    assert "from Quick Plot" in app.text_area[0].value
