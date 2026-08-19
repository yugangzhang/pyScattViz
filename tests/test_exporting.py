import json

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from pyscattviz.exporting import (
    ExportError,
    default_output_root,
    load_settings,
    resolve_output_dir,
    safe_component,
    save_arrays,
    save_matplotlib_figure,
    save_plotly_figure,
    save_settings,
    save_table,
    save_text,
    settings_file,
    timestamp_suffix,
    unique_path,
)


@pytest.fixture
def config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PYSCATTVIZ_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.delenv("PYSCATTVIZ_OUTPUT_DIR", raising=False)
    return tmp_path


def test_safe_component_removes_emoji_and_separators():
    assert safe_component("🧭 GIWAXS Explorer") == "GIWAXS_Explorer"
    assert safe_component("a/b\\c") == "a_b_c"
    assert safe_component("  ") == "pyscattviz"
    assert safe_component("", fallback="figure") == "figure"


def test_safe_component_keeps_scientific_decimal_points():
    assert safe_component("Kim_th0.1000deg_2026_08_01") == "Kim_th0.1000deg_2026_08_01"


def test_safe_component_avoids_reserved_windows_device_names():
    assert safe_component("CON") == "pyscattviz"
    assert safe_component("com1") == "pyscattviz"


def test_resolve_output_dir_builds_one_subfolder_per_tab(tmp_path):
    folder = resolve_output_dir(tmp_path, "🧭 GIWAXS Explorer", "sample A")
    assert folder == tmp_path / "GIWAXS_Explorer" / "sample_A"
    assert not folder.exists()

    created = resolve_output_dir(tmp_path, "Quick Plot", create=True)
    assert created.is_dir()


def test_resolve_output_dir_skips_empty_components_and_can_date_stamp(tmp_path):
    assert resolve_output_dir(tmp_path, "", "  ") == tmp_path
    dated = resolve_output_dir(tmp_path, "Quick Plot", date_subfolder=True)
    assert dated.parent == tmp_path / "Quick_Plot"


def test_resolve_output_dir_reports_a_folder_it_cannot_create(tmp_path):
    blocker = tmp_path / "not_a_folder"
    blocker.write_text("x")
    with pytest.raises(ExportError):
        resolve_output_dir(blocker, "Quick Plot", create=True)


def test_unique_path_never_overwrites(tmp_path):
    target = tmp_path / "curve.png"
    assert unique_path(target) == target
    target.write_bytes(b"1")
    assert unique_path(target).name == "curve_001.png"
    (tmp_path / "curve_001.png").write_bytes(b"2")
    assert unique_path(target).name == "curve_002.png"


def test_timestamp_suffix_is_sortable():
    stamp = timestamp_suffix()
    assert len(stamp) == 15 and stamp[8] == "_"


def test_save_matplotlib_figure_writes_and_auto_numbers(tmp_path):
    figure, axis = plt.subplots()
    axis.plot([1, 2, 3])
    first = save_matplotlib_figure(figure, tmp_path / "Publication_Plot", "curves")
    second = save_matplotlib_figure(figure, tmp_path / "Publication_Plot", "curves")
    plt.close(figure)

    assert first.name == "curves.png"
    assert second.name == "curves_001.png"
    assert first.parent.name == "Publication_Plot"
    assert first.stat().st_size > 0


def test_save_matplotlib_figure_can_overwrite_and_rejects_bad_formats(tmp_path):
    figure, axis = plt.subplots()
    axis.plot([1, 2])
    first = save_matplotlib_figure(figure, tmp_path, "curve", overwrite=True)
    second = save_matplotlib_figure(figure, tmp_path, "curve", overwrite=True)
    assert first == second
    with pytest.raises(ExportError):
        save_matplotlib_figure(figure, tmp_path, "curve", fmt="bmp")
    plt.close(figure)


def test_save_matplotlib_figure_keeps_a_name_with_decimal_points(tmp_path):
    figure, axis = plt.subplots()
    axis.plot([1, 2])
    written = save_matplotlib_figure(figure, tmp_path, "Kim_th0.1000deg_qphi")
    plt.close(figure)
    assert written.name == "Kim_th0.1000deg_qphi.png"


def test_save_plotly_figure_writes_html_and_json(tmp_path):
    figure = go.Figure(go.Scatter(x=[1, 2, 3], y=[1, 4, 9]))
    html = save_plotly_figure(figure, tmp_path, "quick", fmt="html")
    payload = save_plotly_figure(figure, tmp_path, "quick", fmt="json")

    assert html.suffix == ".html" and html.stat().st_size > 0
    assert json.loads(payload.read_text())["data"][0]["type"] == "scatter"
    with pytest.raises(ExportError):
        save_plotly_figure(figure, tmp_path, "quick", fmt="tif")


def test_save_table_writes_csv_and_tab_separated_text(tmp_path):
    table = pd.DataFrame({"q": [0.1, 0.2], "I": [10.0, 5.0]})
    csv_path = save_table(table, tmp_path, "curve", fmt="csv")
    txt_path = save_table(table, tmp_path, "curve", fmt="txt")

    assert csv_path.read_text().splitlines()[0] == "q,I"
    assert txt_path.read_text().splitlines()[0] == "q\tI"
    with pytest.raises(ExportError):
        save_table(table, tmp_path, "curve", fmt="xlsx")


def test_save_arrays_writes_npz_bundles_and_single_npy(tmp_path):
    bundle = {"qimg": np.ones((3, 3)), "qx": np.arange(3)}
    npz_path = save_arrays(bundle, tmp_path, "frame", fmt="npz")
    with np.load(npz_path) as archive:
        assert sorted(archive.files) == ["qimg", "qx"]

    npy_path = save_arrays(np.arange(4), tmp_path, "line", fmt="npy")
    assert np.load(npy_path).tolist() == [0, 1, 2, 3]

    with pytest.raises(ExportError):
        save_arrays(bundle, tmp_path, "frame", fmt="npy")


def test_save_text_writes_a_path_list(tmp_path):
    written = save_text("a\nb\n", tmp_path, "selected_files")
    assert written.name == "selected_files.txt"
    assert written.read_text() == "a\nb\n"


def test_settings_round_trip_and_defaults(config_home):
    defaults = load_settings()
    assert defaults["output_root"] == str(default_output_root())
    assert defaults["output_subfolder_per_tab"] is True

    save_settings({"output_root": "/tmp/figures", "output_overwrite": True})
    reloaded = load_settings()
    assert reloaded["output_root"] == "/tmp/figures"
    assert reloaded["output_overwrite"] is True
    assert reloaded["output_subfolder_per_tab"] is True
    assert settings_file().is_file()


def test_load_settings_ignores_a_corrupt_or_wrongly_typed_file(config_home):
    settings_file().parent.mkdir(parents=True, exist_ok=True)
    settings_file().write_text("{not json")
    assert load_settings()["output_subfolder_per_tab"] is True

    settings_file().write_text(json.dumps({"output_subfolder_per_tab": "yes"}))
    assert load_settings()["output_subfolder_per_tab"] is True


def test_default_output_root_honours_the_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("PYSCATTVIZ_OUTPUT_DIR", str(tmp_path / "figures"))
    assert default_output_root() == tmp_path / "figures"
