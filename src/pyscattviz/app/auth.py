"""An optional password in front of every page.

On a laptop nothing else can reach the server, so there is nothing to protect
and no password is asked for. On a shared beamline workstation anybody logged
in to the same machine can open ``localhost:<port>``, and with ``--address
0.0.0.0`` anybody on the network can, so the launcher can set a password:

    ./run 5649 secret            # or: pyscattviz --port 5649 --password secret

The launcher hands it to Streamlit through ``PYSCATTVIZ_PASSWORD`` rather than
on the command line, so it never appears in ``ps`` for the server process.
When the variable is unset or empty, :func:`require_password` does nothing.
"""

from __future__ import annotations

import hmac
import os

PASSWORD_ENV = "PYSCATTVIZ_PASSWORD"
AUTH_KEY = "pyscattviz_authenticated"


def configured_password() -> str:
    """The password this server was started with, or ``""`` for none."""

    return os.environ.get(PASSWORD_ENV, "")


def password_matches(attempt: str, password: str) -> bool:
    """Compare in constant time, so the answer's timing gives nothing away."""

    return hmac.compare_digest(str(attempt).encode("utf-8"), str(password).encode("utf-8"))


def require_password() -> None:
    """Stop the page here until this browser session has given the password.

    Call it straight after ``keep_widget_state`` on every page. The flag lives
    in session state, so one sign-in covers every page until the browser tab is
    reloaded.
    """

    password = configured_password()
    if not password:
        return

    import streamlit as st

    from pyscattviz.app.state import action_key

    if st.session_state.get(AUTH_KEY):
        return

    st.title("🔒 pyScattViz")
    # Registered as action keys so keep_widget_state leaves them alone: a submit
    # button refuses reassignment, and the typed password should not be kept.
    with st.form("pyscattviz_login"):
        attempt = st.text_input(
            "Password",
            type="password",
            key=action_key(st.session_state, "pyscattviz_login_password"),
        )
        submitted = st.form_submit_button(
            "Sign in", key=action_key(st.session_state, "pyscattviz_login_submit")
        )
    if submitted:
        if password_matches(attempt, password):
            st.session_state[AUTH_KEY] = True
            st.rerun()
        st.error("Wrong password.")
    st.stop()
