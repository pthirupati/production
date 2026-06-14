"""
Custom DRF throttles for resource-intensive operations.
"""
from rest_framework.throttling import UserRateThrottle


class LabStartThrottle(UserRateThrottle):
    """
    Limit new lab provisions per user. Staff are exempt; resumed sessions
    for the same scenario do not consume quota.
    """
    scope = "lab_start"
    rate = "60/hour"

    def allow_request(self, request, view):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
                return True
            scenario_id = getattr(view, "kwargs", {}).get("scenario_id")
            if scenario_id:
                from apps.labs.models import LabSession
                if LabSession.objects.filter(
                    user=user,
                    scenario_id=scenario_id,
                    status__in=["RUNNING", "PROVISIONING"],
                ).exists():
                    return True
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return super().get_cache_key(request, view)
