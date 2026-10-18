"""Reading a CMS experiment from its names: frames, progress, samples, runs,
and the organiser made of them — on a small experiment written to disk."""

from __future__ import annotations

import importlib.util

import numpy as np
import pandas as pd
import pytest
from org_experiment import make_experiment

from pyscattviz.org import cms

has_pydataorg = importlib.util.find_spec("pyDataOrg") is not None


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------


def test_parse_static_stitched_frame():
    m = cms.parse_frame(
        "film_S10_pos2_x+0.001_th+0.080_10.00s_stitched_1000784_000000_waxs_temp.tiff"
    )
    assert (m["sample"], m["kind"], m["pos"], m["x"], m["th"]) == (
        "film_S10",
        "static",
        2,
        0.001,
        0.08,
    )
    assert (m["exposure_s"], m["scan"], m["frame"], m["stitched"]) == (10.0, 1000784, 0, True)
    # The exposure is not an elapsed time.
    assert m["elapsed_s"] is None and m["index"] is None


def test_parse_humidity_frame_and_dead_sensor():
    m = cms.parse_frame(
        "film_humid_RH50_228_4623.0s_x+0.000_th+0.100_1.00s_"
        "RH68.497_T69.982C_1000539_000000_maxs.tiff"
    )
    assert (m["sample"], m["kind"], m["index"], m["elapsed_s"]) == (
        "film_humid_RH50",
        "insitu",
        228,
        4623.0,
    )
    assert (m["RH"], m["T_C"], m["th"], m["exposure_s"]) == (68.497, 69.982, 0.1, 1.0)
    dead = cms.parse_frame(
        "film_dry_RT_3_120.0s_x+0.000_th+0.100_1.00s_RH661.095_T-273.150C_1000000_000000_maxs.tiff"
    )
    assert dead["RH"] is None and dead["T_C"] is None


def test_parse_spin_frame():
    m = cms.parse_frame("spin_X_1786.0s_x28.800_th0.500_0.29s_1003176_000123_maxs.tiff")
    assert (m["sample"], m["kind"], m["frame"], m["elapsed_s"]) == ("spin_X", "insitu", 123, 1786.0)
    assert m["index"] is None and m["x"] == 28.8


def test_parse_saxs_and_odd_names():
    m = cms.parse_frame("AgBH_cali_5m_13.5kev_x-0.000_th+0.000_10.00s_1000110_000000_saxs.tiff")
    assert (m["sample"], m["kind"], m["th"]) == ("AgBH_cali_5m_13.5kev", "static", 0.0)
    odd = cms.parse_frame("something.tiff")
    assert odd["sample"] == "something" and odd["th"] is None


def test_product_stem():
    assert cms.product_stem("Cir_Avg_a_b.tiff.csv", "cir") == "a_b.tiff"
    assert cms.product_stem("qimg_a.tiff.npz", "qimg") == "a.tiff"
    assert cms.product_stem("qimg_a.tiff.npz", "qphi") is None


# ---------------------------------------------------------------------------
# An experiment
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def experiment(tmp_path_factory):
    return make_experiment(tmp_path_factory.mktemp("cms"))


@pytest.fixture(scope="module")
def frames(experiment):
    return cms.index_experiment(experiment)


def test_experiment_folders_skip_per_sample_raw(experiment):
    names = [p.name for p in cms.experiment_folders(experiment)]
    assert names == ["1_Static", "2_Humidity", "3_spincoating"]
    dets = [p.name for p in cms.detector_folders(experiment / "3_spincoating")]
    assert dets == ["maxs"]  # not spin_D/


