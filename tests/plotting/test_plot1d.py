"""Tests for pyscattviz.plotting.plot1d — 1D plotting."""

import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def test_plot1d_basic():
    from pyscattviz.plotting.plot1d import plot1d

    ax = plot1d([1, 2, 3, 4])
    assert ax is not None
    plt.close("all")


def test_plot1d_with_x():
    from pyscattviz.plotting.plot1d import plot1d

    x = np.linspace(0, 10, 50)
    y = np.sin(x)
    ax = plot1d(y, x=x, title="Sine")
    assert ax.get_title() == "Sine"
    plt.close("all")


def test_plot1d_log():
    from pyscattviz.plotting.plot1d import plot1d

    x = np.logspace(-3, 0, 100)
    y = 1e4 * x**-2
    ax = plot1d(y, x=x, logxy=True)
    assert ax.get_xscale() == "log"
    assert ax.get_yscale() == "log"
    plt.close("all")


def test_plot1d_errorbar():
    from pyscattviz.plotting.plot1d import plot1d

    x = np.arange(10)
    y = np.random.rand(10)
    yerr = np.ones(10) * 0.1
    ax = plot1d(y, x=x, yerr=yerr)
    assert ax is not None
    plt.close("all")


def test_plot1d_styling():
    from pyscattviz.plotting.plot1d import plot1d

    ax = plot1d([1, 2, 3], marker="o", color="red", ls="--", lw=2, alpha=0.7)
    assert ax is not None
    plt.close("all")


def test_plot1d_series():
    from pyscattviz.plotting.plot1d import plot1d

    s = pd.Series([10, 20, 30], name="intensity")
    ax = plot1d(s)
    assert ax is not None
    plt.close("all")


def test_plot1d_dataframe():
    from pyscattviz.plotting.plot1d import plot1d

    df = pd.DataFrame({"q": [0.1, 0.2, 0.3], "I": [100, 200, 300]})
    ax = plot1d(data=df, x="q", y="I")
    assert ax is not None
    plt.close("all")


def test_plot1d_interactive():
    from pyscattviz.plotting.plot1d import plot1d

    x = np.linspace(0, 5, 50)
    fig = plot1d(np.sin(x), x=x, interactive=True, title="Interactive")
    assert hasattr(fig, "update_layout")  # plotly Figure


def test_plot1d_save():
    from pyscattviz.plotting.plot1d import plot1d

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test_1d.png"
        plot1d([1, 2, 3], save=str(path))
        assert path.exists()
    plt.close("all")


def test_plot1d_with_fit():
    from pyscattviz.plotting.plot1d import plot1d_with_fit

    x = np.linspace(0, 5, 20)
    y = np.exp(-x) + np.random.normal(0, 0.05, 20)
    xf = np.linspace(0, 5, 100)
    yf = np.exp(-xf)
    ax = plot1d_with_fit(x, y, xf, yf, ylabel="Signal")
    assert ax is not None
    plt.close("all")


def test_plot1d_with_fit_interactive():
    from pyscattviz.plotting.plot1d import plot1d_with_fit

    x = np.linspace(0, 5, 20)
    y = np.exp(-x)
    fig = plot1d_with_fit(x, y, x, y, interactive=True)
    assert hasattr(fig, "update_layout")


def test_plot1d_with_fit_txts():
    from pyscattviz.plotting.plot1d import plot1d_with_fit

    x = np.linspace(0, 5, 20)
    y = np.exp(-x)
    ax = plot1d_with_fit(x, y, x, y, txts="tau = 1.0\nA = 1.0")
    assert ax is not None
    plt.close("all")


def test_plot1d_multi_dicts():
    from pyscattviz.plotting.plot1d import plot1d_multi

    x = np.linspace(0, 10, 50)
    datasets = [
        {"x": x, "y": np.sin(x), "label": "sin"},
        {"x": x, "y": np.cos(x), "label": "cos"},
    ]
    ax = plot1d_multi(datasets, title="Trig")
    assert ax is not None
    plt.close("all")


def test_plot1d_multi_tuples():
    from pyscattviz.plotting.plot1d import plot1d_multi

    x = np.linspace(0, 10, 50)
    datasets = [
        (x, np.sin(x), "sin"),
        (x, np.cos(x), "cos"),
    ]
    ax = plot1d_multi(datasets)
    assert ax is not None
    plt.close("all")


def test_plot1d_multi_interactive():
    from pyscattviz.plotting.plot1d import plot1d_multi

    x = np.linspace(0, 10, 50)
    datasets = [
        {"x": x, "y": np.sin(x), "label": "sin"},
        {"x": x, "y": np.cos(x), "label": "cos"},
    ]
    fig = plot1d_multi(datasets, interactive=True)
    assert hasattr(fig, "update_layout")


def test_plot1d_on_existing_ax():
    from pyscattviz.plotting.plot1d import plot1d

    fig, ax = plt.subplots()
    ret = plot1d([1, 2, 3], ax=ax, color="blue")
    assert ret is ax
    ret2 = plot1d([3, 2, 1], ax=ax, color="red")
    assert ret2 is ax
    plt.close(fig)
