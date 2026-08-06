"""Health and readiness probes — minimal public liveness; richer internal readiness."""

import logging
import os

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.urls import path

logger = logging.getLogger(__name__)


def health_check(request):
    """Liveness — server process is up."""
    return JsonResponse({"status": "ok"})


def _vault_status() -> dict:
    """Report Vault without failing liveness when API is down but secrets were loaded."""
    enabled = str(getattr(settings, "VAULT_ENABLED", "") or os.environ.get("VAULT_ENABLED", "")).lower() in (
        "1", "true", "yes", "on",
    )
    if not enabled:
        return {"enabled": False, "status": "disabled"}

    try:
        from config.vault_loader import _VAULT_LOADED, vault_api_reachable

        loaded = _VAULT_LOADED
        reachable = vault_api_reachable()
    except Exception as exc:
        logger.debug("Vault readiness check failed: %s", exc)
        loaded = False
        reachable = False

    if loaded and reachable:
        status = "ok"
    elif loaded:
        status = "degraded"
    else:
        status = "unavailable"

    return {
        "enabled": True,
        "status": status,
        "secrets_loaded": loaded,
        "api_reachable": reachable,
    }


def readiness_check(request):
    """Readiness — dependencies required to serve traffic (used by deploy/CI)."""
    checks: dict = {}
    overall = "ok"

    try:
        connection.ensure_connection()
        checks["database"] = {"status": "ok"}
    except Exception as exc:
        checks["database"] = {"status": "error", "error": str(exc)}
        overall = "error"

    vault = _vault_status()
    checks["vault"] = vault
    # Vault is a live secret SOURCE, not a hard runtime dependency. In the 4D
    # cluster the backend runs on the APP node while Vault lives on the EDGE, so
    # the app node loads its secrets from the rendered/baked env by design. If this
    # process is serving the request, its critical secrets (SECRET_KEY, DB creds,
    # …) are already present — a sealed/unreachable Vault is a by-design fallback,
    # NOT a readiness failure. Surface it as an informational sub-status but keep
    # the node "ok" as long as the database is reachable. Only a genuinely missing
    # secret would prevent the process from booting at all (so it couldn't answer
    # this probe). Rotation still flows through the edge Vault when available.
    if vault.get("enabled") and vault.get("status") in ("unavailable", "degraded"):
        checks["vault"]["note"] = (
            "live Vault unavailable on this node; serving from rendered/baked env "
            "(Vault is a rotation source, not required to serve traffic)"
        )

    # Informational gauge, never a readiness failure.
    #
    # _SIM_SESSIONS is a process-local registry of live simulation engines, and it
    # leaks across workers (audit Z5-1). Without this number an OOM caused by that
    # leak is indistinguishable from a random worker restart, which is exactly what
    # made it hard to spot. Each uvicorn worker reports its OWN count, so polling
    # this endpoint repeatedly will show different values — that is the point.
    try:
        from apps.labs.provisioner.simulation.shell import sim_session_count

        checks["sim_sessions"] = {"status": "ok", "count": sim_session_count()}
    except Exception as exc:  # pragma: no cover - never fail readiness on a gauge
        checks["sim_sessions"] = {"status": "unknown", "error": str(exc)}

    code = 200 if overall in ("ok", "degraded") else 503
    return JsonResponse({"status": overall, "checks": checks}, status=code)


urlpatterns = [
    path("", health_check, name="health"),
    path("ready/", readiness_check, name="health-ready"),
]
