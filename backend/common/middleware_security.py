"""
JWT and session validation middleware for security hardening.
- Validates JWT tokens and tracks sessions
- Detects and prevents duplicate logins
- Extracts request metadata for structured logging
"""

from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
import jwt
import logging
import uuid
from functools import wraps

logger = logging.getLogger(__name__)

# Loopback origins are inherently trustworthy: a request whose REMOTE_ADDR is
# loopback came from this host (health checks, server-side / in-container E2E),
# not from a remote client, and its X-Forwarded-For cannot have been spoofed by
# an external party (nothing proxied it). Used by the admin fail-closed path.
_LOOPBACK_IPS = frozenset({"127.0.0.1", "::1", "localhost"})


def client_ip_from_request(request):
    """Return the real client IP, trusting only our own reverse proxy hop.

    SECURITY_AUDIT A-01: the left-most ``X-Forwarded-For`` entry is fully
    attacker-controlled (a client can send any ``X-Forwarded-For: 1.2.3.4`` and
    nginx APPENDS the real peer with ``$proxy_add_x_forwarded_for``, producing
    ``1.2.3.4, <real>``). Reading ``split(',')[0]`` therefore lets a client
    forge its IP, defeating the admin IP allowlist and the per-IP login
    brute-force throttle.

    We instead take the entry ``GATEWAY_PROXY_HOPS`` (default 1) positions from
    the RIGHT — i.e. the address our own nginx appended — which a client cannot
    forge. With a single trusted proxy this is the right-most XFF value; with N
    chained trusted proxies set ``GATEWAY_PROXY_HOPS=N``. If there is no XFF
    header (direct/in-container request) we fall back to ``REMOTE_ADDR``.
    """
    hops = int(getattr(settings, "GATEWAY_PROXY_HOPS", 1) or 1)
    if hops < 1:
        hops = 1
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "") or ""
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    if len(parts) >= hops:
        # The hop our trusted proxy added: count `hops` from the right.
        return parts[-hops]
    # Fewer hops than expected (no proxy in front, or direct loopback call):
    # trust the transport-level peer instead of a partially-spoofable XFF.
    return request.META.get("REMOTE_ADDR", "") or ""


class JWTSessionValidationMiddleware(MiddlewareMixin):
    """
    Middleware to validate JWT session state.
    Checks if the JWT token's jti (JWT ID) is still active for the user.
    
    This prevents duplicate login by invalidating the previous token
    when a user logs in from another device.
    """
    
    def process_request(self, request):
        """Extract JWT and validate session before view execution."""
        
        # Attach request ID for tracking
        request.id = str(uuid.uuid4())
        
        # Extract JWT token from Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        try:
            jwt_settings = getattr(settings, "SIMPLE_JWT", {})
            algorithm = jwt_settings.get("ALGORITHM", "HS256")
            verify_key = jwt_settings.get("VERIFYING_KEY") or jwt_settings.get("SIGNING_KEY")
            if verify_key:
                decoded = jwt.decode(
                    token,
                    verify_key,
                    algorithms=[algorithm],
                    options={"verify_exp": True},
                )
                user_id = decoded.get('user_id')
                jti = decoded.get('jti')
                
                if user_id and jti:
                    request.jwt_user_id = user_id
                    request.jwt_jti = jti
            else:
                logger.debug("JWT signing key not configured — skipping session pre-check")
                
        except Exception as e:
            # Token verification failed - let DRF handle authentication
            logger.debug(f"JWT decode error: {e}")
        
        return None


