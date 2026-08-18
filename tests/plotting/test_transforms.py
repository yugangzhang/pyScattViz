"""Tests for pyscattviz.plotting.transforms — z-transforms, percentile ranges."""

import numpy as np
import pytest


def test_z_range_basic():
    from pyscattviz.plotting.transforms import z_range

    data = np.arange(100, dtype=float)
    vmin, vmax = z_range(data)
    assert vmin >= 0
    assert vmax <= 99
    assert vmin < vmax


def test_z_range_override():
    from pyscattviz.plotting.transforms import z_range

    data = np.arange(100, dtype=float)
    vmin, vmax = z_range(data, zmin=10.0, zmax=90.0)
    assert vmin == 10.0
    assert vmax == 90.0


def test_z_transform_linear():
    from pyscattviz.plotting.transforms import z_transform

    data = np.array([[0, 50], [50, 100]], dtype=float)
    Z = z_transform(data, mode="linear", vmin=0, vmax=100)
    assert Z.shape == (2, 2)
    np.testing.assert_allclose(Z[0, 0], 0.0)
    np.testing.assert_allclose(Z[1, 1], 1.0)


def test_z_transform_log():
    from pyscattviz.plotting.transforms import z_transform

    data = np.array([[1, 10], [100, 1000]], dtype=float)
    Z = z_transform(data, mode="log", vmin=1, vmax=1000)
    assert Z.min() >= 0.0
    assert Z.max() <= 1.0


def test_z_transform_gamma():
    from pyscattviz.plotting.transforms import z_transform

    data = np.linspace(0, 100, 50).reshape(5, 10)
    Z = z_transform(data, mode="gamma", adj=0.3, vmin=0, vmax=100)
    assert Z.shape == (5, 10)
    assert Z.min() >= 0.0
    assert Z.max() <= 1.0


def test_z_transform_radial():
    from pyscattviz.plotting.transforms import radial_map, z_transform

    data = np.ones((50, 50))
    R = radial_map((50, 50))
    Z = z_transform(data, mode="radial", adj=1.0, vmin=0, vmax=50, r_map=R)
    assert Z.shape == (50, 50)


def test_z_transform_radial_requires_r_map():
    from pyscattviz.plotting.transforms import z_transform

    with pytest.raises(ValueError, match="r_map"):
        z_transform(np.ones((10, 10)), mode="radial")


def test_radial_map_shape():
    from pyscattviz.plotting.transforms import radial_map

    R = radial_map((100, 200))
    assert R.shape == (100, 200)


def test_radial_map_center():
    from pyscattviz.plotting.transforms import radial_map

    R = radial_map((100, 100), center=(50, 50))
    assert R[50, 50] == 0.0
