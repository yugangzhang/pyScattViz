"""Tests for pyscattviz.plotting.plot2d — 2D images and heatmaps."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def _make_image():
    return np.random.exponential(10, (50, 50))


def test_imshow_basic():
    from pyscattviz.plotting.plot2d import imshow

    ax = imshow(_make_image())
    assert ax is not None
    plt.close("all")


def test_imshow_log():
    from pyscattviz.plotting.plot2d import imshow

    ax = imshow(_make_image(), log=True, colorbar=True)
    assert ax is not None
    plt.close("all")


def test_imshow_zlim():
    from pyscattviz.plotting.plot2d import imshow

    ax = imshow(_make_image(), zlim=(0.01, 0.99), colorbar=True)
    assert ax is not None
    plt.close("all")


def test_imshow_custom_cmap():
    from pyscattviz.plotting.plot2d import imshow

    ax = imshow(_make_image(), cmap="pv_vge_hdr")
    assert ax is not None
    plt.close("all")


def test_imshow_labels():
    from pyscattviz.plotting.plot2d import imshow

    ax = imshow(
        _make_image(),
        title="Test Image",
        xlabel="X pixels",
        ylabel="Y pixels",
    )
    assert ax.get_title() == "Test Image"
    plt.close("all")


def test_imshow_no_ticks():
    from pyscattviz.plotting.plot2d import imshow

    ax = imshow(_make_image(), show_ticks=False)
    assert ax is not None
    plt.close("all")


def test_imshow_interactive():
    from pyscattviz.plotting.plot2d import imshow

    fig = imshow(_make_image(), interactive=True, title="Interactive")
    assert hasattr(fig, "update_layout")


def test_imshow_interactive_honors_log_percentile_range():
    from pyscattviz.plotting.plot2d import imshow

    image = np.arange(1, 101, dtype=float).reshape(10, 10)
    fig = imshow(image, interactive=True, log=True, zlim=(0.1, 0.9))
    assert fig.layout.coloraxis.cmin is not None
    assert fig.layout.coloraxis.cmax is not None


def test_imshow_z_linear():
    from pyscattviz.plotting.plot2d import imshow_z

    ax = imshow_z(_make_image(), z_mode="linear", colorbar=True)
    assert ax is not None
    plt.close("all")


def test_imshow_z_gamma():
    from pyscattviz.plotting.plot2d import imshow_z

    ax = imshow_z(_make_image(), z_mode="gamma", z_adj=0.3)
    assert ax is not None
    plt.close("all")


def test_imshow_z_log():
    from pyscattviz.plotting.plot2d import imshow_z

    ax = imshow_z(_make_image(), z_mode="log")
    assert ax is not None
    plt.close("all")


def test_imshow_z_with_coords():
    from pyscattviz.plotting.plot2d import imshow_z

    img = _make_image()
    x = np.linspace(0, 1, img.shape[1] + 1)
    y = np.linspace(0, 1, img.shape[0] + 1)
    ax = imshow_z(img, x=x, y=y, z_mode="gamma", z_adj=0.5)
    assert ax is not None
    plt.close("all")


def test_imshow_z_interactive():
    from pyscattviz.plotting.plot2d import imshow_z

    fig = imshow_z(_make_image(), z_mode="gamma", interactive=True)
    assert hasattr(fig, "update_layout")


def test_heatmap_array():
    from pyscattviz.plotting.plot2d import heatmap

    data = np.random.rand(10, 15)
    ax = heatmap(data, title="Test Heatmap")
    assert ax is not None
    plt.close("all")


def test_heatmap_with_coords():
    from pyscattviz.plotting.plot2d import heatmap

    data = np.random.rand(10, 15)
    x = np.linspace(0, 1, 16)
    y = np.linspace(0, 2, 11)
    ax = heatmap(data, x=x, y=y, cmap="plasma")
    assert ax is not None
    plt.close("all")


def test_heatmap_dataframe():
    from pyscattviz.plotting.plot2d import heatmap

    df = pd.DataFrame(np.random.rand(5, 5), columns=list("ABCDE"))
    ax = heatmap(df, annot=True, fmt=".2f")
    assert ax is not None
    plt.close("all")


def test_heatmap_interactive():
    from pyscattviz.plotting.plot2d import heatmap

    fig = heatmap(np.random.rand(10, 10), interactive=True)
    assert hasattr(fig, "update_layout")


def test_heatmap_interactive_uses_coordinate_edges_as_centers():
    from pyscattviz.plotting.plot2d import heatmap

    data = np.arange(6).reshape(2, 3)
    fig = heatmap(data, x=np.arange(4), y=np.arange(3), interactive=True)
    assert list(fig.data[0].x) == [0.5, 1.5, 2.5]
    assert list(fig.data[0].y) == [0.5, 1.5]


def test_imshow_on_existing_ax():
    from pyscattviz.plotting.plot2d import imshow

    fig, ax = plt.subplots()
    ret = imshow(_make_image(), ax=ax)
    assert ret is ax
    plt.close(fig)
