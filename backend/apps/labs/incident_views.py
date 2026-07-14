"""API surface for the Live Incident Director + public postmortem artifact.

Two entrypoints, both additive:

* ``PublicPostmortemView`` — GET /api/labs/postmortem/<public_token>/ is
  ``AllowAny`` and read-only. It returns exactly the one tokened postmortem
  (never a list, never another user's data) plus a replay reference. The path is
  NOT under the admin-IP-gated prefixes (/django-admin/, /api/admin/), so it
  works as an unauthenticated portfolio share link.

* ``IncidentDirectorView`` — POST /api/labs/incidents/director/ is
  authenticated and FLAG-GUARDED (settings.INCIDENT_DIRECTOR_ENABLED). It starts
  a Director-driven incident on the caller's own live lab session and can advance
  an escalation. Off by default so normal lab flows are unaffected.
"""

from __future__ import annotations

import logging

from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class PublicPostmortemView(APIView):
    """GET /api/labs/postmortem/<public_token>/ — public, read-only, no auth.

    Returns 200 with the postmortem for a valid token, 404 otherwise. Leaks no
    other users' data: the token is the only selector and we return only that
    single object.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []  # no auth attempted; purely token-gated

    def get(self, request, public_token):
        from .models import Postmortem

        pm = (
            Postmortem.objects.filter(public_token=public_token, is_public=True)
            .select_related("incident_run", "lab_session")
            .first()
        )
        if pm is None:
            return Response({"error": "Postmortem not found"}, status=404)

        return Response({
            "public_token": str(pm.public_token),
            "title": pm.title,
            "created_at": pm.created_at.isoformat() if pm.created_at else None,
            "postmortem": pm.data,
            "markdown": pm.markdown,
            "replay": (pm.data or {}).get("replay"),
        })


class IncidentDirectorView(APIView):
    """POST /api/labs/incidents/director/ — flag-guarded Director entrypoint.

    Body: {session_id, action?, template_key?, difficulty?, seed?}
      action="start" (default) — seed a Director-driven incident on the session.
      action="escalate"        — advance the next escalation on the session.

    Requires the caller to own the LabSession. Returns 404 if the flag is off so
    the surface is invisible unless explicitly enabled.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .incident_director import IncidentDirector, director_enabled
        from .models import IncidentRun, LabSession

        if not director_enabled():
            return Response({"error": "Not found"}, status=404)

        data = request.data if isinstance(request.data, dict) else {}
        session_id = data.get("session_id")
        if not session_id:
            return Response({"error": "session_id required"}, status=400)

        session = LabSession.objects.filter(id=session_id, user=request.user).first()
        if session is None:
            return Response({"error": "Session not found"}, status=404)

        action = (data.get("action") or "start").lower()
        seed = data.get("seed") or str(session.id)

        if action == "start":
            director = IncidentDirector(
                seed=seed,
                template_key=data.get("template_key", ""),
                difficulty=data.get("difficulty", ""),
            )
            applied = director.seed_incident(str(session.id))
            run = IncidentRun.objects.create(
                lab_session=session,
                template_key=director.template_key,
                seed=str(seed),
                root_cause=director.template.root_cause,
                detection_signal=director.template.detection_signal,
                difficulty=director.template.difficulty,
                director_plan=director.summary(),
                detected_at=timezone.now(),
            )
            return Response({
                "incident_run_id": str(run.id),
                "applied": applied,
                "plan": director.summary(),
            })

        if action == "escalate":
            run = (
                IncidentRun.objects.filter(lab_session=session)
                .order_by("-started_at")
                .first()
            )
            if run is None:
                return Response({"error": "No incident run to escalate"}, status=404)
            director = IncidentDirector(seed=run.seed or str(session.id),
                                        template_key=run.template_key)
            director.escalations = list(run.escalations or [])
            director._escalation_fired = bool(run.escalations)
            record = director.next_escalation(str(session.id))
            if record is None:
                return Response({"escalated": False, "reason": "already escalated"})
            run.escalations = director.escalations
            plan = dict(run.director_plan or {})
            plan["escalations"] = director.escalations
            run.director_plan = plan
            run.save(update_fields=["escalations", "director_plan"])
            return Response({"escalated": True, "escalation": record})

        return Response({"error": f"Unknown action: {action}"}, status=400)
