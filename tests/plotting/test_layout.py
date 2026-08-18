"""Tests for pyscattviz.plotting.layout — figure/axes creation."""

import matplotlib.pyplot as plt


def test_create_axes_1x1():
    from pyscattviz.plotting.layout import create_axes

    fig, axes = create_axes()
    assert len(axes) == 1
    plt.close(fig)


def test_create_axes_2x3():
    from pyscattviz.plotting.layout import create_axes

    fig, axes = create_axes(2, 3)
    assert len(axes) == 6
    plt.close(fig)


def test_create_axes_with_title():
    from pyscattviz.plotting.layout import create_axes

    fig, axes = create_axes(title="Test Figure")
    assert fig._suptitle is not None
    plt.close(fig)


def test_create_axes_ratio_vertical():
    from pyscattviz.plotting.layout import create_axes_ratio

    fig, ax_main, ax_minor = create_axes_ratio(ratio=4)
    assert ax_main is not None
    assert ax_minor is not None
    plt.close(fig)


def test_create_axes_ratio_horizontal():
    from pyscattviz.plotting.layout import create_axes_ratio

    fig, ax_main, ax_minor = create_axes_ratio(ratio=3, orientation="horizontal")
    assert ax_main is not None
    assert ax_minor is not None
    plt.close(fig)


def test_create_axes_mosaic_list():
    from pyscattviz.plotting.layout import create_axes_mosaic

    layout = [["A", "A", "B"], ["C", "D", "B"]]
    fig, axes = create_axes_mosaic(layout)
    assert set(axes.keys()) == {"A", "B", "C", "D"}
    plt.close(fig)


def test_create_axes_mosaic_string():
    from pyscattviz.plotting.layout import create_axes_mosaic

    fig, axes = create_axes_mosaic("AB\nCC")
    assert "A" in axes
    assert "B" in axes
    assert "C" in axes
    plt.close(fig)


def test_create_axes_inset():
    from pyscattviz.plotting.layout import create_axes, create_axes_inset

    fig, axes = create_axes()
    ax_in = create_axes_inset(axes[0])
    assert ax_in is not None
    ax_in.plot([1, 2, 3])
    plt.close(fig)
