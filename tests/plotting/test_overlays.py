"""Tests for pyscattviz.plotting.overlays — annotations and overlays."""

import matplotlib.pyplot as plt
import numpy as np


def test_overlay_mask():
    from pyscattviz.plotting.overlays import overlay_mask

    fig, ax = plt.subplots()
    mask = np.zeros((50, 50), dtype=int)
    mask[10:30, 10:30] = 1
    mask[35:45, 35:45] = 2
    im = overlay_mask(ax, mask)
    assert im is not None
    plt.close(fig)


def test_overlay_mask_on_image():
    from pyscattviz.plotting.overlays import overlay_mask_on_image

    fig, ax = plt.subplots()
    img = np.random.exponential(10, (50, 50))
    mask = np.zeros((50, 50), dtype=int)
    mask[10:30, 10:30] = 1
    im, im_label = overlay_mask_on_image(ax, img, mask)
    assert im is not None
    assert im_label is not None
    plt.close(fig)


def test_overlay_mask_on_image_linear():
    from pyscattviz.plotting.overlays import overlay_mask_on_image

    fig, ax = plt.subplots()
    img = np.random.rand(50, 50) * 100
    mask = np.zeros((50, 50), dtype=int)
    mask[20:40, 20:40] = 1
    im, im_label = overlay_mask_on_image(ax, img, mask, log_img=False)
    assert im is not None
    plt.close(fig)


def test_add_vlines():
    from pyscattviz.plotting.overlays import add_vlines

    fig, ax = plt.subplots()
    ax.plot([0, 10], [0, 10])
    add_vlines(ax, [3, 5, 7], color="blue")
    plt.close(fig)


def test_add_hlines():
    from pyscattviz.plotting.overlays import add_hlines

    fig, ax = plt.subplots()
    ax.plot([0, 10], [0, 10])
    add_hlines(ax, [2, 4, 8], color="green", ls=":")
    plt.close(fig)


def test_add_patches():
    from pyscattviz.plotting.overlays import add_patches

    fig, ax = plt.subplots()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    add_patches(ax, [(0, 0, 3, 10), (3, 0, 4, 10), (7, 0, 3, 10)])
    assert len(ax.patches) == 3
    plt.close(fig)


def test_add_region_patches():
    from pyscattviz.plotting.overlays import add_region_patches

    fig, ax = plt.subplots()
    ax.plot(range(30), range(30))
    add_region_patches(ax, [10, 20], (0, 30))
    assert len(ax.patches) >= 3
    plt.close(fig)


def test_add_text_box():
    from pyscattviz.plotting.overlays import add_text_box

    fig, ax = plt.subplots()
    ax.plot([1, 2, 3])
    add_text_box(ax, "peak = 2.5\nFWHM = 0.3")
    plt.close(fig)


def test_add_text_box_locations():
    from pyscattviz.plotting.overlays import add_text_box

    fig, ax = plt.subplots()
    ax.plot([1, 2, 3])
    for loc in ["upper right", "upper left", "lower right", "lower left", "center"]:
        add_text_box(ax, f"at {loc}", loc=loc, fontsize=8)
    plt.close(fig)