class RequestMetadataMiddleware(MiddlewareMixin):
    """
    Middleware to extract and store request metadata for structured logging.
    Adds IP address, user agent, method, path to request object.
    """
    
    def process_request(self, request):
        """Extract metadata at request start."""

        # Extract client IP from the trusted proxy hop (SECURITY_AUDIT A-01).
        # NOT the left-most X-Forwarded-For, which the client controls.
        request.client_ip = client_ip_from_request(request)

        # Extract user agent
        request.user_agent = request.META.get('HTTP_USER_AGENT', '')[:200]
        
        # Attach request start time for duration calculation
        import time
        request.start_time = time.time()
        
        return None


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add critical security headers to all responses.
    Prevents common attacks: XSS, clickjacking, MIME sniffing, etc.
    """
    
    def process_response(self, request, response):
        """Add security headers to response."""
        
        # Prevent MIME sniffing attacks
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Prevent clickjacking
        response['X-Frame-Options'] = 'DENY'
        
        # Prevent XSS (browser-based)
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer policy: don't leak sensitive URLs
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Feature policy: restrict dangerous APIs
        response['Permissions-Policy'] = (
            'accelerometer=(), camera=(), geolocation=(), '
            'gyroscope=(), magnetometer=(), microphone=(), '
            'payment=(), usb=()'
        )
        
        # Content Security Policy - strict
        if not settings.DEBUG:
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data: https:; "
                "font-src 'self' https://fonts.gstatic.com; "
                "connect-src 'self' https:; "
                "frame-ancestors 'none'"
            )
        
        return response


class AdminIPRestrictionMiddleware(MiddlewareMixin):
    """
    Restrict Django admin and admin API to configured IP addresses.

    When ADMIN_ALLOWED_IPS is empty:
      * dev (DEBUG) — all IPs allowed (development default).
      * prod with ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST=True — admin paths are
        default-DENIED (fail closed, SECURITY_AUDIT I-01).
      * prod with the flag False (default) — legacy fail-open (a startup warning
        is emitted in settings); set the flag on once the allowlist is populated.
    """

    ADMIN_PREFIXES = ("/django-admin/", "/api/admin/")

    def process_request(self, request):
        allowed_ips = getattr(settings, "ADMIN_ALLOWED_IPS", None) or []
        path = request.path
        is_admin_path = any(path.startswith(prefix) for prefix in self.ADMIN_PREFIXES)

        if not is_admin_path:
            return None

        # Resolve the un-spoofable client IP (right-most trusted-proxy hop).
        # REMOTE_ADDR is the transport peer; for a loopback/in-container caller
        # there is no XFF so this is loopback — which we always trust.
        client_ip = getattr(request, "client_ip", None) or client_ip_from_request(request)
        remote_addr = request.META.get("REMOTE_ADDR", "") or ""
        is_loopback = client_ip in _LOOPBACK_IPS or remote_addr in _LOOPBACK_IPS

        if not allowed_ips:
            # No allowlist configured. SECURITY_AUDIT I-04: fail CLOSED in
            # production by default so /api/admin/ + /django-admin/ are not
            # reachable from arbitrary internet IPs. Loopback / in-container
            # callers (health checks, server-side E2E run via
            # `docker compose exec ... e2e`) are always allowed — their origin
            # is this host and cannot be spoofed by a remote client.
            fail_closed = not getattr(settings, "DEBUG", False) and getattr(
                settings, "ADMIN_FAIL_CLOSED_WITHOUT_ALLOWLIST", True
            )
            if fail_closed and not is_loopback:
                logger.warning(
                    "Admin access denied (fail-closed: ADMIN_ALLOWED_IPS unset) "
                    "for IP %s on %s",
                    client_ip, path,
                )
                return JsonResponse(
                    {"detail": "Admin access is restricted. No allowlist is configured."},
                    status=403,
                )
            return None

        # An allowlist is configured: permit listed IPs plus loopback callers.
        if client_ip in allowed_ips or is_loopback:
            return None

        logger.warning("Admin access denied for IP %s on %s", client_ip, path)
        return JsonResponse(
            {"detail": "Admin access is restricted to authorized IP addresses."},
            status=403,
        )


def require_session_valid(view_func):
    """
    Decorator to check if JWT session is still active.
    Use on views that require session validation.
    
    Usage:
        @require_session_valid
        def my_view(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Skip if user not authenticated
        if not request.user or not request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        
        # Check if JWT session is valid (runtime-aware enforcement toggle)
        from common.security import SessionTracker, session_enforcement_enabled
        if hasattr(request, 'jwt_jti') and session_enforcement_enabled():
            if not SessionTracker.is_session_valid(request.user.id, request.jwt_jti):
                logger.warning(
                    f"Invalid JWT session detected for user {request.user.id}: "
                    f"jti={request.jwt_jti[:16]}... - likely duplicate login"
                )
                return JsonResponse(
                    {
                        "detail": "Your session has been invalidated. "
                        "You've logged in from another device. Please log in again.",
                        "code": "SESSION_INVALIDATED",
                    },
                    status=401
                )
        
        return view_func(request, *args, **kwargs)
    
    return wrapper
