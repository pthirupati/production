import logging
from .models import AuditLog

logger = logging.getLogger(__name__)

# Map API paths to audit actions
AUDIT_PATH_MAP = {
    "/api/auth/login": "login",
    "/api/auth/register": "login",
    "/api/auth/logout": "logout",
    "/api/admin/": "admin_action",
}

# Skip high-frequency read-only endpoints from audit
AUDIT_SKIP_PATHS = {
    "/api/scenarios/",
    "/api/technologies/",
    "/api/categories/",
    "/api/tags/",
    "/api/stats/",
    "/api/leaderboard/",
}


class AuditMiddleware:
    """
    Capture authenticated user actions with proper action types.
    Only logs mutating (POST/PUT/DELETE) API calls to avoid log flooding.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only log authenticated POST/PUT/DELETE calls
        if (
            request.user.is_authenticated
            and request.path.startswith("/api/")
            and request.method in ("POST", "PUT", "DELETE")
        ):
            # Skip high-frequency endpoints
            if any(request.path.startswith(p) for p in AUDIT_SKIP_PATHS):
                return response

            action = self._resolve_action(request)
            try:
                AuditLog.objects.create(
                    user=request.user,
                    action=action,
                    resource=request.path,
                    metadata={
                        "method": request.method,
                        "status_code": response.status_code,
                    },
                    ip_address=self._get_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                )
            except Exception as e:
                logger.warning(f"Audit log failed: {e}")

        return response

    def _resolve_action(self, request):
        """Map request path to a valid ACTION_CHOICES value."""
        path = request.path.rstrip("/")

        for prefix, action in AUDIT_PATH_MAP.items():
            if path.startswith(prefix):
                return action

        # Map lab-related paths
        if "/labs/" in path:
            if "/start" in path:
                return "lab_start"
            if "/stop" in path:
                return "lab_stop"
            if "/validate" in path:
                return "validate"

        # Default for admin paths
        if path.startswith("/api/admin"):
            return "admin_action"

        return "admin_action"  # Safe fallback (exists in ACTION_CHOICES)

    def _get_ip(self, request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

