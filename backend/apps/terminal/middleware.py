"""
JWT WebSocket authentication middleware for Django Channels.
Extracts JWT token from query string: ws://host/ws/terminal/<id>/?token=<jwt>
"""
import logging
from urllib.parse import parse_qs
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
    """Validate JWT token and return the user."""
    try:
        token = AccessToken(_coerce_token_str(token_str))
        user_id = token["user_id"]
        return User.objects.get(id=user_id)
    except Exception as e:
        logger.warning(f"WebSocket JWT auth failed: {e}")
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware that authenticates WebSocket connections via JWT
    token passed in the query string.
    """
    async def __call__(self, scope, receive, send):
        params = parse_qs(_scope_query_string(scope))
        token_list = params.get("token", [])

        if token_list:
            scope["user"] = await get_user_from_token(token_list[0])
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
