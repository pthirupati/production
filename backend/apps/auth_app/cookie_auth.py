"""
CookieJWTAuthentication — drop-in replacement / companion for DRF simplejwt.

Tries the standard Authorization: Bearer header first, then falls back to the
httpOnly `access_token` cookie set by the login/register/refresh endpoints.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class CookieJWTAuthentication(JWTAuthentication):
    """Accept JWT from either Authorization header OR access_token cookie."""

    def authenticate(self, request):
        # 1. Try the standard Authorization: Bearer header first (existing behaviour)
        result = super().authenticate(request)
        if result is not None:
            return result

        # 2. Fall back to the httpOnly cookie
        raw_token = request.COOKIES.get("access_token")
        if raw_token is None:
            return None

        try:
            validated_token = self.get_validated_token(raw_token.encode())
            return self.get_user(validated_token), validated_token
        except (InvalidToken, TokenError):
            return None
