"""Tests for pyscattviz.plotting.plot3d — 3D visualization."""

import matplotlib.pyplot as plt
import numpy as np


def _grid():
    from pyscattviz.plotting.plot3d import make_demo_data

    return make_demo_data("ripple", n=20)


def test_surface():
    from pyscattviz.plotting.plot3d import surface

    X, Y, Z = _grid()
    ax = surface(X, Y, Z, title="Surface")
    assert ax is not None
    plt.close("all")


def test_surface_interactive():
    from pyscattviz.plotting.plot3d import surface

    X, Y, Z = _grid()
    fig = surface(X, Y, Z, interactive=True, title="Surface")
    assert hasattr(fig, "update_layout")


def test_wireframe():
    from pyscattviz.plotting.plot3d import wireframe

    X, Y, Z = _grid()
    ax = wireframe(X, Y, Z, title="Wire")
    assert ax is not None
    plt.close("all")


def test_wireframe_interactive():
    from pyscattviz.plotting.plot3d import wireframe

    X, Y, Z = _grid()
    fig = wireframe(X, Y, Z, interactive=True)
    assert hasattr(fig, "update_layout")


def test_scatter3d():
    from pyscattviz.plotting.plot3d import scatter3d

    rng = np.random.default_rng(42)
    x, y, z = rng.normal(size=(3, 50))
    ax = scatter3d(x, y, z, c=z, cmap="coolwarm")
    assert ax is not None
    plt.close("all")


def test_scatter3d_interactive():
    from pyscattviz.plotting.plot3d import scatter3d

    rng = np.random.default_rng(42)
    x, y, z = rng.normal(size=(3, 50))
    fig = scatter3d(x, y, z, interactive=True)
    assert hasattr(fig, "update_layout")


def test_contour():
    from pyscattviz.plotting.plot3d import contour

    X, Y, Z = _grid()
    ax = contour(X, Y, Z, levels=10, title="Contour")
    assert ax is not None
    plt.close("all")


def test_contour_interactive():
    from pyscattviz.plotting.plot3d import contour

    X, Y, Z = _grid()
    fig = contour(X, Y, Z, interactive=True)
    assert hasattr(fig, "update_layout")


def test_surface_contour():
    from pyscattviz.plotting.plot3d import surface_contour

    X, Y, Z = _grid()
    ax = surface_contour(X, Y, Z, cmap="turbo")
    assert ax is not None
    plt.close("all")


def test_make_demo_data_all():
    from pyscattviz.plotting.plot3d import make_demo_data

    for kind in ("gaussian", "ripple", "saddle", "volcano"):
        X, Y, Z = make_demo_data(kind, n=30)
        assert X.shape == (30, 30)
        assert Z.shape == (30, 30)


def test_make_demo_data_invalid():
    import pytest

    from pyscattviz.plotting.plot3d import make_demo_data

    with pytest.raises(ValueError, match="Unknown kind"):
        make_demo_data("invalid")


def test_surface_scattered_data():
    from pyscattviz.plotting.plot3d import surface

    rng = np.random.default_rng(42)
    x = rng.uniform(-5, 5, 200)
    y = rng.uniform(-5, 5, 200)
    z = np.sin(np.sqrt(x**2 + y**2))
    ax = surface(x, y, z, title="Scattered->Gridded")
    assert ax is not None
    plt.close("all")
