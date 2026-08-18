from pathlib import Path

import pytest

from pyscattviz.globus import default_cache, proposal_path


def test_proposal_path_supports_cms_and_smi():
    assert proposal_path("CMS", "2026-2", "123456") == (
        "/nsls2/data/cms/proposals/2026-2/pass-123456"
    )
    assert proposal_path("smi", "2026-2", "pass-123456") == (
        "/nsls2/data/smi/proposals/2026-2/pass-123456"
    )


@pytest.mark.parametrize(
    "beamline,cycle,proposal",
    [("XPD", "2026-2", "123456"), ("CMS", "26-2", "123456"), ("SMI", "2026-2", "123")],
)
def test_proposal_path_rejects_invalid_values(beamline, cycle, proposal):
    with pytest.raises(ValueError):
        proposal_path(beamline, cycle, proposal)


def test_default_cache_is_under_home():
    assert default_cache("123456") == Path.home() / "pyScattViz-data" / "pass-123456"
