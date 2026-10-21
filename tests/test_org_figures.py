"""The Org pages' figures: limits left blank frame the data, limits typed are
kept, and the intensity follows the window shown."""

from __future__ import annotations

import numpy as np

from pyscattviz.app.components.org import figures


def test_blank_sides_are_filled_and_typed_ones_kept():
    assert figures.filled((None, None), (1.0, 2.0)) == (1.0, 2.0)
    assert figures.filled((None, 5.0), (1.0, 2.0)) == (1.0, 5.0)
    assert figures.filled((3.0, None), None) is None
    assert figures.filled((3.0, 1.0), None) is None  # min above max: auto
    assert figures.span([np.nan, -1.0, 0.0, 4.0], positive=True) == (4.0, 4.0)


def test_a_remeshed_map_is_framed_on_its_data_and_scaled_in_the_window():
    x, y = np.linspace(-2, 2, 41), np.linspace(-1, 3, 41)
    z = np.full((41, 41), np.nan)
    z[10:30, 20:41] = 1.0  # the detector covers x 0…2, y 0…1.9
    z[10:30, 30:41] = 100.0  # a bright half, x 1…2
    xr, yr, vmin, vmax = figures.image_limits(z, x, y)
    assert xr == (0.0, 2.0) and yr == (0.0, 1.9000000000000004)
    assert vmax == 100.0
    # Narrowed to the dim half, the colour scale is the dim half's.
    xr, _, vmin, vmax = figures.image_limits(z, x, y, x_range=(None, 0.9))
    assert xr == (0.0, 0.9) and vmin == vmax == 1.0
    # Typed limits are not touched.
    assert figures.image_limits(z, x, y, (-1.0, 1.0), (0.5, 1.0), 2.0, 50.0) == (
        (-1.0, 1.0),
        (0.5, 1.0),
        2.0,
        50.0,
    )


def test_intensity_follows_the_q_window():
    q = np.linspace(0.01, 1.0, 100)
    iq = q**-3
    full_x, full_y = figures.curve_limits([(q, iq)], logy=True)
    assert full_x == (0.01, 1.0) and full_y[1] > 1e6
    _, window_y = figures.curve_limits([(q, iq)], (0.5, None), logy=True)
    assert 0.9 < window_y[0] < 1.0 and 8.0 < window_y[1] < 10.0
    _, typed = figures.curve_limits([(q, iq)], (0.5, None), (1.0, 2.0), logy=True)
    assert typed == (1.0, 2.0)


def test_figures_take_their_limits():
    q = np.linspace(0.01, 1.0, 100)
    figure = figures.curves_figure([("a", q, q**-2)], logx=False, x_range=(0.2, 0.4))
    assert tuple(figure.layout.xaxis.range) == (0.2, 0.4)
    assert figure.layout.yaxis.range[1] < np.log10(30.0)  # I at q = 0.2 is 25, not 10⁴
    z = np.outer(np.ones(20), np.arange(1, 31, dtype=float))
    figure = figures.image_figure(
        z, np.arange(30.0), np.arange(20.0), "x", "y", y_range=(5.0, 9.0), vmin=2.0, vmax=8.0
    )
    assert tuple(figure.layout.yaxis.range) == (5.0, 9.0)
    assert figure.data[0].zmin == np.log10(2.0) and figure.data[0].zmax == np.log10(8.0)
    waterfall = figures.waterfall_figure(
        q, [3.0, 1.0, 2.0], np.vstack([q**-2] * 3), "t", y_range=(1.5, None)
    )
    assert tuple(waterfall.layout.yaxis.range) == (1.5, 3.0)
