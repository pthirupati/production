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
