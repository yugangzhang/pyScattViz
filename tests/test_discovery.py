import pytest

from pyscattviz.discovery import (
    classify_folder,
    describe_paths,
    filter_names,
    find_files,
    find_folders,
    ls_dir,
    matches_terms,
    parse_terms,
)


def test_parse_terms_splits_commas_semicolons_and_lines():
    assert parse_terms("Kim, 0.10deg;  giwaxs\nAgBH") == (
        "Kim",
        "0.10deg",
        "giwaxs",
        "AgBH",
    )


def test_parse_terms_strips_quotes_comments_and_duplicates():
    assert parse_terms('"sample one", # note\n sample one , other') == (
        "sample one",
        "other",
    )


def test_parse_terms_accepts_none_and_iterables():
    assert parse_terms(None) == ()
    assert parse_terms(["a, b", "c"]) == ("a", "b", "c")


def test_matches_terms_applies_and_or_exclude():
    assert matches_terms("Kim_giwaxs_0.10deg", and_list=["kim", "giwaxs"])
    assert not matches_terms("Kim_gisaxs", and_list=["kim", "giwaxs"])
    assert matches_terms("Kim_gisaxs", or_list=["giwaxs", "gisaxs"])
    assert not matches_terms("Kim_maxs", or_list=["giwaxs", "gisaxs"])
    assert not matches_terms("Kim_AgBH", no_list=["agbh"])


def test_matches_terms_with_no_conditions_is_true():
    assert matches_terms("anything")


def test_matches_terms_supports_wildcards_and_case_sensitivity():
    assert matches_terms("Kim_sample_WAXS", and_list=["Kim_*_WAXS"])
    assert not matches_terms("Kim_sample_SAXS", and_list=["Kim_*_WAXS"])
    assert not matches_terms("kim_sample", and_list=["Kim"], case_sensitive=True)


def test_filter_names_matches_the_pyscatt_ls_dir_semantics():
    names = ["a_Kim_giwaxs", "b_Kim_gisaxs", "c_Lee_giwaxs", "d_Kim_AgBH"]
    assert filter_names(names, and_list=["Kim"], no_list=["AgBH"]) == [
        "a_Kim_giwaxs",
        "b_Kim_gisaxs",
    ]
    assert filter_names(names, or_list=["gisaxs", "AgBH"]) == [
        "b_Kim_gisaxs",
        "d_Kim_AgBH",
    ]


@pytest.fixture
def proposal(tmp_path):
    giwaxs = tmp_path / "projects" / "microbeam_Kim" / "Results" / "giwaxs"
    (giwaxs / "cir_avg").mkdir(parents=True)
    (giwaxs / "q_image").mkdir()
    (giwaxs / "cir_avg" / "Cir_Avg_Kim_th0.1000deg.tif.csv").write_text("q,I\n1,2\n")
    (giwaxs / "cir_avg" / "Cir_Avg_AgBH.tif.csv").write_text("q,I\n1,2\n")
    (giwaxs / "q_image" / "qimg_Kim_th0.1000deg.tif.npz").touch()

    gisaxs = tmp_path / "projects" / "microbeam_Kim" / "Results" / "gisaxs"
    (gisaxs / "cir_avg").mkdir(parents=True)
    (gisaxs / "cir_avg" / "Cir_Avg_Kim_B.tif.csv").write_text("q,I\n1,2\n")

    other = tmp_path / "projects" / "other_Lee" / "Results" / "giwaxs"
    other.mkdir(parents=True)
    (tmp_path / ".hidden_cache").mkdir()
    return tmp_path


def test_ls_dir_filters_direct_entries(proposal):
    folder = proposal / "projects" / "microbeam_Kim" / "Results" / "giwaxs" / "cir_avg"
    assert ls_dir(folder, and_list=["Kim"]) == ["Cir_Avg_Kim_th0.1000deg.tif.csv"]
    assert ls_dir(folder, no_list=["AgBH"]) == ["Cir_Avg_Kim_th0.1000deg.tif.csv"]
    assert len(ls_dir(folder)) == 2


def test_ls_dir_can_restrict_to_folders_and_return_full_paths(proposal):
    root = proposal / "projects" / "microbeam_Kim" / "Results" / "giwaxs"
    names = ls_dir(root, kind="folder")
    assert names == ["cir_avg", "q_image"]
    full = ls_dir(root, kind="folder", full_path=True)
    assert all(item.startswith(str(root)) for item in full)


def test_ls_dir_rejects_an_unknown_kind(proposal):
    with pytest.raises(ValueError):
        ls_dir(proposal, kind="everything")


def test_find_folders_matches_on_the_whole_path(proposal):
    rows, truncated = find_folders(
        proposal,
        and_list=["Results"],
        or_list=["giwaxs", "gisaxs"],
        no_list=["other"],
        match_on="path",
        max_depth=6,
    )
    assert not truncated
    # ``.../Results/giwaxs/cir_avg`` also contains both terms, but the parent is
    # what the user meant, so the product folders collapse into it.
    names = sorted(row["name"] for row in rows)
    assert names == ["gisaxs", "giwaxs"]
    assert all("microbeam_Kim" in row["path"] for row in rows)


