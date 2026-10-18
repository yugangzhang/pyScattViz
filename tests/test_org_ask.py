"""Asking about an org, and a model proposing how to read a folder: what the
model is given, how it is run, what is accepted back — with a stand-in for
the model, on a small experiment."""

from __future__ import annotations

import datetime as dt
import json
import sys

import pytest
from org_experiment import make_experiment

from pyscattviz.org import ask, cms, layouts, store


def _stand_in(script: str) -> ask.Backend:
    return ask.Backend("stand-in", "stand-in", (sys.executable, "-c", script), model="echo")


@pytest.fixture(scope="module")
def experiment(tmp_path_factory):
    return make_experiment(tmp_path_factory.mktemp("ask"))


@pytest.fixture(scope="module")
def frames(experiment):
    return cms.index_experiment(experiment)


def test_a_named_sample_is_found_by_its_whole_name(frames):
    samples = cms.sample_table(frames)
    assert ask.mentioned("compare film_A10 with film_A1", samples) == [
        ("1_Static", "film_A10"),
        ("1_Static", "film_A1"),
    ]
    assert ask.mentioned("what is film_A100?", samples) == []
    assert ask.mentioned("FILM_C_HUMID_70C_2nd, please", samples) == [
        ("2_Humidity", "film_C_humid_70C_2nd")
    ]
    assert ask.mentioned("", samples) == []


def test_the_context_holds_progress_samples_and_named_frames(frames, experiment):
    progress = cms.progress_table(experiment)
    source = store.Source("cms", "../demo_run")
    text = ask.context(
        frames,
        question="How is film_A1 doing?",
        progress=progress,
        source=source,
        root=experiment,
        today=dt.date(2026, 1, 2),
    )
    assert text.startswith("# demo_run — ") and "Today 2026-01-02." in text
    assert "Read as: CMS experiment" in text
    assert "## Raw against reduced, per folder and detector" in text
    assert "## Samples (5; 14 reduced frames in all)" in text
    assert "## Frames of film_A1 in 1_Static (3)" in text
    assert "Frames of film_A10" not in text
    assert "1000605" in text and "1.0006e+06" not in text and "NaT" not in text
    # Names only: nothing of where the data is on this machine.
    assert str(experiment.parent) not in text
    assert len(ask.context(frames, question="film_A1", limit=500)) <= 500


def test_ask_returns_the_model_answer(frames):
    backend = _stand_in("import sys; print('ANSWER:' + str(len(sys.stdin.read())))")
    answer = ask.ask("How many samples?", frames, backend=backend, timeout=60)
    assert answer.error == ""
    assert answer.text == f"ANSWER:{answer.prompt_chars}"
    assert answer.backend == "stand-in" and answer.seconds >= 0
    full = ask.prompt("How many samples?", answer.context, [("Before?", "Yes.")])
    assert "Question: How many samples?" in full and "Q: Before?" in full


def test_a_failing_or_missing_model_is_an_error_not_an_exception(frames):
    missing = ask.Backend("none", "none", ("pyscattviz-no-such-tool-xyz",))
    answer = ask.ask("Hello?", frames, backend=missing)
    assert answer.text == "" and "not installed" in answer.error
    failing = _stand_in(
        "import sys; sys.stdin.read(); print('broken', file=sys.stderr); sys.exit(3)"
    )
    answer = ask.ask("Hello?", frames, backend=failing)
    assert "exit 3" in answer.error and "broken" in answer.error
    slow = _stand_in("import time; time.sleep(5)")
    answer = ask.ask("Hello?", frames, backend=slow, timeout=0.5)
    assert "longer than" in answer.error


def test_asking_is_on_locally_and_off_on_a_shared_server_unless_turned_on(monkeypatch):
    monkeypatch.delenv(ask.ASK_ENV, raising=False)
    monkeypatch.delenv(ask.PASSWORD_ENV, raising=False)
    assert ask.enabled()
    monkeypatch.setenv(ask.PASSWORD_ENV, "secret")
    assert not ask.enabled()
    monkeypatch.setenv(ask.ASK_ENV, "1")
    assert ask.enabled()
    monkeypatch.setenv(ask.ASK_ENV, "off")
    monkeypatch.delenv(ask.PASSWORD_ENV)
    assert not ask.enabled()


