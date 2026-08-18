"""Tests for pyscattviz.plotting.plotnd — N-D visualization."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _make_df():
    rng = np.random.default_rng(42)
    df = pd.DataFrame(rng.standard_normal((80, 4)), columns=list("ABCD"))
    df["group"] = rng.choice(["x", "y"], 80)
    return df


def test_pairplot():
    from pyscattviz.plotting.plotnd import pairplot

    fig = pairplot(_make_df(), hue="group")
    assert fig is not None
    plt.close("all")


def test_pairplot_vars():
    from pyscattviz.plotting.plotnd import pairplot

    fig = pairplot(_make_df(), vars=["A", "B"], corner=True)
    assert fig is not None
    plt.close("all")


def test_pairplot_interactive():
    from pyscattviz.plotting.plotnd import pairplot

    fig = pairplot(_make_df(), hue="group", interactive=True)
    assert hasattr(fig, "update_layout")


def test_multi_hue_pairplot():
    from pyscattviz.plotting.plotnd import multi_hue_pairplot

    df = _make_df()
    df["val"] = np.random.rand(80)
    fig = multi_hue_pairplot(
        df,
        x_vars=["A", "B"],
        y_vars=["C"],
        hues=["group", "val"],
        figsize=(8, 6),
        s=30,
    )
    assert fig is not None
    plt.close("all")


def test_parallel_coords():
    from pyscattviz.plotting.plotnd import parallel_coords

    ax = parallel_coords(_make_df(), class_column="group", cols=["A", "B", "C"])
    assert ax is not None
    plt.close("all")


def test_parallel_coords_interactive():
    from pyscattviz.plotting.plotnd import parallel_coords

    fig = parallel_coords(_make_df(), class_column="group", interactive=True)
    assert hasattr(fig, "update_layout")


def test_correlation_matrix():
    from pyscattviz.plotting.plotnd import correlation_matrix

    ax = correlation_matrix(_make_df(), title="Corr")
    assert ax is not None
    plt.close("all")


def test_correlation_matrix_mask():
    from pyscattviz.plotting.plotnd import correlation_matrix

    ax = correlation_matrix(_make_df(), mask_upper=True)
    assert ax is not None
    plt.close("all")


def test_correlation_matrix_interactive():
    from pyscattviz.plotting.plotnd import correlation_matrix

    fig = correlation_matrix(_make_df(), interactive=True)
    assert hasattr(fig, "update_layout")