def test_product_folders_can_be_kept_alongside_their_parent(proposal):
    rows, _truncated = find_folders(
        proposal,
        and_list=["Results"],
        or_list=["giwaxs", "gisaxs"],
        no_list=["other"],
        match_on="path",
        max_depth=6,
        collapse_product_folders=False,
    )
    assert sorted(row["name"] for row in rows) == [
        "cir_avg",
        "cir_avg",
        "gisaxs",
        "giwaxs",
        "q_image",
    ]


def test_a_product_folder_survives_when_its_parent_did_not_match(proposal):
    """Searching for cir_avg alone must still return the product folders."""

    rows, _truncated = find_folders(proposal, and_list=["cir_avg"], match_on="name", max_depth=6)
    assert sorted(row["name"] for row in rows) == ["cir_avg", "cir_avg"]


def test_find_folders_matching_on_name_returns_only_the_result_folders(proposal):
    rows, _truncated = find_folders(
        proposal, or_list=["giwaxs", "gisaxs"], match_on="name", max_depth=6
    )
    assert sorted(row["name"] for row in rows) == ["gisaxs", "giwaxs", "giwaxs"]


def test_find_folders_reports_products_and_can_require_them(proposal):
    rows, _truncated = find_folders(proposal, and_list=["giwaxs"], match_on="name", max_depth=6)
    giwaxs = next(row for row in rows if "microbeam" in row["path"])
    assert giwaxs["products"] == "cir_avg, q_image"

    only_products, _ = find_folders(
        proposal, and_list=["giwaxs"], match_on="name", max_depth=6, products_only=True
    )
    assert [row["path"] for row in only_products] == [giwaxs["path"]]


def test_find_folders_skips_hidden_folders_and_missing_roots(proposal):
    rows, _truncated = find_folders([proposal, proposal / "does_not_exist"], max_depth=2)
    assert not any(row["name"].startswith(".") for row in rows)


def test_find_folders_truncates_and_reports_it(proposal):
    rows, truncated = find_folders(proposal, max_depth=6, max_results=2)
    assert len(rows) == 2
    assert truncated


def test_find_folders_validates_its_arguments(proposal):
    with pytest.raises(ValueError):
        find_folders(proposal, match_on="contents")
    with pytest.raises(ValueError):
        find_folders(proposal, max_depth=0)


def test_find_files_filters_by_extension_and_terms(proposal):
    rows, truncated = find_files(
        proposal, and_list=["Kim"], no_list=["AgBH"], extensions=[".csv"], max_depth=8
    )
    assert not truncated
    assert sorted(row["name"] for row in rows) == [
        "Cir_Avg_Kim_B.tif.csv",
        "Cir_Avg_Kim_th0.1000deg.tif.csv",
    ]


def test_find_files_accepts_extensions_without_a_leading_dot(proposal):
    rows, _truncated = find_files(proposal, extensions=["npz"], max_depth=8)
    assert [row["suffix"] for row in rows] == [".npz"]


def test_find_files_default_extensions_cover_every_readable_kind(proposal):
    rows, _truncated = find_files(proposal, max_depth=8)
    assert len(rows) == 4


def test_classify_folder_describes_products_and_availability(proposal):
    giwaxs = proposal / "projects" / "microbeam_Kim" / "Results" / "giwaxs"
    summary = classify_folder(giwaxs)
    assert summary["products"] == ("cir_avg", "q_image")
    assert summary["is_product_folder"] is False
    assert summary["available"] is True

    product = classify_folder(giwaxs / "cir_avg")
    assert product["is_product_folder"] is True
    assert product["data_files"] == 2

    missing = classify_folder(proposal / "nowhere")
    assert missing["available"] is False


def test_describe_paths_reports_kind_for_each_entry(proposal):
    giwaxs = proposal / "projects" / "microbeam_Kim" / "Results" / "giwaxs"
    described = describe_paths(
        [str(giwaxs), str(giwaxs / "cir_avg" / "Cir_Avg_AgBH.tif.csv"), "/no/such/path", ""]
    )
    assert [item["kind"] for item in described] == ["folder", "file", "missing"]
    assert described[0]["products"] == "cir_avg, q_image"


def test_find_folders_can_skip_the_product_report(proposal):
    """The report costs one directory listing per match; it must be optional."""

    described, _ = find_folders(proposal, and_list=["giwaxs"], match_on="name", max_depth=6)
    plain, _ = find_folders(
        proposal,
        and_list=["giwaxs"],
        match_on="name",
        max_depth=6,
        describe_products=False,
    )
    assert [row["path"] for row in plain] == [row["path"] for row in described]
    assert all(row["products"] == "—" and row["data_files"] is None for row in plain)
    assert any(row["products"] != "—" for row in described)


def test_products_only_still_works_without_the_report(proposal):
    rows, _ = find_folders(
        proposal,
        match_on="name",
        max_depth=6,
        products_only=True,
        describe_products=False,
    )
    assert sorted(row["name"] for row in rows) == ["gisaxs", "giwaxs"]
