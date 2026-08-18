"""Tests for pyscattviz.plotting.utils — helpers."""

import numpy as np


def test_find_nearest():
    from pyscattviz.plotting.utils import find_nearest

    arr = np.array([1.0, 3.0, 7.0, 10.0])
    idx, val = find_nearest(arr, 6.5)
    assert idx == 2
    assert val == 7.0


def test_find_nearest_exact():
    from pyscattviz.plotting.utils import find_nearest

    arr = np.array([0.01, 0.02, 0.05])
    idx, val = find_nearest(arr, 0.02)
    assert idx == 1
    assert val == 0.02


def test_create_meshgrid_scattered():
    from pyscattviz.plotting.utils import create_meshgrid

    rng = np.random.default_rng(42)
    x = rng.uniform(-5, 5, 200)
    y = rng.uniform(-5, 5, 200)
    z = np.sin(np.sqrt(x**2 + y**2))

    X, Y, Z = create_meshgrid(x, y, z, n_grid=30)
    assert X.shape == (30, 30)
    assert Y.shape == (30, 30)
    assert Z.shape == (30, 30)


def test_create_meshgrid_gridded():
    from pyscattviz.plotting.utils import create_meshgrid

    x_1d = np.array([1.0, 2.0, 3.0])
    y_1d = np.array([10.0, 20.0])
    xx, yy = np.meshgrid(x_1d, y_1d)
    z = (xx + yy).ravel()
    x = xx.ravel()
    y = yy.ravel()

    X, Y, Z = create_meshgrid(x, y, z)
    assert X.shape == (2, 3)
    assert Z.shape == (2, 3)
