"""Canonical OAuth callback URLs — must match GitHub/Google app settings."""

from django.conf import settings


def canonical_frontend_url() -> str:
    return (settings.FRONTEND_URL or "").rstrip("/") or "http://localhost:8080"


def oauth_callback_url(provider: str) -> str:
    return f"{canonical_frontend_url()}/auth/callback/{provider}"
