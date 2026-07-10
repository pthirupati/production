"""OAuth CSRF protection — cryptographic state nonces bound to intent."""

import secrets

from django.core.cache import cache

OAUTH_STATE_TTL = 600  # 10 minutes
_VALID_INTENTS = frozenset({"login", "register", "link"})


def issue_oauth_state(intent: str) -> str:
    """Return provider state param: ``{intent}:{nonce}`` stored server-side."""
    if intent not in _VALID_INTENTS:
        intent = "login"
    nonce = secrets.token_urlsafe(32)
    cache.set(f"oauth_state:{nonce}", intent, OAUTH_STATE_TTL)
    return f"{intent}:{nonce}"


def validate_oauth_state(state: str) -> tuple[bool, str]:
    """
    Validate and consume a provider-returned state.
    Returns (ok, intent). Intent is best-effort when invalid.
    """
    if not state or ":" not in state:
        return False, "login"
    intent, nonce = state.split(":", 1)
    if intent not in _VALID_INTENTS or not nonce:
        return False, "login"
    stored = cache.get(f"oauth_state:{nonce}")
    if stored != intent:
        return False, intent
    cache.delete(f"oauth_state:{nonce}")
    return True, intent
