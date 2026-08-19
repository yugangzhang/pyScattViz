import pytest

from pyscattviz.filters import FilterSyntaxError, compile_filter, parse_filename_list


@pytest.mark.parametrize(
    ("expression", "name", "expected"),
    [
        ("", "anything", True),
        ("sampleA 0.1000deg", "sampleA_run_0.1000deg", True),
        ("sampleA AND (0.1000deg OR 0.1500deg)", "sampleA_run_0.1500deg", True),
        ("sampleA AND (0.1000deg OR 0.1500deg)", "sampleA_run_0.2000deg", False),
        ("sampleA NOT AgBH", "sampleA_run", True),
        ("sampleA NOT AgBH", "sampleA_AgBH", False),
        ('"sample one" OR sample_two', "prefix_sample one_data", True),
        ("sampleA_*_WAXS", "sampleA_7_WAXS", True),
    ],
)
def test_boolean_filename_filter(expression, name, expected):
    assert compile_filter(expression)(name) is expected


@pytest.mark.parametrize("expression", ["sampleA AND", "(sampleA OR SAXS", "sampleA OR ) SAXS"])
def test_filter_reports_invalid_expressions(expression):
    with pytest.raises(FilterSyntaxError):
        compile_filter(expression)


def test_filename_list_accepts_lines_commas_comments_and_quotes():
    assert parse_filename_list('one.tif\n# note\n"two.tif", one.tif') == [
        "one.tif",
        "two.tif",
    ]
