"""
CookieJWTAuthentication — drop-in replacement / companion for DRF simplejwt.

Tries the standard Authorization: Bearer header first, then falls back to the
httpOnly `access_token` cookie set by the login/register/refresh endpoints.

CSRF (SECURITY_AUDIT A-01): DRF's JWTAuthentication never calls enforce_csrf, so
a browser will auto-attach the httpOnly `access_token` cookie to a cross-site
state-changing request. SameSite=Lax blocks most of this, but a top-level
cross-site POST can still ride the cookie. To close that gap WITHOUT breaking
the SPA (which sends Authorization: Bearer for authenticated calls and the
``X-Requested-With`` header on every request), we require a custom header on the
COOKIE-authenticated path for unsafe methods. A cross-site HTML form cannot set
a custom header, so it is rejected; the Bearer-header path is unaffected (a
stolen-cookie CSRF can't forge an Authorization header either). Gated by
``settings.COOKIE_AUTH_REQUIRE_CSRF_HEADER`` (default True).
"""

from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.exceptions import AuthenticationFailed

from common.security import SessionTracker

# Methods that don't change state never need the CSRF header.
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
# Any one of these headers proves the request came from our JS (fetch/XHR), not
# a cross-site auto-submitting form. The SPA sets X-Requested-With globally.
_CSRF_HEADER_KEYS = ("HTTP_X_REQUESTED_WITH", "HTTP_X_CSRF_HEADER")


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

    @staticmethod
    def _enforce_cookie_csrf(request):
        """Reject cookie-authenticated unsafe requests that lack our JS header.

        Only applies to the cookie path (the header path is immune to CSRF since
        a cross-site form can't forge an Authorization header). No-op for safe
        methods and when the control is disabled.
        """
        if not getattr(settings, "COOKIE_AUTH_REQUIRE_CSRF_HEADER", True):
            return
        method = (getattr(request, "method", "") or "").upper()
        if method in _SAFE_METHODS:
            return
        if any(request.META.get(key) for key in _CSRF_HEADER_KEYS):
            return
        raise AuthenticationFailed(
            "Missing CSRF header for cookie-authenticated request.",
            code="csrf_header_required",
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
        except (InvalidToken, TokenError):
            return None

        # The cookie is valid — now require proof this isn't a cross-site form
        # POST before honouring it for a state change (A-01).
        self._enforce_cookie_csrf(request)
        self._validate_active_session(user, validated_token)
        return user, validated_token
