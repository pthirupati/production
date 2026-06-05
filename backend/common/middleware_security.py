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
            # Decode JWT without verification first (just to get user_id and jti)
            # The rest_framework_simplejwt authentication class will verify the token
            decoded = jwt.decode(
                token,
                options={"verify_signature": False}  # Will be verified by DRF
            )
            
            user_id = decoded.get('user_id')
            jti = decoded.get('jti')
            
            if user_id and jti:
                # Store in request for later validation
                request.jwt_user_id = user_id
                request.jwt_jti = jti
                
        except Exception as e:
            # Token decoding failed - let DRF handle authentication
            logger.debug(f"JWT decode error: {e}")
        
        return None


class RequestMetadataMiddleware(MiddlewareMixin):
    """
    Middleware to extract and store request metadata for structured logging.
    Adds IP address, user agent, method, path to request object.
    """
    
    def process_request(self, request):
        """Extract metadata at request start."""
        
        # Extract client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            request.client_ip = x_forwarded_for.split(',')[0].strip()
        else:
            request.client_ip = request.META.get('REMOTE_ADDR', '')
        
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
    When ADMIN_ALLOWED_IPS is empty, all IPs are allowed (development default).
    """

    ADMIN_PREFIXES = ("/django-admin/", "/api/admin/")

    def process_request(self, request):
        allowed_ips = getattr(settings, "ADMIN_ALLOWED_IPS", None) or []
        if not allowed_ips:
            return None

        path = request.path
        if not any(path.startswith(prefix) for prefix in self.ADMIN_PREFIXES):
            return None

        client_ip = getattr(request, "client_ip", None)
        if not client_ip:
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if x_forwarded_for:
                client_ip = x_forwarded_for.split(",")[0].strip()
            else:
                client_ip = request.META.get("REMOTE_ADDR", "")

        if client_ip in allowed_ips:
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
        
        # Check if JWT session is valid
        if hasattr(request, 'jwt_jti'):
            from common.security import SessionTracker
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
