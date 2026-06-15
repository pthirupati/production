"""Canonical OAuth callback URLs — must match GitHub/Google app settings."""

from urllib.parse import urlencode

from django.conf import settings


def canonical_frontend_url() -> str:
    """Single canonical origin for OAuth callbacks (apex, no trailing slash)."""
    explicit = getattr(settings, "GITHUB_OAUTH_CALLBACK_URL", "") or getattr(
        settings, "OAUTH_CALLBACK_BASE_URL", ""
    )
    if explicit:
        base = explicit.strip().rstrip("/")
        if base.endswith("/auth/callback/github"):
            return base[: -len("/auth/callback/github")]
        if base.endswith("/auth/callback/google"):
            return base[: -len("/auth/callback/google")]
        return base
    url = (settings.FRONTEND_URL or "").strip().rstrip("/") or "http://localhost:8080"
    # GitHub OAuth apps allow one callback URL — always use apex for fixitlab.in
    url = url.replace("://www.fixitlab.in", "://fixitlab.in")
    return url


def oauth_callback_url(provider: str) -> str:
    return f"{canonical_frontend_url()}/auth/callback/{provider}"


def github_authorize_url(*, intent: str = "login") -> str:
    """Full GitHub authorize URL with canonical redirect_uri (matches token exchange)."""
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": oauth_callback_url("github"),
        "scope": "user:email",
        "state": intent,
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


def google_authorize_url(*, intent: str = "login") -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": oauth_callback_url("google"),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": intent,
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
