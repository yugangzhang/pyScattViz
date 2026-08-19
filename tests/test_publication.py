import matplotlib.pyplot as plt
import numpy as np
import pytest

from pyscattviz.plotting import fig_to_bytes
from pyscattviz.publication import (
    Curve,
    CurveStyle,
    build_curve_figure,
    compact_label,
    prepare_curve,
)

Q = np.logspace(-2, 0, 60)


def test_compact_label_preserves_both_filename_ends():
    label = compact_label("sample_with_a_very_long_detector_filename_000001_SAXS2M", 24)
    assert len(label) == 24
    assert label.startswith("sample_with_")
    assert label.endswith("001_SAXS2M")


def test_prepare_curve_filters_range_and_normalizes_maximum():
    curve = Curve("sample", np.array([0.01, 0.1, 1.0, np.nan]), np.array([2, 4, 8, 3]))
    result = prepare_curve(curve, q_min=0.1, q_max=1.0, normalization="maximum")
    np.testing.assert_allclose(result.q, [0.1, 1.0])
    np.testing.assert_allclose(result.intensity, [0.5, 1.0])


def test_build_curve_figure_exports_png_and_honors_legend_toggle():
    q = np.logspace(-3, 0, 20)
    curves = [Curve("one", q, q**-1), Curve("two", q, 2 * q**-1)]
    figure = build_curve_figure(curves, legend=False, theme="science")
    assert figure.axes[0].get_xscale() == "log"
    assert figure.axes[0].get_yscale() == "log"
    assert figure.axes[0].legend_ is None
    assert len(fig_to_bytes(figure, format="png")) > 100
    plt.close(figure)


def test_build_curve_figure_rejects_empty_or_nonpositive_log_data():
    with pytest.raises(ValueError, match="at least one"):
        build_curve_figure([])
    with pytest.raises(ValueError, match="no positive points"):
        build_curve_figure([Curve("bad", np.array([1.0]), np.array([-1.0]))])


# ---------------------------------------------------------------------------
# Full matplotlib control over the figure
# ---------------------------------------------------------------------------
def test_per_curve_style_reaches_matplotlib():
    curves = [Curve("a", Q, Q**-2), Curve("b", Q, Q**-2.5)]
    styles = [
        CurveStyle(
            color="crimson",
            linestyle="--",
            linewidth=3.0,
            marker="o",
            markersize=7.0,
            markevery=5,
            alpha=0.7,
            label="sample A",
        ),
        CurveStyle(color="#1f77b4", linestyle=":", marker="s"),
    ]
    figure = build_curve_figure(curves, styles=styles)
    first, second = figure.axes[0].lines

    assert first.get_color() == "crimson"
    assert first.get_linestyle() == "--"
    assert first.get_linewidth() == 3.0
    assert first.get_marker() == "o"
    assert first.get_markersize() == 7.0
    assert first.get_alpha() == 0.7
    assert first.get_label() == "sample A"
    assert second.get_color() == "#1f77b4"
    plt.close(figure)


def test_axis_limits_ticks_and_frame_are_controllable():
    figure = build_curve_figure(
        [Curve("a", Q, Q**-2)],
        xlim=(0.02, 0.8),
        ylim=(1.0, 1e4),
        grid=True,
        minor_grid=True,
        tick_direction="out",
        tick_length=6.0,
        spine_width=2.0,
        font_size=12.0,
    )
    axis = figure.axes[0]

    assert axis.get_xlim() == pytest.approx((0.02, 0.8))
    assert axis.get_ylim() == pytest.approx((1.0, 1e4))
    assert axis.spines["left"].get_linewidth() == 2.0
    plt.close(figure)


def test_the_legend_is_placed_and_sized_as_asked():
    figure = build_curve_figure(
        [Curve("a", Q, Q**-2), Curve("b", Q, Q**-2.5)],
        legend_location="upper right",
        legend_columns=2,
        legend_font_size=7.0,
        legend_frame=False,
    )
    legend = figure.axes[0].get_legend()

    assert legend is not None
    assert legend._ncols == 2
    assert legend.get_frame_on() is False
    plt.close(figure)


def test_a_multiplier_stacks_the_curves():
    """A factor of 2 gives 1, 2, 4, 8 … which is how a waterfall is built."""

    curves = [Curve(name, Q, Q**-2) for name in ("a", "b", "c")]
    figure = build_curve_figure(curves, multiplier=2.0)
    lines = figure.axes[0].lines

    assert lines[1].get_ydata()[0] == pytest.approx(2 * lines[0].get_ydata()[0])
    assert lines[2].get_ydata()[0] == pytest.approx(4 * lines[0].get_ydata()[0])
    plt.close(figure)


def test_a_grid_that_is_off_stays_off():
    """matplotlib turns the grid back on if alpha is passed with grid(False)."""

    figure = build_curve_figure([Curve("a", Q, Q**-2)], grid=False, grid_alpha=0.3)
    assert not figure.axes[0].xaxis.get_gridlines()[0].get_visible()
    plt.close(figure)


def test_curves_without_styles_still_draw():
    figure = build_curve_figure([Curve("a", Q, Q**-2), Curve("b", Q, Q**-3)])
    assert len(figure.axes[0].lines) == 2
    plt.close(figure)
