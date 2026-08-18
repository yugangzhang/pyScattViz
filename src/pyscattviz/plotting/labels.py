"""
Matplotlib label sanitization utilities.

Converts common scientific notation (e.g. ``"q (//A)"``) into
matplotlib-safe strings with proper LaTeX rendering.  Optionally
monkey-patches matplotlib axes to auto-sanitize all labels.

Adapted from pyScatt ``core/plot_text.py`` by Y.G.@CFN.

Examples
--------
>>> from pyscattviz.plotting.labels import sanitize_label
>>> sanitize_label("q (//A)")
'$q\\\\,(\\\\AA^{-1})$'

>>> from pyscattviz.plotting.labels import enable_auto_sanitize
>>> enable_auto_sanitize()  # all future set_xlabel/ylabel/title auto-clean
"""

from __future__ import annotations

import re

import matplotlib as mpl
from matplotlib.axes import Axes
from matplotlib.mathtext import MathTextParser

__all__ = [
    "sanitize_label",
    "enable_auto_sanitize",
    "disable_auto_sanitize",
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_Q_UNIT_RE = re.compile(
    r"(?P<sym>[Qq](?:_[A-Za-z0-9]+)?)\s*[\(\[]\s*"
    r"(?://\s*A|/\s*A|1\s*/\s*A|A\s*\^?\s*-?1|AA\s*\^?\s*-?1)"
    r"\s*[\)\]]"
)
_MATH_PARSER = MathTextParser("path")
_PATCHED = False


def _normalize_q_unit(label: str) -> str:
    """Replace common Q-unit notations with proper LaTeX."""

    def _replace(match):
        sym = match.group("sym")
        if "_" in sym:
            base, sub = sym.split("_", 1)
            sym_math = f"{base}_{{{sub}}}"
        else:
            sym_math = sym
        return rf"${sym_math}\,(\AA^{{-1}})$"

    text = _Q_UNIT_RE.sub(_replace, label)
    if text.strip() in {"//A", "/A", "1/A", "A-1", "A^-1", "AA-1", "AA^-1"}:
        return r"$\AA^{-1}$"
    return text


def _fix_math_delimiters(label: str) -> str:
    """Fix broken ``$`` delimiters to avoid mathtext crashes."""
    text = label
    while "$$" in text:
        text = text.replace("$$", "$")
    if text.count("$") % 2:
        text = text.replace("$", r"\$")
    return text


def _mathtext_ok(label: str) -> bool:
    """Check whether *label* is valid for matplotlib mathtext."""
    if "$" not in label:
        return True
    try:
        _MATH_PARSER.parse(label, dpi=72)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sanitize_label(label: str | None) -> str | None:
    """Convert common scientific notation into matplotlib-safe strings.

    Handles Q-unit labels, broken math delimiters, and invalid mathtext.

    Parameters
    ----------
    label : str or None
        The raw label string.  Returns *None* unchanged.

    Returns
    -------
    safe_label : str or None
        Sanitized label suitable for ``ax.set_xlabel()`` etc.

    Examples
    --------
    >>> from pyscattviz.plotting.labels import sanitize_label
    >>> sanitize_label("q (//A)")
    '$q\\\\,(\\\\AA^{-1})$'

    >>> sanitize_label("$bad")     # odd number of $ signs
    '\\\\$bad'

    >>> sanitize_label(None)
    """
    if label is None or not isinstance(label, str):
        return label

    text = _normalize_q_unit(label.strip())
    text = _fix_math_delimiters(text)

    if _mathtext_ok(text):
        return text

    # Fallback to plain text
    plain = text.replace("$", "")
    plain = plain.replace(r"\AA^{-1}", "A^-1").replace(r"\AA", "A")
    plain = plain.replace(r"\,", " ")
    return plain


def enable_auto_sanitize():
    """Monkey-patch matplotlib axes to auto-sanitize labels.

    After calling this, every ``ax.set_xlabel()``, ``ax.set_ylabel()``,
    and ``ax.set_title()`` call will automatically pass through
    :func:`sanitize_label`.

    Also disables external TeX rendering and sets ``DejaVuSans`` for
    robustness in notebook environments.

    Examples
    --------
    >>> from pyscattviz.plotting.labels import enable_auto_sanitize, disable_auto_sanitize
    >>> enable_auto_sanitize()
    >>> # ... all labels are now auto-sanitized ...
    >>> disable_auto_sanitize()
    """
    global _PATCHED

    mpl.rcParams["text.usetex"] = False
    mpl.rcParams["mathtext.fontset"] = "dejavusans"
    mpl.rcParams["axes.unicode_minus"] = False

    if _PATCHED:
        return

    # Store originals
    if not hasattr(Axes, "_pv_orig_set_xlabel"):
        Axes._pv_orig_set_xlabel = Axes.set_xlabel
        Axes._pv_orig_set_ylabel = Axes.set_ylabel
        Axes._pv_orig_set_title = Axes.set_title

    def _wrap(original):
        def _wrapped(self, value, *args, **kwargs):
            return original(self, sanitize_label(value), *args, **kwargs)

        return _wrapped

    Axes.set_xlabel = _wrap(Axes._pv_orig_set_xlabel)
    Axes.set_ylabel = _wrap(Axes._pv_orig_set_ylabel)
    Axes.set_title = _wrap(Axes._pv_orig_set_title)
    _PATCHED = True


def disable_auto_sanitize():
    """Undo the monkey patches created by :func:`enable_auto_sanitize`.

    Examples
    --------
    >>> from pyscattviz.plotting.labels import enable_auto_sanitize, disable_auto_sanitize
    >>> enable_auto_sanitize()
    >>> disable_auto_sanitize()  # back to normal
    """
    global _PATCHED
    if not _PATCHED:
        return
    if hasattr(Axes, "_pv_orig_set_xlabel"):
        Axes.set_xlabel = Axes._pv_orig_set_xlabel
        Axes.set_ylabel = Axes._pv_orig_set_ylabel
        Axes.set_title = Axes._pv_orig_set_title
    _PATCHED = False
