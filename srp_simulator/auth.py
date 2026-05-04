"""Optional Google OIDC auth gate, restricted to a single email domain.

Activated only when an ``[auth]`` block is present in Streamlit secrets
(``client_id`` set). Otherwise this is a no-op so local dev and pre-auth
deploys keep working.

Usage (top of app.py, after ``st.set_page_config``)::

    from srp_simulator.auth import require_auth
    require_auth(allowed_domain="onarrival.travel")
"""

from __future__ import annotations

import streamlit as st


def _auth_configured() -> bool:
    try:
        return bool(st.secrets.get("auth", {}).get("client_id"))
    except Exception:
        return False


def require_auth(allowed_domain: str) -> None:
    """Block the app until the user signs in with an allowed-domain Google account.

    No-op when ``[auth]`` is not configured in secrets.
    """
    if not _auth_configured():
        return

    if not st.user.is_logged_in:
        st.title("Mirador")
        st.caption(f"Sign in with your @{allowed_domain} Google account to continue.")
        if st.button("Sign in with Google", type="primary"):
            st.login("google")
        st.stop()

    email = (st.user.email or "").lower()
    if not email.endswith(f"@{allowed_domain}"):
        st.error(
            f"Access restricted to @{allowed_domain} accounts. "
            f"You're signed in as `{email}`."
        )
        if st.button("Sign out"):
            st.logout()
        st.stop()
