"""Public REST API for the free, ephemeral Playgrounds.

All endpoints are ``AllowAny`` (no login, no subscription) and rate-limited
per-IP via :class:`PlaygroundRateThrottle`. They never write to the database —
session state is in-memory and idle-expired by ``playground_engine`` — so a
visitor can "try instantly" without leaving anything behind.

The client generates an opaque, ephemeral ``session`` id (a UUID) per tab and
sends it with each action; it only keys the in-memory sandbox and is never
stored server-side.
"""

import logging

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.throttles import PlaygroundRateThrottle

from . import playground_engine as pg

logger = logging.getLogger(__name__)

# Bound the session-id length so a client can't use it as an unbounded memory key.
_MAX_SESSION_ID_LEN = 100


def _session_id(request) -> str:
    raw = ""
    data = getattr(request, "data", None)
    if isinstance(data, dict):
        raw = str(data.get("session") or "")
    if not raw:
        raw = str(request.query_params.get("session") or "")
    return raw[:_MAX_SESSION_ID_LEN]


class PlaygroundListView(APIView):
    """GET /api/playgrounds/ — the public catalogue of available playgrounds."""

    permission_classes = [AllowAny]
    throttle_classes = [PlaygroundRateThrottle]

    def get(self, request):
        return Response({"playgrounds": pg.public_catalogue()})


class PlaygroundDetailView(APIView):
    """GET /api/playgrounds/<slug>/ — metadata + starter content for one playground."""

    permission_classes = [AllowAny]
    throttle_classes = [PlaygroundRateThrottle]

    def get(self, request, slug):
        definition = pg.get_definition(slug)
        if not definition:
            return Response({"error": "Unknown playground"}, status=404)

        payload = {
            "slug": definition["slug"],
            "name": definition["name"],
            "tagline": definition["tagline"],
            "category": definition["category"],
            "icon": definition.get("icon", "terminal"),
            "kind": definition["kind"],
            "language": definition.get("language", ""),
            "scenario_slug": definition.get("scenario_slug", ""),
            "starter": definition.get("starter", []),
            "starter_code": definition.get("starter_code", ""),
            "idle_timeout_seconds": pg.IDLE_TTL_SECONDS,
            "ephemeral": True,
        }
        if definition["kind"] == "terminal":
            try:
                payload["prompt"] = pg.terminal_banner(definition).get("prompt", "$ ")
            except Exception:
                payload["prompt"] = "$ "
        return Response(payload)


class PlaygroundRunView(APIView):
    """POST /api/playgrounds/<slug>/run/ — execute one action in the sandbox.

    Body: ``{"session": "<uuid>", "input": "<command|sql|code>", "stdin": ""}``
    The action dispatched depends on the playground ``kind``.
    """

    permission_classes = [AllowAny]
    throttle_classes = [PlaygroundRateThrottle]

    def post(self, request, slug):
        definition = pg.get_definition(slug)
        if not definition:
            return Response({"error": "Unknown playground"}, status=404)

        kind = definition["kind"]
        if kind == "lab_link":
            return Response(
                {
                    "ok": False,
                    "error": "This playground links to a full lab — start a scenario to practise it.",
                },
                status=400,
            )

        body = request.data if isinstance(request.data, dict) else {}
        user_input = str(body.get("input") or "")
        session_id = _session_id(request)
        if kind in ("terminal", "sql") and not session_id:
            return Response({"ok": False, "error": "Missing session id."}, status=400)

        try:
            if kind == "terminal":
                result = pg.run_terminal(session_id, definition, user_input)
            elif kind == "sql":
                result = pg.run_sql(session_id, definition, user_input)
            elif kind == "code":
                result = pg.run_code(definition, user_input, str(body.get("stdin") or ""))
            else:  # pragma: no cover - defensive
                return Response({"ok": False, "error": "Unsupported playground."}, status=400)
        except Exception:
            logger.exception("Playground run failed for slug=%s kind=%s", slug, kind)
            return Response(
                {"ok": False, "error": "The playground engine hit an error. Try again."},
                status=200,  # public page: surface as an in-UI error, not a toast-y 500
            )

        status = 200 if result.get("ok", True) else 400
        return Response(result, status=status)


class PlaygroundResetView(APIView):
    """POST /api/playgrounds/<slug>/reset/ — wipe this session's in-memory state."""

    permission_classes = [AllowAny]
    throttle_classes = [PlaygroundRateThrottle]

    def post(self, request, slug):
        definition = pg.get_definition(slug)
        if not definition:
            return Response({"error": "Unknown playground"}, status=404)
        session_id = _session_id(request)
        if session_id:
            pg.reset(session_id)
        return Response({"reset": True})
