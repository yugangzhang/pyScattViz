import pytest

from pyscattviz.filters import FilterSyntaxError, compile_filter, parse_filename_list


@pytest.mark.parametrize(
    ("expression", "name", "expected"),
    [
        ("", "anything", True),
        ("Kim 0.1000deg", "Kim_sample_0.1000deg", True),
        ("Kim AND (0.1000deg OR 0.1500deg)", "Kim_sample_0.1500deg", True),
        ("Kim AND (0.1000deg OR 0.1500deg)", "Kim_sample_0.2000deg", False),
        ("Kim NOT AgBH", "Kim_sample", True),
        ("Kim NOT AgBH", "Kim_AgBH", False),
        ('"sample one" OR sample_two', "prefix_sample one_data", True),
        ("Kim_*_WAXS", "Kim_7_WAXS", True),
    ],
)
def test_boolean_filename_filter(expression, name, expected):
    assert compile_filter(expression)(name) is expected


@pytest.mark.parametrize("expression", ["Kim AND", "(Kim OR SAXS", "Kim OR ) SAXS"])
def test_filter_reports_invalid_expressions(expression):
    with pytest.raises(FilterSyntaxError):
        compile_filter(expression)


def test_filename_list_accepts_lines_commas_comments_and_quotes():
    assert parse_filename_list('one.tif\n# note\n"two.tif", one.tif') == [
        "one.tif",
        "two.tif",
    ]
