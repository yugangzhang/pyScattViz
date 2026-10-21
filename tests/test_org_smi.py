"""An SMI project read as an org: the names (group, sample, angle, spot,
energy, arc, distance, scan), the raw frames each reduced frame was made
of, and what the org keeps about how it was measured and reduced — on a
small project written to disk as the beamline and the reduction write it.

    <cycle>/<proposal>/projects/Demo/
        user_data/900KW/   WAXS at arcs 0, 20, 40 of two films (2 angles x 3 spots)
                           and the AgBH, which is not reduced
        user_data/2M/      SAXS at arc 40 of the same, alignment scans, a snapshot
        Results/giwaxs/    the WAXS stitched over the arcs, one spot not reduced yet
        Results/gisaxs/    the SAXS
        Results/configs/   the reduction's YAML configs
        Results/Mask/      the calibrant's stitch check (not a detector)
        yz_logs/           the acquisition's logbook and alignment
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from org_experiment import write_products
from streamlit.testing.v1 import AppTest

from pyscattviz.org import cms, layouts, smi, store

PAGES = Path(__file__).parents[1] / "src" / "pyscattviz" / "app" / "pages"
has_pydataorg = importlib.util.find_spec("pyDataOrg") is not None
needs_pydataorg = pytest.mark.skipif(not has_pydataorg, reason="pyDataOrg not importable")
has_yaml = importlib.util.find_spec("yaml") is not None

FILMS = {"film_A": 6000.0, "film_B": 8000.0}  # sample: piezo y (um)
ANGLES = (0.10, 0.15)
CENTRES = {"film_A": 40000.0, "film_B": -2000.0}
OFFSETS = (-1000.0, 0.0, 1000.0)
CONFIG = """\
identity: {cycle: 2026C3, user: Demo, beamline: SMI, technique: waxs}
detector: {det_str: Pilatus900kw, energy_keV: 16.15}
calibration: {sdd_mm: 270.0, b_xy: [106, 1256], mask_path: /x/Mask/mask_waxs.npy}
geometry: {geometry: Reflection, incident_angle_from_filename: true}
paths: {in_dir: /x/user_data/900KW/, out_root: /x/Results/giwaxs/}
run:
  stitch:
    offset_y_by_arc_angle: {0: [-27.5, 0.0], 20: [-49.9, -41.1]}
