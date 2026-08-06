"""Signed one-click marketing unsubscribe tokens."""

from __future__ import annotations

from django.conf import settings
from django.core.signing import BadSignature, Signer

SIGNER_SALT = "fixitlab-marketing-unsubscribe"


def _signer() -> Signer:
    return Signer(salt=SIGNER_SALT)


def make_marketing_unsubscribe_token(user_id: int) -> str:
    return _signer().sign(str(user_id))


def verify_marketing_unsubscribe_token(token: str) -> int | None:
    try:
        return int(_signer().unsign(token))
    except (BadSignature, ValueError, TypeError):
        return None


def marketing_unsubscribe_url(user_id: int) -> str:
    token = make_marketing_unsubscribe_token(user_id)
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/unsubscribe?token={token}"


def marketing_unsubscribe_api_url(user_id: int) -> str:
    """The POST-able endpoint for RFC 8058 one-click unsubscribe.

    Distinct from ``marketing_unsubscribe_url``, which is a frontend *page* a human
    clicks. One-click requires a URL the mail provider can POST to unattended, with
    no confirmation step and no login — that is the API view, which accepts POST and
    reads the signed token from the query string.
    """
    token = make_marketing_unsubscribe_token(user_id)
    # The gateway serves the SPA and /api on the same host, so FRONTEND_URL is the
    # correct base. BACKEND_PUBLIC_URL is honoured first in case they ever split.
    base = (
        getattr(settings, "BACKEND_PUBLIC_URL", "")
        or getattr(settings, "FRONTEND_URL", "")
        or ""
    ).rstrip("/")
    return f"{base}/api/notifications/unsubscribe/?token={token}"


def list_unsubscribe_headers(user_id: int) -> dict:
    """RFC 8058 / RFC 2369 headers Gmail and Yahoo have REQUIRED of bulk senders
    since February 2024. Without them, marketing mail is far more likely to be
    classified as spam — which also drags down the domain reputation that
    transactional mail (OTP, password reset) depends on.
    """
    return {
        "List-Unsubscribe": f"<{marketing_unsubscribe_api_url(user_id)}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
