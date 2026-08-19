import numpy as np
import pandas as pd
import pytest
from PIL import Image

from pyscattviz.dataio import (
    DataReadError,
    common_prefix_suffix,
    curve_columns,
    guess_kind,
    read_arrays,
    read_curve,
    read_image,
    read_table,
    short_label,
    stack_curves,
)

Q = np.logspace(-2, 0, 40)
INTENSITY = Q**-2


@pytest.fixture
def files(tmp_path):
    """One folder holding every 1D convention I actually receive."""

    pd.DataFrame({"q_ca": Q, "iq_ca": INTENSITY}).to_csv(
        tmp_path / "Cir_Avg_sample.tif.csv", index=False
    )
    with (tmp_path / "whitespace.dat").open("w") as handle:
        handle.write("# sample B\n# measured at 13.5 keV\n")
        for x, y in zip(Q, INTENSITY * 2):
            handle.write(f"{x:.8g}   {y:.8g}\n")
    with (tmp_path / "commented_header.txt").open("w") as handle:
        handle.write("# q  I  sigma\n")
        for x, y in zip(Q, INTENSITY * 3):
            handle.write(f"{x:.8g} {y:.8g} 1.0\n")
    with (tmp_path / "fit2d.chi").open("w") as handle:
        handle.write("fit2d.chi\nq (A-1)\nIntensity\n     40\n")
        for x, y in zip(Q, INTENSITY * 4):
            handle.write(f"  {x:.6e}  {y:.6e}\n")
    pd.DataFrame({"q": Q, "I": INTENSITY * 5}).to_csv(
        tmp_path / "tabbed.txt", sep="\t", index=False
    )
    pd.DataFrame({"q": Q, "I": INTENSITY * 6}).to_csv(
        tmp_path / "semicolon.csv", sep=";", index=False
    )
    np.savez(tmp_path / "bundle.npz", q=Q, iq=INTENSITY * 7, qimg=np.ones((4, 5)))
    np.save(tmp_path / "single.npy", np.arange(12).reshape(3, 4))
    Image.fromarray(np.arange(24, dtype=np.uint8).reshape(4, 6)).save(tmp_path / "det.png")
    return tmp_path


def test_guess_kind_classifies_by_extension():
    assert guess_kind("a.csv") == "curve"
    assert guess_kind("a.NPZ") == "array"
    assert guess_kind("a.tiff") == "image"
    assert guess_kind("a.h5") == "other"


def test_read_curve_uses_the_reduction_column_names(files):
    curve = read_curve(files / "Cir_Avg_sample.tif.csv")
    assert (curve["x_name"], curve["y_name"]) == ("q_ca", "iq_ca")
    assert curve["x"].size == 40
    assert np.isclose(curve["y"][0], INTENSITY[0])


def test_read_curve_handles_a_free_text_comment_block(files):
    curve = read_curve(files / "whitespace.dat")
    # "# sample B" is prose, not a header, so the columns stay positional.
    assert curve["columns"] == ["column_0", "column_1"]
    assert np.isclose(curve["y"][0], 2 * INTENSITY[0])


def test_read_curve_accepts_a_commented_column_header(files):
    curve = read_curve(files / "commented_header.txt")
    assert curve["columns"] == ["q", "I", "sigma"]
    assert (curve["x_name"], curve["y_name"]) == ("q", "I")


def test_read_curve_reads_a_fit2d_chi_header_block(files):
    curve = read_curve(files / "fit2d.chi")
    assert curve["x"].size == 40
    assert np.isclose(curve["y"][0], 4 * INTENSITY[0])


def test_read_curve_detects_tab_and_semicolon_delimiters(files):
    tabbed = read_curve(files / "tabbed.txt")
    semicolon = read_curve(files / "semicolon.csv")
    assert tabbed["columns"] == ["q", "I"]
    assert semicolon["columns"] == ["q", "I"]
    assert np.isclose(semicolon["y"][0], 6 * INTENSITY[0])


def test_read_curve_reads_one_dimensional_arrays_from_an_npz(files):
    curve = read_curve(files / "bundle.npz")
    assert (curve["x_name"], curve["y_name"]) == ("q", "iq")
    assert "qimg" in curve["columns"] or curve["columns"] == ["q", "iq"]


