"""Lightweight health check — no authentication required.
Only accessible internally (Docker/k8s healthchecks).
External access is blocked by nginx in production.
"""
from django.http import JsonResponse
from django.urls import path


def health_check(request):
    """Return 200 OK if the server is running.
    Deliberately minimal — no DB/Redis/version info exposed.
    This is a liveness probe only. Readiness probes should check dependencies.
    """
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("", health_check, name="health"),
]
