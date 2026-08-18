"""
Figure save and export utilities.

Provides simple functions to save matplotlib figures to files, byte buffers,
or base64 strings.

Examples
--------
>>> import matplotlib.pyplot as plt
>>> from pyscattviz.plotting.io import save_fig, fig_to_bytes
>>> fig, ax = plt.subplots()
>>> ax.plot([1, 2, 3])
>>> save_fig(fig, 'plot.png')
>>> png_bytes = fig_to_bytes(fig)
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from matplotlib.figure import Figure

__all__ = [
    "save_fig",
    "fig_to_bytes",
    "fig_to_base64",
]


def save_fig(
    fig: Figure,
    path: str | Path,
    dpi: int = 300,
    format: str | None = None,
    tight: bool = True,
):
    """Save a matplotlib figure to a file.

    Auto-detects format from the file extension unless *format* is given.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure to save.
    path : str or Path
        Output file path (e.g. ``'plot.png'``, ``'fig.svg'``, ``'out.pdf'``).
    dpi : int
        Resolution in dots per inch (ignored for vector formats).
    format : str, optional
        Explicit format override (``'png'``, ``'svg'``, ``'pdf'``).
    tight : bool
        If *True*, use ``bbox_inches='tight'`` to remove excess whitespace.

    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> from pyscattviz.plotting.io import save_fig
    >>> fig, ax = plt.subplots()
    >>> ax.plot([0, 1, 2], [0, 1, 4])
    >>> save_fig(fig, 'quadratic.png')
    >>> save_fig(fig, 'quadratic.svg', dpi=150)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    bbox = "tight" if tight else None
    fig.savefig(path, dpi=dpi, format=format, bbox_inches=bbox)


def fig_to_bytes(
    fig: Figure,
    format: str = "png",
    dpi: int = 300,
) -> bytes:
    """Serialize a matplotlib figure to a bytes buffer.

    Useful for Streamlit download buttons, HTTP responses, etc.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure to serialize.
    format : str
        Image format (``'png'``, ``'svg'``, ``'pdf'``).
    dpi : int
        Resolution in dots per inch.

    Returns
    -------
    data : bytes
        Raw image bytes.

    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> from pyscattviz.plotting.io import fig_to_bytes
    >>> fig, ax = plt.subplots()
    >>> ax.plot([1, 2, 3])
    >>> data = fig_to_bytes(fig)
    >>> len(data) > 0
    True
    """
    buf = io.BytesIO()
    fig.savefig(buf, format=format, dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    return buf.read()


def fig_to_base64(
    fig: Figure,
    format: str = "png",
    dpi: int = 300,
) -> str:
    """Serialize a matplotlib figure to a base64 string.

    Useful for embedding in HTML or Markdown.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure to serialize.
    format : str
        Image format (``'png'``, ``'svg'``).
    dpi : int
        Resolution in dots per inch.

    Returns
    -------
    b64 : str
        Base64-encoded string of the image.

    Examples
    --------
    >>> import matplotlib.pyplot as plt
    >>> from pyscattviz.plotting.io import fig_to_base64
    >>> fig, ax = plt.subplots()
    >>> ax.plot([1, 2, 3])
    >>> b64 = fig_to_base64(fig)
    >>> b64[:10]
    'iVBORw0KGg'
    """
    raw = fig_to_bytes(fig, format=format, dpi=dpi)
    return base64.b64encode(raw).decode("ascii")
