"""Tests for pyscattviz.plotting.io — save and export."""

import tempfile
from pathlib import Path

import matplotlib.pyplot as plt


def _make_fig():
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [0, 1, 4])
    return fig


def test_save_fig_png():
    from pyscattviz.plotting.io import save_fig

    fig = _make_fig()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.png"
        save_fig(fig, path)
        assert path.exists()
        assert path.stat().st_size > 0
    plt.close(fig)


def test_save_fig_svg():
    from pyscattviz.plotting.io import save_fig

    fig = _make_fig()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.svg"
        save_fig(fig, path)
        assert path.exists()
    plt.close(fig)


def test_fig_to_bytes():
    from pyscattviz.plotting.io import fig_to_bytes

    fig = _make_fig()
    data = fig_to_bytes(fig)
    assert isinstance(data, bytes)
    assert len(data) > 100
    plt.close(fig)


def test_fig_to_base64():
    from pyscattviz.plotting.io import fig_to_base64

    fig = _make_fig()
    b64 = fig_to_base64(fig)
    assert isinstance(b64, str)
    assert len(b64) > 100
    plt.close(fig)
