"""Tests for pyscattviz.plotting.style — colormaps, palettes, themes."""

import matplotlib as mpl
import matplotlib.pyplot as plt
import pytest


def test_cmaps_registered():
    """All custom colormaps are available via matplotlib."""
    from pyscattviz.plotting.style import list_cmaps

    names = list_cmaps()
    assert len(names) > 0
    for name in names:
        cmap = mpl.colormaps[name]
        assert cmap is not None


def test_list_cmaps_includes_reversed():
    from pyscattviz.plotting.style import list_cmaps

    names = list_cmaps()
    assert "pv_vge" in names
    assert "pv_vge_r" in names


def test_cmap_objects():
    from pyscattviz.plotting.style import CMAP_ALBULA, CMAP_VGE, CMAP_VGE_HDR

    for cmap in (CMAP_VGE, CMAP_VGE_HDR, CMAP_ALBULA):
        rgba = cmap(0.5)
        assert len(rgba) == 4


def test_show_cmaps():
    from pyscattviz.plotting.style import show_cmaps

    fig = show_cmaps(figsize=(6, 3))
    assert fig is not None
    plt.close(fig)


def test_colors_10():
    from pyscattviz.plotting.style import COLORS_10

    assert len(COLORS_10) == 10
    assert all(c.startswith("#") for c in COLORS_10)


def test_markers():
    from pyscattviz.plotting.style import MARKERS

    assert len(MARKERS) >= 20


def test_set_theme_science():
    from pyscattviz.plotting.style import set_theme

    set_theme("science")
    assert mpl.rcParams["font.family"] == ["serif"]


def test_set_theme_invalid():
    from pyscattviz.plotting.style import set_theme

    with pytest.raises(ValueError, match="Unknown style"):
        set_theme("nonexistent")


def test_theme_context():
    from pyscattviz.plotting.style import set_theme, theme_context

    set_theme("science")
    old_size = mpl.rcParams["font.size"]

    with theme_context("poster"):
        assert mpl.rcParams["font.size"] == 18

    assert mpl.rcParams["font.size"] == old_size


def test_get_color_cycle():
    from pyscattviz.plotting.style import get_color_cycle

    colors = get_color_cycle(5)
    assert len(colors) == 5
    colors_20 = get_color_cycle(20)
    assert len(colors_20) == 20


def test_get_marker_cycle():
    from pyscattviz.plotting.style import get_marker_cycle

    markers = get_marker_cycle(5)
    assert len(markers) == 5
    assert markers[0] == "o"