def test_index_experiment(frames):
    assert list(frames.columns) == list(cms.FRAME_COLUMNS)
    by = frames.groupby(["folder", "det_folder", "kind"]).size().to_dict()
    assert by == {
        ("1_Static", "waxs_temp", "static"): 4,
        ("2_Humidity", "maxs", "insitu"): 5,
        ("3_spincoating", "maxs", "insitu"): 5,
    }
    static = frames[frames["folder"] == "1_Static"]
    assert static["raw"].str.replace("\\", "/").str.contains("/analysis/stitched/").all()
    spin = frames[frames["folder"] == "3_spincoating"]
    assert spin["qc"].notna().sum() == 1  # QC on one frame in a few
    assert spin["frame"].tolist() == [0, 1, 2, 3, 4]


def test_only_selected_folders(experiment):
    part = cms.index_experiment(experiment, folders=["2_Humidity"])
    assert set(part["folder"]) == {"2_Humidity"}


def test_progress_table(experiment):
    p = cms.progress_table(experiment).set_index(["folder", "det_folder"])
    assert p.loc[("1_Static", "waxs_temp"), ["raw", "stitched", "cir", "to_reduce"]].tolist() == [
        10,
        5,
        4,
        1,
    ]
    assert p.loc[("1_Static", "saxs"), ["raw", "cir", "to_reduce"]].tolist() == [1, 0, 1]
    assert p.loc[("2_Humidity", "maxs"), ["raw", "cir", "to_reduce"]].tolist() == [6, 5, 1]
    assert p.loc[("3_spincoating", "maxs"), ["qc", "to_reduce"]].tolist() == [1, 0]


def test_sample_table(frames):
    s = cms.sample_table(frames).set_index(["folder", "sample"])
    a1 = s.loc[("1_Static", "film_A1")]
    assert (a1["kind"], a1["frames"], a1["angles"], a1["spots"], a1["repeats"]) == (
        "static",
        3,
        "0.08, 0.1",
        1,
        2,
    )
    run = s.loc[("2_Humidity", "film_C_humid_70C")]
    assert (run["frames"], run["time_s"], run["RH"], run["T_C"]) == (
        3,
        "0–120",
        "40.1–50.3",
        "70–70.02",
    )
    second = s.loc[("2_Humidity", "film_C_humid_70C_2nd")]
    assert second["RH"] == "38"  # the dead reading is not a value
    spin = s.loc[("3_spincoating", "spin_D")]
    assert (spin["frames"], spin["time_s"]) == (5, "0–4")
    assert np.isnan(spin["spots"])


def test_sample_params_match_the_table(frames):
    params = cms.sample_params(frames[frames["sample"] == "film_A1"])
    assert params["angles"] == "0.08, 0.1" and params["time_s"] is None


def test_run_time_and_axes(frames):
    run = cms.frames_of(frames, "2_Humidity", "film_C_humid_70C", th=0.1)
    t, label = cms.run_time(run)
    assert label == "time (s)" and t.tolist() == [0.0, 60.0, 120.0]
    rh, rh_label = cms.run_axis(run, "RH")
    assert rh_label == "RH (%)" and rh.tolist() == [40.1, 45.2, 50.3]
    spin = cms.frames_of(frames, "3_spincoating", "spin_D")
    t, label = cms.run_time(spin)
    assert label == "frame" and t.tolist() == [0, 1, 2, 3, 4]
    with pytest.raises(ValueError):
        cms.run_axis(run, "pressure")


def test_run_time_spreads_frames_of_one_scan():
    run = pd.DataFrame(
        dict(elapsed_s=[10.0, 10.0, 20.0], frame=[0, 1, 0], exposure_s=[0.5, 0.5, 0.5])
    )
    t, label = cms.run_time(run)
    assert label == "time (s)" and t.tolist() == [0.0, 0.5, 10.0]


def test_frame_label():
    assert (
        cms.frame_label(dict(kind="static", pos=2, x=0.0, th=0.1, scan=12))
        == "pos2 · x+0.000 · th0.100 · scan 12"
    )
    label = cms.frame_label(
        dict(kind="insitu", index=3, elapsed_s=60.0, frame=0, RH=45.2, T_C=70.0, scan=13)
    )
    assert label == "#3 · 60 s · RH 45.2% · 70.0°C · scan 13"


