"""
JWT WebSocket authentication middleware for Django Channels.
Authenticates via the httpOnly access_token cookie (same as REST API).
Query-string ?token= is ignored — tokens must not appear in URLs/logs.
"""
import logging

from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


def _scope_query_string(scope) -> str:
    """Normalize ASGI query_string (bytes, str, or accidental tuple) to str."""
    raw = scope.get("query_string", b"")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    if isinstance(raw, (tuple, list)):
        parts = []
        for chunk in raw:
            if isinstance(chunk, bytes):
                parts.append(chunk.decode("utf-8", errors="replace"))
            elif isinstance(chunk, str):
                parts.append(chunk)
            elif isinstance(chunk, (tuple, list)):
                parts.append(_scope_query_string({"query_string": chunk}))
        return "".join(parts)
    return ""


def _cookie_from_scope(scope, name: str) -> str | None:
    for header, value in scope.get("headers") or []:
        if header.lower() != b"cookie":
            continue
        try:
            raw = value.decode("utf-8", errors="replace")
        except AttributeError:
            raw = str(value)
        for part in raw.split(";"):
            key, _, val = part.strip().partition("=")
            if key == name and val:
                return val
    return None


def _coerce_token_str(token_str) -> str:
    if isinstance(token_str, str):
        return token_str
    if isinstance(token_str, bytes):
        return token_str.decode("utf-8", errors="replace")
    if isinstance(token_str, (tuple, list)) and token_str:
        return _coerce_token_str(token_str[0])
    return str(token_str or "")


@database_sync_to_async
def get_user_from_token(token_str):
    """Validate JWT token, enforce session revocation, and return the user."""
    try:
        token = AccessToken(_coerce_token_str(token_str))
        user_id = token["user_id"]
        jti = token.get("jti")
        user = User.objects.get(id=user_id)

        from common.security import SessionTracker, session_enforcement_enabled
        if session_enforcement_enabled() and jti and not SessionTracker.is_session_valid(user.id, jti):
            logger.warning("WebSocket JWT session revoked: user=%s jti=%s...", user_id, jti[:16])
            return AnonymousUser()

        return user
    except Exception as e:
        logger.warning(f"WebSocket JWT auth failed: {e}")
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Authenticate WebSocket connections via the httpOnly access_token cookie.
    """

    async def __call__(self, scope, receive, send):
        token_str = _cookie_from_scope(scope, "access_token")
        if token_str:
            scope["user"] = await get_user_from_token(token_str)
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
