"""Run a snippet of the user's own Python, notebook-style.

The GUI covers the plots I could anticipate. This covers the rest: paste the
code a page generated, change the normalization, add a fit, build a panel nobody
thought of. The namespace arrives with the session's data already in it, so the
first line can be about the science.

Like a notebook cell, a trailing expression is echoed:

    >>> result = run_snippet("curves = [read_curve(p) for p in basket]\\nlen(curves)", ns)
    >>> result.value
    3

**On safety.** This runs the code you type, in this process, with your
permissions — exactly like typing it at a Python prompt. That is the point of
the feature, and it is why :func:`is_local_only` exists: pyScattViz listens on
127.0.0.1 by default, and the page refuses to run anything when the server has
been bound to an address other people can reach.
"""

from __future__ import annotations

import ast
import contextlib
import io
import traceback
from dataclasses import dataclass, field
from ipaddress import ip_address

__all__ = ["ConsoleResult", "STARTER_SNIPPETS", "is_local_only", "run_snippet"]


@dataclass
class ConsoleResult:
    """What one snippet produced."""

    stdout: str = ""
    value: object = None
    has_value: bool = False
    error: str = ""
    names: dict = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return bool(self.error)


def is_local_only(address: str | None) -> bool:
    """True when ``address`` can only be reached from this computer.

    An unset address is treated as local because that is what the launcher
    passes by default; anything routable is not.
    """

    text = (address or "").strip()
    if not text or text in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ip_address(text).is_loopback
    except ValueError:
        return False


def _user_traceback(exc: BaseException) -> str:
    """Format a traceback showing the user's own lines, not this module's.

    The frame for the ``exec`` call inside :func:`run_snippet` is noise to
    somebody debugging their own snippet, so drop the frames that belong to this
    file and keep everything from ``<pyscattviz>`` down.
    """

    frames = traceback.extract_tb(exc.__traceback__)
    interesting = [frame for frame in frames if frame.filename != __file__]
    lines = ["Traceback (most recent call last):\n"]
    lines.extend(traceback.format_list(interesting or frames))
    lines.extend(traceback.format_exception_only(type(exc), exc))
    return "".join(lines)


def run_snippet(code: str, namespace: dict) -> ConsoleResult:
    """Execute ``code`` in ``namespace`` and report what came out.

    The namespace is modified in place, so names defined in one snippet are
    available to the next, as in a notebook. A trailing expression is evaluated
    separately and returned as ``value``.
    """

    result = ConsoleResult()
    if not code.strip():
        result.error = "Nothing to run."
        return result

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        result.error = "".join(traceback.format_exception_only(type(exc), exc))
        return result

    tail = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        tail = tree.body.pop()

    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            if tree.body:
                exec(compile(ast.Module(tree.body, []), "<pyscattviz>", "exec"), namespace)
            if tail is not None:
                value = eval(  # noqa: S307 - running the user's own code is the feature
                    compile(ast.Expression(tail.value), "<pyscattviz>", "eval"), namespace
                )
                if value is not None:
                    result.value = value
                    result.has_value = True
    except BaseException as exc:  # noqa: BLE001 - report anything the snippet raises
        result.error = _user_traceback(exc)
    result.stdout = stdout.getvalue()
    result.names = namespace
    return result


STARTER_SNIPPETS = {
    "Overlay the current list": """# `basket` holds whatever the Terminal or Data Selection put there.
curves = [read_curve(path) for path in basket[:8]]

fig, ax = plt.subplots(figsize=(7, 5))
for curve in curves:
    ax.loglog(curve["x"], curve["y"], lw=1.4, label=curve["label"][:40])
ax.set_xlabel(r"q ($\\AA^{-1}$)")
ax.set_ylabel("I(q)")
ax.legend(fontsize=7)
fig
""",
    "Fit a power law": """# Slope of I(q) over a q window — the first thing I check on a new sample.
curve = read_curve(basket[0])
q, intensity = curve["x"], curve["y"]

window = (q > 0.01) & (q < 0.05) & (intensity > 0)
slope, intercept = np.polyfit(np.log10(q[window]), np.log10(intensity[window]), 1)
print(f"I(q) ~ q^{slope:.2f} over 0.01-0.05 A^-1")

fig, ax = plt.subplots()
ax.loglog(q, intensity, lw=1.2, label=curve["label"][:40])
ax.loglog(q[window], 10 ** (intercept + slope * np.log10(q[window])), "r--",
          label=f"slope {slope:.2f}")
ax.legend()
fig
""",
    "List a folder": """# ls_dir is the same helper the Terminal and Data Selection use.
names = ls_dir(folder, and_list=["Cir_Avg"], no_list=["AgBH"])
print(len(names), "curves")
names[:10]
""",
    "Write a figure to disk": """folder_out = resolve_output_dir(output_root, "Python Console", create=True)

curve = read_curve(basket[0])
fig, ax = plt.subplots()
ax.loglog(curve["x"], curve["y"])
ax.set_xlabel(r"q ($\\AA^{-1}$)")
ax.set_ylabel("I(q)")

path = save_matplotlib_figure(fig, folder_out, "console_figure", fmt="png", dpi=300)
print("wrote", path)
fig
""",
}
