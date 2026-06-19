"""
CookieJWTAuthentication — drop-in replacement / companion for DRF simplejwt.

Tries the standard Authorization: Bearer header first, then falls back to the
httpOnly `access_token` cookie set by the login/register/refresh endpoints.
"""

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.exceptions import AuthenticationFailed

from common.security import SessionTracker


class CookieJWTAuthentication(JWTAuthentication):
    """Accept JWT from either Authorization header OR access_token cookie."""

    def _validate_active_session(self, user, validated_token):
        if not getattr(settings, "JWT_SESSION_ENFORCEMENT", True):
            return
        jti = validated_token.get("jti") if hasattr(validated_token, "get") else None
        if jti and not SessionTracker.is_session_valid(user.id, jti):
            raise AuthenticationFailed(
                "Your session has been invalidated. Please log in again.",
                code="session_invalidated",
            )

    def authenticate(self, request):
        # 1. Try the standard Authorization: Bearer header first (existing behaviour)
        result = super().authenticate(request)
        if result is not None:
            user, validated_token = result
            self._validate_active_session(user, validated_token)
            return user, validated_token

        # 2. Fall back to the httpOnly cookie
        raw_token = request.COOKIES.get("access_token")
        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token.encode())
            user = self.get_user(validated_token)
            self._validate_active_session(user, validated_token)
            return user, validated_token
        except (InvalidToken, TokenError):
            return None
