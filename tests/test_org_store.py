"""Layouts that read a data folder, and the org kept of it: made, saved
with paths relative to itself, reopened with the frames written since."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys

import numpy as np
import pytest
from org_experiment import make_experiment, write_products

from pyscattviz.org import analysis, cms, layouts, store

has_pydataorg = importlib.util.find_spec("pyDataOrg") is not None
needs_pydataorg = pytest.mark.skipif(not has_pydataorg, reason="pyDataOrg not importable")


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path / "settings"))
    monkeypatch.setenv(store.ORGS_ENV, str(tmp_path / "orgs"))
    return tmp_path / "settings"


@pytest.fixture
def proposal(tmp_path):
    """``<base>/<cycle>/<proposal>/experiments/demo_run`` and its Org folder."""
    root = make_experiment(tmp_path / "2026-1" / "pass-000001" / "experiments")
    return root


# ---------------------------------------------------------------------------
# Layouts
# ---------------------------------------------------------------------------


def test_a_cms_experiment_is_recognised(proposal, tmp_path):
    assert layouts.detect_layout(proposal) == "cms"
    assert layouts.detect_layout(tmp_path / "nothing") is None
    assert len(layouts.index(proposal, "cms")) == 14
    only = layouts.progress(proposal, "cms", {"folders": ["2_Humidity"]})
    assert only["folder"].tolist() == ["2_Humidity"]


def test_product_folders_read_with_a_pattern(tmp_path):
    root = tmp_path / "beamtime"
    for sample, temp in (("blend_A", 25), ("blend_A", 80), ("blend_B", 25)):
        write_products(root / "day1" / "saxs", f"{sample}_{temp}C_x0.50_th0.12_saxs.tiff", 1.0)
    write_products(root / "loose", "odd_name.tiff", 1.0, qc=False)
    assert layouts.detect_layout(root) == "products"
    pattern = r"^(?P<sample>.+?)_(?P<T_C>\d+)C_x(?P<x>[-\d.]+)_th(?P<th>[\d.]+)"
    frames = layouts.index(root, "products", {"sample_pattern": pattern})
    assert list(frames.columns) == list(cms.FRAME_COLUMNS)
    assert sorted(frames["folder"].unique()) == ["beamtime", "day1"]
    series = frames[frames["folder"] == "day1"]
    assert set(series["det_folder"]) == {"saxs"}
    assert sorted(series["sample"]) == ["blend_A", "blend_A", "blend_B"]
    assert sorted(series["T_C"]) == [25.0, 25.0, 80.0]
    assert set(series["th"]) == {0.12} and set(series["kind"]) == {"static"}
    loose = frames[frames["folder"] == "beamtime"]
    assert loose["sample"].tolist() == ["odd_name"]  # not matched: read as a CMS name
    insitu = layouts.index(root, "products", {"sample_pattern": pattern, "kind": "insitu"})
    assert set(insitu["kind"]) == {"insitu"}
    progress = layouts.progress(root, "products")
    assert progress.set_index("folder").loc["day1", ["cir", "to_reduce"]].tolist() == [3, 0]


def test_reading_a_folder_needs_no_streamlit(tmp_path):
    """The org modules are for notebooks and scripts too: no GUI comes with them."""
    write_products(tmp_path / "run" / "saxs", "a_th0.10_saxs.tiff", 1.0)
    script = (
        "import sys\n"
        "from pyscattviz.org import ask, cms, layouts, store\n"
        f"root = {str(tmp_path / 'run')!r}\n"
        "assert layouts.detect_layout(root) == 'products'\n"
        "assert len(layouts.index(root, 'products')) == 1\n"
        "layouts.progress(root, 'products')\n"
        "assert 'streamlit' not in sys.modules, 'streamlit was imported'\n"
    )
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_options_are_checked():
    assert layouts.check_options("cms", {"folders": []}) == {}
    with pytest.raises(ValueError, match="takes"):
        layouts.check_options("cms", {"kind": "static"})
    with pytest.raises(ValueError, match="list of folder names"):
        layouts.check_options("cms", {"folders": "1_Static"})
    with pytest.raises(KeyError):
        layouts.check_options("nope")


def test_describe_tree_shows_names_and_counts(proposal):
    text = layouts.describe_tree(proposal, examples=2)
    lines = text.splitlines()
    assert lines[0] == "demo_run/"
    assert "  1_Static/" in lines and "        cir_avg/" in lines
    assert any(line.strip().startswith("[5 files]") for line in lines)
    assert len(layouts.describe_tree(proposal, max_lines=5).splitlines()) <= 5


# ---------------------------------------------------------------------------
# Names and places
# ---------------------------------------------------------------------------


def test_names_of_an_experiment(proposal, settings, tmp_path):
    assert store.title(proposal) == "demo_run · 2026-1 · pass-000001"
    assert store.tag(proposal) == "2026-1_pass-000001_demo_run"
    assert store.suggest_store(proposal) == proposal.parent.parent / "Org" / "demo_run.json"
    loose = tmp_path / "somewhere" / "run"
    assert store.suggest_store(loose) == tmp_path / "orgs" / "run.json"


def test_a_source_is_relative_to_the_org(tmp_path):
    source = store.Source.from_dict({"layout": "cms", "root": "../experiments/run"})
    assert source.path(tmp_path / "p" / "Org") == tmp_path / "p" / "experiments" / "run"
    assert source.to_dict() == {"layout": "cms", "root": "../experiments/run", "options": {}}
    assert store.Source("cms", str(tmp_path)).path(tmp_path / "x") == tmp_path


def test_without_pydataorg_an_org_says_how_to_get_it(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "has_pydataorg", lambda: False)
    with pytest.raises(ModuleNotFoundError, match="pyScattViz\\[org\\]"):
        store.create_org(tmp_path / "x.json", make_experiment(tmp_path))


# ---------------------------------------------------------------------------
# An org
# ---------------------------------------------------------------------------


@needs_pydataorg
def test_create_save_and_reopen_beside_the_data(proposal, settings):
    where = store.suggest_store(proposal)
    org = store.create_org(where, proposal, description="a test run")
    assert org.path == where and where.is_file()
    saved = json.loads(where.read_text())
    config = saved["project"]
    assert config["description"] == "a test run"
    assert config["extensions"]["pyscattviz"]["source"] == {
        "layout": "cms",
        "root": "../experiments/demo_run",
        "options": {},
    }
    assert len(saved["samples"]) == 5
    assert str(proposal.parent) not in where.read_text()
    assert store.recent() == [str(where.resolve())]
    assert store.orgs_in(where.parent) == [where]
    assert store.is_org_file(where) and not store.is_org_file(settings / "recent_orgs.json")

    # The proposal moves (another mount): the org and its data move together.
    moved = settings.parent / "mounted" / "pass-000001"
    shutil.copytree(proposal.parent.parent, moved)
    again = store.open_org(moved / "Org" / "demo_run.json")
    assert store.data_root(again) == moved / "experiments" / "demo_run"
    q, curves, _ = again.data("film_C_humid_70C", "iq", stage="2_Humidity", role="maxs_th0.100")
    assert curves.shape == (3, 60)


@needs_pydataorg
def test_reopening_links_the_frames_written_since(proposal, settings):
    where = store.suggest_store(proposal)
    org = store.create_org(where, proposal, layout="cms", options={"folders": ["2_Humidity"]})
    linked = len(org.table(level="measurement", all_samples=True))
    org.project.samples["film_C_humid_70C"].notes = "kept"
    org.save()
    frame = (
        "film_C_humid_70C_5_250.0s_x+0.000_th+0.100_1.00s_RH60.000_T70.000C_"
        "1002005_000000_maxs.tiff"
    )
    write_products(proposal / "2_Humidity" / "maxs" / "analysis", frame, 2.0)
    again = store.open_org(where)
    assert len(again.table(level="measurement", all_samples=True)) == linked
    m = again.measurement("film_C_humid_70C", "iq", stage="2_Humidity", role="maxs_th0.100")
    assert len(m.paths) == 4  # the new frame, linked in
    assert again.project.samples["film_C_humid_70C"].notes == "kept"
    assert "film_A1" not in again.project.samples  # only the folders it was made of
    with pytest.raises(FileNotFoundError):
        store.open_org(where.with_name("missing.json"))


@needs_pydataorg
def test_an_org_store_without_a_file_name_gets_one(proposal, settings):
    org = store.create_org(settings.parent / "orgs", proposal, save=False)
    assert org.path.name == "2026-1_pass-000001_demo_run.json"
    assert not org.path.exists()


# ---------------------------------------------------------------------------
# A peak
# ---------------------------------------------------------------------------


def test_a_peak_above_its_background():
    q = np.linspace(1.0, 2.0, 1001)
    iq = 5.0 + 2.0 * q + 10.0 * np.exp(-0.5 * ((q - 1.4) / 0.02) ** 2)
    found = analysis.peak(q, iq, 1.2, 1.6)
    assert found["q_max"] == pytest.approx(1.4, abs=1e-3)
    assert found["q_centroid"] == pytest.approx(1.4, abs=1e-3)
    assert found["height"] == pytest.approx(10.0, rel=1e-3)
    assert found["fwhm"] == pytest.approx(2.3548 * 0.02, rel=1e-2)
    assert found["area"] == pytest.approx(10.0 * 0.02 * np.sqrt(2 * np.pi), rel=1e-2)
    assert found["points"] == 401
    table = analysis.peaks(q, np.vstack([iq, 2 * iq]), 1.6, 1.2)
    assert list(table.columns) == list(analysis.PEAK_COLUMNS)
    assert table["area"].iloc[1] == pytest.approx(2 * table["area"].iloc[0])
    empty = analysis.peak(q, iq, 5.0, 6.0)
    assert empty["points"] == 0 and np.isnan(empty["area"])