def test_read_curve_honours_explicit_column_choices(files):
    curve = read_curve(files / "commented_header.txt", x_column="q", y_column="sigma")
    assert curve["y_name"] == "sigma"
    assert np.allclose(curve["y"], 1.0)


def test_read_curve_sorts_by_x_and_drops_non_finite_points(tmp_path):
    path = tmp_path / "messy.csv"
    path.write_text("q,I\n0.3,3\n0.1,1\nnan,9\n0.2,\n")
    curve = read_curve(path)
    assert curve["x"].tolist() == [0.1, 0.3]
    assert curve["y"].tolist() == [1.0, 3.0]


def test_read_curve_reports_a_file_it_cannot_use(tmp_path):
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    with pytest.raises(DataReadError):
        read_curve(empty)

    prose = tmp_path / "prose.txt"
    prose.write_text("this file has no numbers at all\n")
    with pytest.raises(DataReadError):
        read_curve(prose)


def test_read_curve_rejects_a_single_column_file(tmp_path):
    single = tmp_path / "one.csv"
    single.write_text("I\n1\n2\n3\n")
    with pytest.raises(DataReadError):
        read_curve(single)


def test_read_table_returns_only_numeric_columns(files):
    table = read_table(files / "commented_header.txt")
    assert list(table.columns) == ["q", "I", "sigma"]
    assert table.shape[0] == 40


def test_read_arrays_and_read_image(files):
    bundle = read_arrays(files / "bundle.npz")
    assert sorted(bundle) == ["iq", "q", "qimg"]
    single = read_arrays(files / "single.npy")
    assert single["single"].shape == (3, 4)
    image = read_image(files / "det.png")
    assert image.shape == (4, 6)


def test_read_image_rejects_a_non_image(tmp_path):
    path = tmp_path / "not_an_image.png"
    path.write_text("hello")
    with pytest.raises(DataReadError):
        read_image(path)


def test_curve_columns_lists_choices_for_both_kinds(files):
    assert curve_columns(files / "commented_header.txt") == ["q", "I", "sigma"]
    assert curve_columns(files / "bundle.npz") == ["q", "iq"]


def test_common_prefix_suffix_and_short_label():
    names = ["Cir_Avg_KimA_th0.10.tif", "Cir_Avg_KimB_th0.10.tif"]
    prefix, suffix = common_prefix_suffix(names)
    assert prefix == "Cir_Avg_Kim"
    assert suffix == "_th0.10.tif"
    assert short_label(names[0], prefix, suffix) == "A"


def test_common_prefix_suffix_never_erases_a_name():
    assert common_prefix_suffix(["sample", "sample_extra"]) == ("", "")
    assert common_prefix_suffix(["only_one"]) == ("", "")


def test_short_label_shortens_a_very_long_name():
    label = short_label("x" * 200, max_length=20)
    assert len(label) == 20 and "…" in label


def test_stack_curves_interpolates_onto_one_grid(files):
    curves = [
        read_curve(files / "Cir_Avg_sample.tif.csv"),
        read_curve(files / "tabbed.txt"),
    ]
    grid, labels, matrix = stack_curves(curves, points=25, log_x=True)
    assert grid.shape == (25,)
    assert matrix.shape == (2, 25)
    assert labels == ["Cir_Avg_sample.tif", "tabbed"]
    assert np.isfinite(matrix).all()


def test_stack_curves_leaves_out_of_range_points_as_nan(tmp_path):
    short = tmp_path / "short.csv"
    short.write_text("q,I\n0.1,1\n0.2,2\n")
    long = tmp_path / "long.csv"
    long.write_text("q,I\n0.1,1\n0.5,5\n")
    grid, _labels, matrix = stack_curves(
        [read_curve(short), read_curve(long)], points=11
    )
    assert np.isnan(matrix[0, -1])
    assert not np.isnan(matrix[1, -1])


def test_stack_curves_needs_a_usable_range(tmp_path):
    with pytest.raises(DataReadError):
        stack_curves([])