"""


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def _name(sample, x, y, z, arc, scan, det, ai=None) -> str:
    angle = f"_{ai:.4f}deg" if ai is not None else ""
    return (
        f"Demo_{sample}{angle}_x{x:.2f}_y{y:.2f}_z{z:.2f}_expt1s_16150.00eV_wa{arc}"
        f"_sdd5000.0mm_id{scan}_000000_{det}.tif"
    )


@pytest.fixture
def project(tmp_path) -> Path:
    """The project; ``Results`` is ``project / "Results"``."""
    home = tmp_path / "2026-3" / "pass-000002" / "projects" / "Demo"
    scan = 1000
    spots = [(s, ai, CENTRES[s] + dx) for s in FILMS for ai in ANGLES for dx in OFFSETS]
    # The arc is the outermost loop: every spot at arc 0, then 20, then 40.
    first_scan = {}
    for arc, jitter in (("-0.0", 0.0), ("20.0", 0.01), ("40.0", 0.03)):
        for sample, ai, x in spots:
            scan += 1
            z = -4010.17 - jitter
            first_scan.setdefault((sample, ai, x), (scan, z))
            _touch(
                home
                / "user_data"
                / "900KW"
                / _name(sample, x, FILMS[sample], z, arc, scan, "WAXS", ai)
            )
            if arc == "40.0":
                saxs = _name(sample, x, FILMS[sample], z, arc, scan, "SAXS2M", ai)
                _touch(home / "user_data" / "2M" / saxs)
                write_products(home / "Results" / "gisaxs", saxs, 1.0, qc=False)
    for k, (sample, ai, x) in enumerate(spots):
        if k == len(spots) - 1:  # the newest spot is not stitched yet
            continue
        first, z = first_scan[(sample, ai, x)]
        stitched = _name(sample, x, FILMS[sample], z, "xsSTITCH", first, "WAXS", ai)
        write_products(home / "Results" / "giwaxs", stitched, 1.0 + k)
    for arc in ("-0.0", "20.0", "40.0"):
        scan += 1
        _touch(home / "user_data" / "900KW" / _name("AgBH", -36000, 2500, 2000, arc, scan, "WAXS"))
    for k in range(3):
        _touch(
            home
            / "user_data"
            / "2M"
            / f"alignment_gisaxs_16150.00eV_wa20.0_sdd5000.0mm_id{900 + k}"
            f"_00000{k}_SAXS2M.tif"
        )
    _touch(
        home / "user_data" / "2M" / "snapshot_16150.00eV_wa20.0_sdd5000.0mm_id899_000000_SAXS2M.tif"
    )
    (home / "user_data" / "OVA").mkdir(parents=True)
    (home / "Results" / "configs").mkdir(parents=True)
    (home / "Results" / "configs" / "2026C3_Demo_giwaxs.yaml").write_text(CONFIG)
    _touch(home / "Results" / "Mask" / "Stitch_Image" / "Stitch_Image_AgBH.png")
    logs = home / "yz_logs"
    logs.mkdir()
    (logs / "logbook_Demo.csv").write_text("time,scan_id,uid,sample_name\n1,2,u,a\n3,4,v,b\n")
    (logs / "alignment_Demo_GI_latest.json").write_text(json.dumps({"film_A": {"th": 0.31}}))
    return home


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path / "settings"))
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv(store.ORGS_ENV, str(tmp_path / "orgs"))
    monkeypatch.delenv(store.ORG_ENV, raising=False)


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------


def test_an_smi_name_is_read():
    gi = smi.parse_frame(
        "QYu_SR_2025S4_0.6000deg_x-39000.00_y7395.85_z-4010.18_expt1s_16150.00eV_waxsSTITCH"
        "_sdd5000.0mm_id1171467_000000_WAXS"
    )
    assert (gi["group"], gi["sample"], gi["kind"]) == ("QYu", "SR_2025S4", "static")
    assert (gi["th"], gi["x"], gi["y"], gi["z"]) == (0.6, -39000.0, 7395.85, -4010.18)
    assert (gi["energy_eV"], gi["arc_deg"], gi["arc_tag"], gi["sdd_mm"]) == (
        16150.0,
        None,
        "STITCH",
        5000.0,
    )
    assert (gi["scan"], gi["frame"], gi["det_token"], gi["exposure_s"]) == (1171467, 0, "WAXS", 1.0)

    trans = smi.parse_frame(
        "HZ_S8_Pd_500_x11800.00_y-2495.00_z2000.00_expt1s_16150.00eV_wa-0.0_sdd5000.0mm"
        "_id1172153_000000_WAXS.tif"
    )
    assert (trans["group"], trans["sample"], trans["th"], trans["arc_deg"]) == (
        "HZ",
        "S8_Pd_500",
        None,
        0.0,
    )

    series = smi.parse_frame(
        "JMayer_S1_insitu_0.1500deg_0012_360.0s_x200.00_y-400.00_z-8400.00_T25.0C_E-0.500V"
        "_expt1s_16100.00eV_wa20.0_sdd5000.0mm_id7_000003_SAXS2M.tif"
    )
    assert (series["sample"], series["kind"], series["index"], series["elapsed_s"]) == (
        "S1_insitu",
        "insitu",
        12,
        360.0,
    )
    assert (series["T_C"], series["E_V"], series["frame"]) == (25.0, -0.5, 3)

    # No group where the name before the conditions is one field.
    bare = smi.parse_frame(
        "AgBH_x-36000.00_y2500.00_z2000.00_expt1s_16150.00eV_wa40.0_sdd5000.0mm_id9_000000_SAXS2M"
    )
    assert (bare["group"], bare["sample"]) == (None, "AgBH")
    assert (
        smi.parse_frame("alignment_gisaxs_16150.00eV_wa20.0_sdd5000.0mm_id9_000000_SAXS2M.tif")
        is None
    )
    assert smi.parse_frame("film_A1_pos2_x+0.000_th+0.100_10.00s_1000600_000000_waxs.tiff") is None


# ---------------------------------------------------------------------------
# The layout
# ---------------------------------------------------------------------------


def test_an_smi_project_is_read_with_its_raw_frames(project):
    results = project / "Results"
    assert layouts.detect_layout(results) == "smi"
    assert layouts.detect_layout(project) == "smi"
    frames = layouts.index(results, "smi")
    assert set(frames["sample"]) == {"film_A", "film_B"}
    assert set(frames["group"]) == {"Demo"}
    assert len(frames) == 12 + 11  # every spot's SAXS; all but the newest stitched

    waxs = frames[frames["det_folder"] == "giwaxs"]
    assert waxs["stitched"].all() and waxs["raw"].isna().all()
    assert set(waxs["arcs"]) == {"0, 20, 40"}
    one = waxs.iloc[0]
    assert len(one["raw_scans"].split(", ")) == 3  # its three arcs, z read anew at each
    saxs = frames[frames["det_folder"] == "gisaxs"]
    assert set(saxs["arcs"]) == {"40"}
    assert saxs["raw"].map(lambda p: Path(p).parent.name).eq("2M").all()

    table = cms.sample_table(frames).set_index("sample")
    assert table.loc["film_A", "group"] == "Demo"
    assert table.loc["film_A", "angles"] == "0.1, 0.15"
    assert table.loc["film_A", "spots"] == 3
    assert table.loc["film_A", "x_um"] == "39000–41000"
    assert table.loc["film_A", "energy_keV"] == "16.15"
    assert table.loc["film_A", "arcs_deg"] == "0, 20, 40"

    progress = layouts.progress(results, "smi").set_index("det_folder")
    assert "Mask" not in progress.index
    assert progress.loc["giwaxs", "raw"] == 36 and progress.loc["giwaxs", "to_reduce"] == 1
    assert progress.loc["gisaxs", "raw"] == 12 and progress.loc["gisaxs", "to_reduce"] == 0


def test_an_smi_project_is_named_and_kept_beside_its_data(project):
    results = project / "Results"
    assert store.title(results) == "Demo · 2026-3 · pass-000002"
    assert store.title(project) == "Demo · 2026-3 · pass-000002"
    assert store.suggest_store(results) == project / "Org" / "Demo.json"
    assert store.suggest_store(project) == project / "Org" / "Demo.json"
    # A group's own folder below Results (TSAXS384/Results/UPenn).
    assert store.suggest_store(results / "UPenn") == project / "Org" / "Demo_UPenn.json"
    assert store.title(Path("/home/me/projects/thing")) == "thing"


# ---------------------------------------------------------------------------
# What the org keeps
# ---------------------------------------------------------------------------


def test_how_the_samples_were_measured(project):
    found = smi.describe(project / "Results", layouts.index(project / "Results", "smi"))
    assert found["beamline"] == "SMI (12-ID)"
    assert (found["cycle"], found["proposal"], found["project"]) == (
        "2026-3",
        "pass-000002",
        "Demo",
    )
    plan = found["strategy"]
    assert plan["geometry"] == "grazing incidence"  # the AgBH, in transmission, aside
    assert plan["groups"] == ["Demo"] and plan["calibrants"] == ["AgBH"]
    assert plan["incident_angles_deg"] == [0.1, 0.15]
    assert plan["arcs_deg"] == {"SAXS2M": [40.0], "WAXS": [0.0, 20.0, 40.0]}
    assert plan["spots_per_sample"] == 3
    assert plan["spot_offsets_um"] == {"x": [-1000.0, 0.0, 1000.0], "y": [0.0]}
    assert plan["energy_keV"] == [16.15] and plan["sdd_mm"] == [5000.0]
    raw = found["acquisition"]
    assert set(raw) == {"2M", "900KW", "OVA"}
    assert raw["900KW"]["frames"] == 39 and raw["900KW"]["arcs_deg"] == [0.0, 20.0, 40.0]
    assert raw["2M"]["other"] == {
        "alignment_gisaxs": {"frames": 3, "scans": [900, 902]},
        "snapshot": {"frames": 1, "scans": [899, 899]},
    }
    assert raw["2M"]["written"] is not None
    assert found["logs"]["logbooks"]["logbook_Demo.csv"]["rows"] == 2
    assert found["logs"]["alignments"]["alignment_Demo_GI_latest"] == {"film_A": {"th": 0.31}}
    json.dumps(found)  # all of it is JSON


@pytest.mark.skipif(not has_yaml, reason="PyYAML not importable")
def test_the_reduction_configs_are_kept_as_written(project):
    found = smi.reduction(project / "Results", base=project / "Org")
    config = found["2026C3_Demo_giwaxs"]
    assert config["file"] == "../Results/configs/2026C3_Demo_giwaxs.yaml"
    assert config["config"]["calibration"]["b_xy"] == [106, 1256]
    held = smi.describe(project / "Results")["reduction"]["2026C3_Demo_giwaxs"]["config"]
    assert held["run"]["stitch"]["offset_y_by_arc_angle"] == {
        "0": [-27.5, 0.0],
        "20": [-49.9, -41.1],
    }


@needs_pydataorg
def test_an_smi_org_keeps_how_it_was_measured(project, settings):
    results = project / "Results"
    org = store.create_org(store.suggest_store(results), results)
    assert org.path == project / "Org" / "Demo.json"
    saved = json.loads(Path(org.path).read_text())
    assert saved["project"]["name"] == "Demo · 2026-3 · pass-000002"
    assert sorted(s["sample_id"] for s in saved["samples"]) == ["film_A", "film_B"]
    kept = saved["project"]["extensions"]["pyscattviz"]
    assert kept["source"] == {"layout": "smi", "root": "../Results", "options": {}}
    assert kept["beamline"]["acquisition"]["2M"]["folder"] == "../user_data/2M"
    assert kept["beamline"]["strategy"]["spots_per_sample"] == 3

    film = next(s for s in saved["samples"] if s["sample_id"] == "film_A")
    params = film["stages"]["Results"]["params"]
    assert (params["group"], params["arcs_deg"], params["energy_keV"]) == (
        "Demo",
        "0, 20, 40",
        "16.15",
    )
    links = [
        m for m in film["measurements"] if m["modality"] == "iq" and m["role"] == "giwaxs_th0.100"
    ]
    assert len(links[0]["meta"]["scans"]) == len(links[0]["paths"]) == 3

    again = store.open_org(org.path)
    assert store.beamline(again)["strategy"]["incident_angles_deg"] == [0.1, 0.15]


@needs_pydataorg
def test_the_org_page_shows_how_it_was_measured(project, settings):
    app = AppTest.from_file(str(PAGES / "14_Org.py"), default_timeout=30)
    app.session_state["pyscattviz_active_root"] = str(project / "Results")
    app.run()
    assert not app.exception, [e.message for e in app.exception]
    assert app.selectbox(key="svorg_make_layout").value == "smi"
    assert app.text_input(key="svorg_make_store").value == str(project / "Org" / "Demo.json")
    next(b for b in app.button if b.label == "Build the org").click().run()
    assert not app.exception, [e.message for e in app.exception]
    labels = [e.label for e in app.expander]
    assert any(
        label.startswith("Beamline, acquisition and reduction — NSLS-II") for label in labels
    )
