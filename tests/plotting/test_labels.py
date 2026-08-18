"""Tests for pyscattviz.plotting.labels — label sanitization."""

import matplotlib.pyplot as plt


def test_sanitize_q_unit():
    from pyscattviz.plotting.labels import sanitize_label

    result = sanitize_label("q (//A)")
    assert r"\AA^{-1}" in result
    assert "$" in result


def test_sanitize_none():
    from pyscattviz.plotting.labels import sanitize_label

    assert sanitize_label(None) is None


def test_sanitize_plain_string():
    from pyscattviz.plotting.labels import sanitize_label

    assert sanitize_label("Intensity") == "Intensity"


def test_sanitize_odd_dollars():
    from pyscattviz.plotting.labels import sanitize_label

    result = sanitize_label("$bad")
    assert "$" not in result or r"\$" in result


def test_enable_disable_auto_sanitize():
    from pyscattviz.plotting.labels import disable_auto_sanitize, enable_auto_sanitize

    enable_auto_sanitize()
    fig, ax = plt.subplots()
    ax.set_xlabel("q (//A)")  # should not crash
    plt.close(fig)

    disable_auto_sanitize()
    fig, ax = plt.subplots()
    ax.set_xlabel("normal label")
    plt.close(fig)
