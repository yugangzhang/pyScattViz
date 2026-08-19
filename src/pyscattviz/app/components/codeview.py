"""Hand the code behind a figure to the user.

Clicking is fast for looking; a script is what you keep. Every plotting page
offers the Python behind the figure on screen, so the next step — a different
normalization, a fit, an inset, a panel the GUI does not offer — starts from
working code rather than a blank cell.

The code can be read, downloaded, saved beside the figures, or opened straight
in the Python Console with the session's data already loaded.
"""

from __future__ import annotations

import streamlit as st

from pyscattviz.app.components.saving import render_save_panel
from pyscattviz.app.state import action_key

__all__ = ["render_code_export"]

CONSOLE_PAGE = "pages/13_Python_Console.py"
HANDOFF_KEY = "pyscattviz_console_handoff"


def render_code_export(
    code: str,
    *,
    key: str,
    tab_name: str,
    filename: str = "pyscattviz_figure",
    label: str = "🐍 Python for this figure",
    expanded: bool = False,
) -> None:
    """Show the generated script with ways to keep or continue it."""

    if not code.strip():
        return

    with st.expander(label, expanded=expanded):
        st.caption(
            "Everything here uses the public API, so it runs in a notebook, from a "
            "terminal, or in the Python Console."
        )
        st.code(code, language="python")

        actions = st.columns([1.2, 1.4, 2])
        actions[0].download_button(
            "Download .py",
            code,
            file_name=f"{filename}.py",
            mime="text/x-python",
            key=action_key(st.session_state, f"{key}_download"),
            use_container_width=True,
        )
        if actions[1].button(
            "Open in Python Console",
            key=action_key(st.session_state, f"{key}_send"),
            use_container_width=True,
        ):
            st.session_state[HANDOFF_KEY] = code
            try:
                st.switch_page(CONSOLE_PAGE)
            except Exception:  # pragma: no cover - older Streamlit, or no page context
                st.success(
                    "Loaded. Open **Python Console** in the sidebar and the code will "
                    "be waiting in the editor."
                )
        actions[2].caption("The console starts with `basket`, `folder`, and the readers loaded.")

        render_save_panel(
            tab_name,
            filename,
            key=f"{key}_save",
            text=code,
            caption="Saved as a .txt beside the figures; rename it to .py to run it.",
        )
