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

        # ─── Diagnostic: shows secret-key shape (no values) ─────
        # TEMP — remove once auth is verified working in production.
        with st.expander("🔧 Auth config check (debug)", expanded=True):
            try:
                cfg = dict(st.secrets.get("auth", {}))
                shape = {
                    k: (
                        f"str(len={len(v)})"
                        if isinstance(v, str)
                        else f"dict(keys={sorted(v.keys())})"
                        if isinstance(v, dict)
                        else type(v).__name__
                    )
                    for k, v in cfg.items()
                }
                st.write({"keys_present": sorted(cfg.keys()), "shapes": shape})
                expected = {"client_id", "client_secret", "redirect_uri",
                            "cookie_secret", "server_metadata_url"}
                missing = expected - set(cfg.keys())
                if missing:
                    st.error(f"Missing required keys: {sorted(missing)}")
            except Exception as e:
                st.error(f"Secrets read error — {type(e).__name__}: {e}")

        if st.button("Sign in with Google", type="primary"):
            try:
                # Uses the default provider in [auth] secrets. To support multiple
                # providers, namespace them as [auth.google] and call
                # st.login("google") instead.
                st.login()
            except Exception as e:
                st.error(f"Sign-in failed — {type(e).__name__}: {e}")
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
