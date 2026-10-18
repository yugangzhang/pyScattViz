"""The Org pages, run as a user would: a data folder looked at (no
pyDataOrg needed), an org made and opened, a model asked — on a small
experiment written to disk, with a stand-in for the model."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import streamlit as st
from org_experiment import make_experiment
from streamlit.testing.v1 import AppTest

from pyscattviz.org import ask, store

PAGES = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"
has_pydataorg = importlib.util.find_spec("pyDataOrg") is not None
needs_pydataorg = pytest.mark.skipif(not has_pydataorg, reason="pyDataOrg not importable")


@pytest.fixture(scope="module")
def experiment(tmp_path_factory):
    return make_experiment(tmp_path_factory.mktemp("pages"))


@pytest.fixture(autouse=True)
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path / "settings"))
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv(store.ORGS_ENV, str(tmp_path / "orgs"))
    monkeypatch.delenv(store.ORG_ENV, raising=False)
    monkeypatch.delenv(ask.PASSWORD_ENV, raising=False)
    monkeypatch.delenv(ask.ASK_ENV, raising=False)


def _page(name: str, experiment=None) -> AppTest:
    app = AppTest.from_file(str(PAGES / name), default_timeout=20)
    if experiment is not None:
        app.session_state["svorg_source"] = {
            "layout": "cms",
            "root": str(experiment),
            "options": {},
        }
    return app.run()


def _ok(app: AppTest) -> AppTest:
    assert not app.exception, [e.message for e in app.exception]
    return app


def _charts(app: AppTest) -> list:
    return [c for c in app.get("plotly_chart")]


def _button(app: AppTest, label: str):
    return next(b for b in app.button if b.label == label)


def _stand_in(script: str) -> ask.Backend:
    return ask.Backend("stand-in", "stand-in", (sys.executable, "-c", script), model="echo")


def _with_model(monkeypatch, backend: ask.Backend) -> None:
    monkeypatch.setattr(ask, "backends", lambda *a, **k: [backend])
    st.cache_resource.clear()


# ---------------------------------------------------------------------------
# A folder, looked at
# ---------------------------------------------------------------------------


def test_pages_point_to_org_when_nothing_is_open():
    for name in (
        "15_Org_Overview.py",
        "16_Org_Sample.py",
        "17_Org_Compare.py",
        "18_Org_In_situ.py",
    ):
        app = _ok(_page(name))
        assert any("No data folder is open" in i.value for i in app.info), name


def test_overview(experiment):
    app = _ok(_page("15_Org_Overview.py", experiment))
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["reduced (I(q))"] == "14" and metrics["still to reduce"] == "3"
    assert metrics["raw frames"] == "22"


def test_one_sample_static_and_in_situ(experiment):
    app = _ok(_page("16_Org_Sample.py", experiment))
    assert app.selectbox(key="svorg_one_folder").value == "3_spincoating"
    assert app.selectbox(key="svorg_one_sample").value == "spin_D"
    assert app.slider(key="svorg_one_frame").value == 4  # its last frame
    app.selectbox(key="svorg_one_folder").set_value("2_Humidity").run()
    app.selectbox(key="svorg_one_sample").set_value("film_C_humid_70C").run()
    assert _ok(app).slider(key="svorg_one_frame").value == 2  # a shorter run
    app.selectbox(key="svorg_one_folder").set_value("1_Static").run()
    app.selectbox(key="svorg_one_sample").set_value("film_A1").run()
    app.select_slider(key="svorg_one_th").set_value("0.1").run()
    _ok(app)
    repeat = app.selectbox(key="svorg_one_repeat")
    assert repeat.options == ["scan 1000601", "scan 1000605"]
    assert len(_charts(app)) == 4


def test_compare_and_its_peak(experiment):
    app = _ok(_page("17_Org_Compare.py", experiment))
    app.selectbox(key="svorg_cmp_folder").set_value("1_Static").run()
    _ok(app)
    chosen = next(m for m in app.multiselect if m.label.startswith("Samples"))
    assert chosen.value == ["film_A1", "film_A10"]
    assert len(_charts(app)) == 3
    assert {"svorg_cmp_plo", "svorg_cmp_phi"} <= set(app.session_state.filtered_state)


def test_in_situ_run_against_rh(experiment):
    app = _ok(_page("18_Org_In_situ.py", experiment))
    app.selectbox(key="svorg_run_folder").set_value("2_Humidity").run()
    app.selectbox(key="svorg_run_sample").set_value("film_C_humid_70C").run()
    app.selectbox(key="svorg_run_axis").set_value("RH").run()
    _ok(app)
    assert len(_charts(app)) == 5
    app.toggle(key="svorg_run_show_qimg").set_value(True).run()
    assert len(_charts(_ok(app))) == 6
    app.slider(key="svorg_run_frame").set_value(0).run()
    app.selectbox(key="svorg_run_folder").set_value("3_spincoating").run()
    assert _ok(app).slider(key="svorg_run_frame").value == 4  # another run: its last
    assert any(c.value.startswith("5 reduced frames · frame 0–4") for c in _ok(app).caption)


def test_look_at_a_folder_without_an_org(experiment):
    app = AppTest.from_file(str(PAGES / "14_Org.py"), default_timeout=20)
    app.session_state["pyscattviz_active_root"] = str(experiment)
    _ok(app.run())
    assert app.selectbox(key="svorg_make_layout").value == "cms"
    assert {m.label: m.value for m in app.metric}["samples"] == "5"
    _button(app, "Look at it without keeping an org").click().run()
    _ok(app)
    assert app.session_state["svorg_source"]["root"] == str(experiment.resolve())
    assert "svorg_org" not in app.session_state


# ---------------------------------------------------------------------------
# An org
# ---------------------------------------------------------------------------


@needs_pydataorg
def test_build_an_org_then_open_it_with_the_launcher(experiment, tmp_path, monkeypatch):
    where = tmp_path / "Org" / "demo.json"
    app = AppTest.from_file(str(PAGES / "14_Org.py"), default_timeout=30)
    app.session_state["pyscattviz_active_root"] = str(experiment)
    _ok(app.run())
    app.text_input(key="svorg_make_store").set_value(str(where)).run()
    _button(app, "Build the org").click().run()
    _ok(app)
    saved = json.loads(where.read_text())
    assert len(saved["samples"]) == 5
    assert saved["project"]["extensions"]["pyscattviz"]["source"]["layout"] == "cms"

    # `pyscattviz --org PATH`: the pages open on it.
    monkeypatch.setenv(store.ORG_ENV, str(where.parent))
    app = _ok(_page("15_Org_Overview.py"))
    assert app.session_state["svorg_org"].path == where
    assert {m.label: m.value for m in app.metric}["reduced (I(q))"] == "14"

    # Samples selected in the org are where Compare starts.
    org = store.open_org(where)
    org.select(["film_A10"])
    app = AppTest.from_file(str(PAGES / "17_Org_Compare.py"), default_timeout=20)
    app.session_state["svorg_source"] = {"layout": "cms", "root": str(experiment), "options": {}}
    app.session_state["svorg_org"] = org
    _ok(app.run())
    app.selectbox(key="svorg_cmp_folder").set_value("1_Static").run()
    chosen = next(m for m in _ok(app).multiselect if m.label.startswith("Samples"))
    assert chosen.value == ["film_A10"]


# ---------------------------------------------------------------------------
# Ask AI
# ---------------------------------------------------------------------------


def test_ask_answers_from_the_org(experiment, monkeypatch):
    _with_model(
        monkeypatch,
        _stand_in(
            "import sys; text = sys.stdin.read(); "
            "print('5 samples' if '## Samples (5;' in text else 'no idea')"
        ),
    )
    app = _ok(_page("19_Ask_AI.py", experiment))
    app.chat_input[0].set_value("How many samples are there?").run()
    _ok(app)
    history = app.session_state["svorg_ask_history"]
    assert len(history) == 1 and history[0]["answer"]["text"] == "5 samples"
    assert history[0]["about"] == "5 samples, 14 frames"
    assert any(m.value == "5 samples" for m in app.markdown)


def test_ask_is_off_on_a_password_protected_server(experiment, monkeypatch):
    monkeypatch.setenv(ask.PASSWORD_ENV, "secret")
    app = AppTest.from_file(str(PAGES / "19_Ask_AI.py"), default_timeout=20)
    app.session_state["pyscattviz_authenticated"] = True
    app.session_state["svorg_source"] = {"layout": "cms", "root": str(experiment), "options": {}}
    app.run()
    assert not app.chat_input


def test_a_model_proposes_how_to_read_a_folder(experiment, monkeypatch):
    reply = json.dumps(
        {
            "layout": "cms",
            "options": {"folders": ["2_Humidity"]},
            "name": "humidity",
            "why": "experiment folders",
        }
    )
    _with_model(monkeypatch, _stand_in(f"import sys; sys.stdin.read(); print({reply!r})"))
    app = AppTest.from_file(str(PAGES / "14_Org.py"), default_timeout=20)
    app.session_state["pyscattviz_active_root"] = str(experiment)
    _ok(app.run())
    _button(app, "Propose how to read this folder").click().run()
    _button(_ok(app), "Use this proposal").click().run()
    _ok(app)
    assert app.text_input(key="svorg_make_cms_folders").value == "2_Humidity"
    assert app.text_input(key="svorg_make_name").value == "humidity"
    assert {m.label: m.value for m in app.metric}["samples"] == "2"
