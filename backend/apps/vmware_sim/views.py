"""REST API for VMware Simulator UI."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.labs.models import LabSession

from .engine import apply_action, drop_session, get_state


class VMwareSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario", "scenario__technology").filter(
            pk=session_id, user=request.user,
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else ""
        return Response(get_state(session_id, slug))


class VMwareSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        result = apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        slug = session.scenario.slug if session.scenario_id else ""
        return Response({**result, "state": get_state(session_id, slug)})


class VMwareSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        drop_session(session_id)
        return Response({"released": True})
