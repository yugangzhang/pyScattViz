from pathlib import Path

from pyscattviz.app.components.scattering import (
    discover_scattering_products,
    index_frames,
)


def _make_products(root: Path, stems: list[str]) -> None:
    for folder in ("q_image", "qphi", "cir_avg", "qc"):
        (root / folder).mkdir(parents=True)
    for stem in stems:
        (root / "q_image" / f"qimg_{stem}.tif.npz").touch()
        (root / "qphi" / f"qphi_{stem}.tif.npz").touch()
        (root / "cir_avg" / f"Cir_Avg_{stem}.tif.csv").touch()
        (root / "qc" / f"qc_{stem}.png").touch()


def test_discovery_counts_direct_products(tmp_path):
    root = tmp_path / "gisaxs"
    _make_products(root, ["sample_a", "sample_b"])

    normalized, products, focused = discover_scattering_products(str(root))

    assert Path(normalized) == root.resolve()
    assert focused is None
    assert {item["key"]: item["count"] for item in products} == {
        "qc": 2,
        "q_image": 2,
        "qphi": 2,
        "cir_avg": 2,
    }


def test_index_filters_names_pairs_products_and_never_opens_arrays(tmp_path):
    root = tmp_path / "giwaxs"
    stems = ["sampleA_0.1000deg", "sampleA_0.1500deg", "AgBH_0.1000deg"]
    _make_products(root, stems)

    table = index_frames(
        str(root),
        product_keys=("q_image", "qphi", "cir_avg", "qc"),
        query="sampleA AND (0.1000deg OR 0.1500deg) NOT AgBH",
        max_frames=100,
    )

    assert table["stem"].tolist() == ["sampleA_0.1000deg", "sampleA_0.1500deg"]
    assert table[["has_qimg", "has_qphi", "has_cir", "has_qc"]].all().all()
    assert table.attrs["scanned_entries"] > 0
    assert not table.attrs["truncated"]


def test_exact_filename_list_and_frame_cap(tmp_path):
    root = tmp_path / "gisaxs"
    _make_products(root, ["sample_a", "sample_b", "sample_c"])

    exact = index_frames(
        str(root),
        product_keys=("q_image", "cir_avg"),
        filename_list=("Cir_Avg_sample_b.tif.csv",),
    )
    assert exact["stem"].tolist() == ["sample_b"]

    capped = index_frames(str(root), product_keys=("q_image",), max_frames=2)
    assert len(capped) == 2
    assert capped.attrs["truncated"]
