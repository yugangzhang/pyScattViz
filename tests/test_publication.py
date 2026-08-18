import matplotlib.pyplot as plt
import numpy as np
import pytest

from pyscattviz.plotting import fig_to_bytes
from pyscattviz.publication import Curve, build_curve_figure, compact_label, prepare_curve


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