def test_the_users_own_models_come_first(monkeypatch, tmp_path):
    (tmp_path / "config.toml").write_text('model = "m-1"\nmodel_provider = "p"\n')
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    monkeypatch.setenv("SV_TEST_KEY", "k-1")
    (tmp_path / "ask.json").write_text(
        json.dumps(
            {
                "models": [
                    {"tool": "codex", "model": "m-2"},
                    {"tool": "codex", "model": "m-3", "note": "fast"},
                    {"tool": "nope"},
                ],
                "env": {"TOOL_KEY": "$SV_TEST_KEY", "UNSET": "$SV_TEST_UNSET"},
            }
        )
    )
    monkeypatch.setenv(ask.CONFIG_ENV, str(tmp_path / "ask.json"))
    monkeypatch.delenv(ask.DEFAULT_ENV, raising=False)
    every = ask.backends(include_missing=True)
    assert [b.key for b in every[:3]] == ["codex:m-2", "codex:m-3", "claude"]
    assert every[1].label == "codex · m-3 (p, fast)"
    assert every[0].env == {"TOOL_KEY": "k-1"}
    monkeypatch.setenv(ask.DEFAULT_ENV, "m-3")
    assert ask.backends(include_missing=True)[0].key == "codex:m-3"


# ---------------------------------------------------------------------------
# Proposing how a folder is read
# ---------------------------------------------------------------------------


def test_a_proposal_is_checked_before_anything_is_built():
    good = ask.parse_proposal(
        '```json\n{"layout": "products", "options": {"sample_pattern": '
        '"^(?P<sample>.+?)_th(?P<th>[0-9.]+)"}, "name": "run", '
        '"why": "product folders"}\n```'
    )
    assert good.ok and good.layout == "products" and good.name == "run"
    assert good.options == {"sample_pattern": "^(?P<sample>.+?)_th(?P<th>[0-9.]+)"}
    for reply, error in [
        ("I cannot tell.", "no JSON object"),
        ('{"layout": "cms", "options": [1]}', "options must be an object"),
        ('{"layout": "nope"}', "no layout 'nope'"),
        ('{"layout": "cms", "options": {"sample_pattern": "x"}}', "takes ['folders']"),
        ('{"layout": "products", "options": {"sample_pattern": "(?P<who>.+)"}}', "names ['who']"),
        ('{"layout": "products", "options": {"sample_pattern": "(?P<th>.+)"}}', "(?P<sample>"),
        ('{"layout": "products", "options": {"sample_pattern": "(?P<sample>"}}', "compile"),
        ('{"layout": "products", "options": {"kind": "moving"}}', "kind must be"),
    ]:
        found = ask.parse_proposal(reply)
        assert not found.ok and error in found.error, (reply, found.error)


def test_propose_source_shows_the_model_names_only(experiment):
    reply = json.dumps(
        {
            "layout": "cms",
            "options": {"folders": ["2_Humidity"]},
            "name": "demo",
            "why": "experiment folders",
        }
    )
    backend = _stand_in(f"import sys; sys.stdin.read(); print({reply!r})")
    found = ask.propose_source(experiment, backend=backend, hint="humidity only", timeout=60)
    assert found.ok, found.error
    assert (found.layout, found.options, found.name) == ("cms", {"folders": ["2_Humidity"]}, "demo")
    assert found.context.startswith("demo_run/") and "cir_avg/" in found.context
    assert str(experiment.parent) not in found.context
    assert layouts.index(experiment, found.layout, found.options)["folder"].unique().tolist() == [
        "2_Humidity"
    ]
    broken = ask.propose_source(experiment, backend=_stand_in("print('no idea')"), timeout=60)
    assert not broken.ok and "no JSON object" in broken.error
