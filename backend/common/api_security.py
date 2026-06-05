"""
Production API authentication enforcement.
Ensures all API endpoints require authentication (except whitelisted public endpoints).
"""

from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
import logging

logger = logging.getLogger(__name__)


def require_authentication(view_func):
    """
    Decorator to enforce authentication on API endpoints.
    Requires valid JWT token.
    
    Usage:
        @require_authentication
        def my_api_view(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            logger.warning(
                f"Unauthorized API access attempt: {request.method} {request.path}",
                extra={
                    'ip': request.META.get('REMOTE_ADDR'),
                    'user_agent': request.META.get('HTTP_USER_AGENT'),
                }
            )
            return Response(
                {'detail': 'Authentication credentials are required.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


# Public endpoints whitelist (only these don't require authentication)
PUBLIC_ENDPOINTS = {
    'POST': [
        '/api/auth/send-otp/',
        '/api/auth/verify-otp/',
        '/api/auth/register/',
        '/api/auth/login/',
        '/api/billing/webhook/stripe/',  # Stripe webhooks (signed)
        '/api/billing/webhook/razorpay/',  # Razorpay webhooks (signed)
        '/api/jira/webhooks/',  # Jira Cloud webhooks (secret query param)
    ],
    'GET': [
        '/health/',
        '/api/health/',
        '/api/billing/status/',  # Check if payment gateway is configured
        '/api/scenarios/list/',  # List free scenarios (no subscription needed)
        '/api/auth/profile/',  # Needs auth but handled separately
    ],
}


def is_public_endpoint(method, path):
    """Check if endpoint is in public whitelist."""
    allowed = PUBLIC_ENDPOINTS.get(method, [])
    return any(path.startswith(ep) for ep in allowed)


# Ensure all views have proper authentication
class AuthenticationEnforcer:
    """
    Middleware-like class to enforce authentication across all API endpoints.
    Applied via decorator on views.
    """
    
    @staticmethod
    def check_authentication(view_func):
        """
        Wrapper to ensure authentication is checked.
        Only allows public endpoints without auth.
        """
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            path = request.path
            method = request.method
            
            # Check if endpoint is public
            if is_public_endpoint(method, path):
                # Public endpoint - allow without auth
                return view_func(request, *args, **kwargs)
            
            # Private endpoint - require authentication
            if not request.user or not request.user.is_authenticated:
                logger.warning(
                    f"Unauthorized access to protected endpoint: {method} {path}",
                    extra={
                        'ip': request.META.get('REMOTE_ADDR', 'unknown'),
                        'path': path,
                    }
                )
                return Response(
                    {'detail': 'Authentication credentials are required.'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