def test_stack_iq_same_and_other_grids():
    q = np.linspace(0.1, 1.0, 10)
    q2, stack = cms.stack_iq([(q, q * 2), (q, q * 3)])
    assert np.array_equal(q2, q) and stack.shape == (2, 10)
    other = np.linspace(0.5, 2.0, 16)
    _, stack = cms.stack_iq([(q, q), (other, other)])
    assert np.isnan(stack[1, :4]).all()  # outside its own range
    assert np.allclose(stack[1, 4:], q[4:])  # interpolated onto q
    assert cms.stack_iq([])[1].shape == (0, 0)


def test_evenly_spaced():
    assert cms.evenly_spaced(10, 3).tolist() == [0, 4, 9]
    assert cms.evenly_spaced(3, 12).tolist() == [0, 1, 2]
    assert cms.evenly_spaced(0, 3).size == 0


def test_link_rows_keep_look_alike_runs_apart(frames):
    rows = cms.link_rows(frames)
    first = rows[(rows["sample_id"] == "film_C_humid_70C") & (rows["modality"] == "iq")]
    assert set(first["role"]) == {"maxs_th0.100"}  # the th 0.5 frame is not reduced
    paths = first["paths"].iloc[0].split(";")
    assert len(paths) == 3 and not any("_2nd_" in p for p in paths)
    a1 = rows[(rows["sample_id"] == "film_A1") & (rows["modality"] == "qimage")]
    assert sorted(a1["role"]) == ["waxs_th0.080", "waxs_th0.100"]
    assert a1.set_index("role").loc["waxs_th0.100", "paths"].count(";") == 1


def test_recorded_path_is_relative_only_nearby(tmp_path):
    base = tmp_path / "p" / "Org"
    near = tmp_path / "p" / "experiments" / "run" / "a.csv"
    assert cms.recorded_path(near, base) == "../experiments/run/a.csv"
    far = tmp_path / "a" / "b" / "c" / "d" / "e.csv"
    deep = tmp_path / "w" / "x" / "y" / "z" / "Org"
    assert cms.recorded_path(far, deep) == str(far)
    assert cms.recorded_path(near, None) == str(near)


@pytest.mark.skipif(not has_pydataorg, reason="pyDataOrg not importable")
def test_build_organizer_save_and_reopen(frames, experiment):
    import json

    from pyDataOrg import Organizer

    store = experiment.parent / "Org" / "demo.json"
    org = cms.build_organizer(frames, store, name="demo")
    table = org.table()
    assert sorted(table.index) == [
        "film_A1",
        "film_A10",
        "film_C_humid_70C",
        "film_C_humid_70C_2nd",
        "spin_D",
    ]
    assert table.loc["film_A1", "1_Static.angles"] == "0.08, 0.1"
    m = org.measurement("film_C_humid_70C", "iq", stage="2_Humidity", role="maxs_th0.100")
    assert len(m.paths) == 3 and m.meta["det_folder"] == "maxs"
    q, curves, _ = org.data("film_C_humid_70C", "iq", stage="2_Humidity", role="maxs_th0.100")
    assert curves.shape == (3, 60)
    org.save()
    # Recorded beside the data: relative, so the two move together.
    text = store.read_text()
    assert '"../demo_run/2_Humidity/maxs/analysis/cir_avg/' in text
    assert str(experiment) not in text
    assert json.loads(text)

    again = Organizer(store)
    assert len(again.table(level="measurement", all_samples=True)) == len(
        org.table(level="measurement", all_samples=True)
    )
    q, curves, _ = again.data("film_C_humid_70C", "iq", stage="2_Humidity", role="maxs_th0.100")
    assert curves.shape == (3, 60)
    # Relinking into it replaces, never duplicates.
    cms.build_organizer(frames, None, organizer=again)
    assert len(again.table(level="measurement", all_samples=True)) == len(cms.link_rows(frames))
