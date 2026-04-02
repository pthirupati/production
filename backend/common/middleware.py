"""
Custom security middleware for FixitLab.
"""
import logging
from django.http import HttpResponseForbidden

logger = logging.getLogger(__name__)


class AdminAccessMiddleware:
    """
    Defense-in-depth: restrict /django-admin/ to superusers only.
    Even if nginx IP-restriction is bypassed, this ensures only
    authenticated superusers can access the Django admin panel.

    Non-superusers get a 403 Forbidden response.
    Anonymous users are redirected to the admin login page (default Django behavior).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/django-admin/"):
            # Allow login page itself (so superusers can authenticate)
            if request.path in ("/django-admin/login/", "/django-admin/logout/"):
                return self.get_response(request)

            # If user is authenticated but NOT a superuser, block access
            if request.user.is_authenticated and not request.user.is_superuser:
                logger.warning(
                    f"Non-superuser {request.user.username} ({request.META.get('REMOTE_ADDR')}) "
                    f"attempted to access Django admin: {request.path}"
                )
                return HttpResponseForbidden(
                    "<h1>403 Forbidden</h1><p>You do not have permission to access this page.</p>",
                    content_type="text/html",
                )

        return self.get_response(request)
