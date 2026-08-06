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

    # Capacity shedding gauges (audit Phase 0) — informational only.
    try:
        from apps.labs.capacity import count_active_engine_labs, get_max_concurrent_labs
        from django.core.cache import cache

        active = count_active_engine_labs()
        cap = get_max_concurrent_labs()
        shed = int(cache.get("fixitlab:capacity_shed_count") or 0)
        checks["lab_capacity"] = {
            "status": "ok",
            "active": active,
            "cap": cap,
            "shed_count": shed,
        }
    except Exception as exc:  # pragma: no cover
        checks["lab_capacity"] = {"status": "unknown", "error": str(exc)}

    # ── Redis / broker / Docker (audit Z5-10) ─────────────────────────────────
    #
    # Readiness checked only DB + Vault, so Redis could be dead while the container
    # reported healthy — and the visible symptom was sim labs silently resetting
    # (Z5-4), which looks like a lab bug rather than an infrastructure outage.
    #
    # These are reported as sub-statuses and move `overall` to "degraded", not
    # "error". That is deliberate and follows the Vault precedent: the cache is
    # configured with `IGNORE_EXCEPTIONS: True` precisely so a Redis hiccup degrades
    # to DB reads instead of 500ing every cached endpoint. Failing readiness would
    # pull the node out of rotation for a condition the application is explicitly
    # designed to survive — turning a degradation into an outage. "degraded" still
    # returns 200 and keeps serving; what it buys is that the dashboard says
    # "Redis" instead of leaving someone to infer it from lab behaviour.
    def _degrade():
        nonlocal overall
        if overall == "ok":
            overall = "degraded"

    try:
        from django.core.cache import cache

        probe = "fixitlab:readiness:probe"
        cache.set(probe, "1", timeout=10)
        if cache.get(probe) == "1":
            checks["redis"] = {"status": "ok"}
        else:
            # django-redis with IGNORE_EXCEPTIONS swallows the error and returns
            # None, so a silent miss is the *normal* signature of a dead Redis —
            # an exception is not raised for us to catch.
            checks["redis"] = {
                "status": "unavailable",
                "note": (
                    "cache set/get round trip failed; simulation lab state resets "
                    "between requests and throttles fail open"
                ),
            }
            _degrade()
    except Exception as exc:
        checks["redis"] = {"status": "unavailable", "error": str(exc)}
        _degrade()

    # Broker: Celery owns provisioning, teardown, email and the retention sweeps.
    # A dead broker does not stop the site serving pages, but labs stop starting.
    try:
        from celery_app.celery import app as celery_app

        conn = celery_app.connection()
        try:
            conn.ensure_connection(max_retries=0, timeout=2)
            checks["broker"] = {"status": "ok"}
        finally:
            conn.release()
    except Exception as exc:
        checks["broker"] = {
            "status": "unavailable",
            "error": str(exc),
            "note": "lab provisioning, teardown and outbound email are queued work",
        }
        _degrade()

    # Docker: only meaningful on a node that actually provisions containers, so a
    # missing socket elsewhere is "not_applicable" rather than a fault. Kept last
    # and behind a short timeout because it is the most expensive probe here.
    try:
        import docker

        client = docker.DockerClient(
            base_url=getattr(settings, "DOCKER_SOCKET", "unix:///var/run/docker.sock"),
            timeout=3,
        )
        try:
            client.ping()
            checks["docker"] = {"status": "ok"}
        finally:
            try:
                client.close()
            except Exception:
                pass
    except Exception as exc:
        checks["docker"] = {
            "status": "not_applicable",
            "detail": str(exc),
            "note": "no reachable Docker daemon on this node (expected off the lab host)",
        }

    code = 200 if overall in ("ok", "degraded") else 503
    return JsonResponse({"status": overall, "checks": checks}, status=code)


urlpatterns = [
    path("", health_check, name="health"),
    path("ready/", readiness_check, name="health-ready"),
]
