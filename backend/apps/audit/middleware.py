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

    Auth note (audit §Z2-1): Django's AuthenticationMiddleware never sees JWT —
    DRF authenticates inside the view. SecurityMiddleware stamps
    ``request.jwt_user_id`` from the Bearer token, so we prefer that (or an
    already-authenticated ``request.user``) instead of the always-false
    ``request.user.is_authenticated`` check that previously made this middleware dead.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user_id = self._resolve_user_id(request)
        if (
            user_id
            and request.path.startswith("/api/")
            and request.method in ("POST", "PUT", "DELETE", "PATCH")
        ):
            if any(request.path.startswith(p) for p in AUDIT_SKIP_PATHS):
                return response

            action = self._resolve_action(request)
            try:
                from apps.audit.tasks import create_audit_log
                create_audit_log.delay(
                    user_id=user_id,
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
                logger.warning("Audit log dispatch failed: %s", e)

        return response

    def _resolve_user_id(self, request):
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            return user.id
        jwt_uid = getattr(request, "jwt_user_id", None)
        if jwt_uid:
            try:
                return int(jwt_uid)
            except (TypeError, ValueError):
                return None
        return None

    def _resolve_action(self, request):
        """Map request path to a valid ACTION_CHOICES value."""
        path = request.path.rstrip("/")

        for prefix, action in AUDIT_PATH_MAP.items():
            if path.startswith(prefix):
                return action

        if "/labs/" in path:
            if "/start" in path:
                return "lab_start"
            if "/stop" in path:
                return "lab_stop"
            if "/validate" in path:
                return "validate"

        if path.startswith("/api/admin"):
            return "admin_action"

        return "admin_action"

    def _get_ip(self, request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
