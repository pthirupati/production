"""REST API for VMware, Kubernetes, and Docker Simulator UIs."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.labs.models import LabSession

from .engine import apply_action, drop_session, get_state
from .k8s_engine import apply_action as k8s_apply_action
from .k8s_engine import drop_session as k8s_drop_session
from .k8s_engine import get_state as k8s_get_state
from .docker_engine import apply_action as docker_apply_action
from .docker_engine import drop_session as docker_drop_session
from .docker_engine import get_state as docker_get_state


def _demo_session_id(user) -> str:
    """Stable sandbox key for standalone VMware simulator (no lab session)."""
    return f"demo-{user.pk}"


# ---------------------------------------------------------------------------
# VMware views
# ---------------------------------------------------------------------------

class VMwareSimDemoStateView(APIView):
    """Standalone VMware sandbox — no LabSession required (e.g. /vmware-sim)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        slug = request.query_params.get("scenario", "") or ""
        sid = _demo_session_id(request.user)
        return Response(get_state(sid, slug))


class VMwareSimDemoActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        sid = _demo_session_id(request.user)
        slug = request.data.get("scenario", "") or request.query_params.get("scenario", "") or ""
        get_state(sid, slug)
        result = apply_action(sid, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": get_state(sid, slug)})


class VMwareSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario", "scenario__technology").filter(
            pk=session_id, user=request.user,
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        # Prefer slug from DB; fall back to query param (e.g. when redirected from LabRunner)
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(get_state(session_id, slug))


class VMwareSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        # Ensure the simulation session is initialized in Redis before applying any action
        get_state(session_id, slug)
        result = apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        slug = session.scenario.slug if session.scenario_id else ""
        return Response({**result, "state": get_state(session_id, slug)})


class VMwareSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        drop_session(session_id)
        return Response({"released": True})


# ---------------------------------------------------------------------------
# Kubernetes views
# ---------------------------------------------------------------------------

class K8sSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario", "scenario__technology").filter(
            pk=session_id, user=request.user,
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(k8s_get_state(session_id, slug))


class K8sSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        # Ensure the simulation session is initialized in Redis before applying any action
        k8s_get_state(session_id, slug)
        result = k8s_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": k8s_get_state(session_id, slug)})


class K8sSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        k8s_drop_session(session_id)
        return Response({"released": True})


# ---------------------------------------------------------------------------
# Docker views
# ---------------------------------------------------------------------------

class DockerSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario", "scenario__technology").filter(
            pk=session_id, user=request.user,
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(docker_get_state(session_id, slug))


class DockerSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        # Ensure the simulation session is initialized in Redis before applying any action
        docker_get_state(session_id, slug)
        result = docker_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": docker_get_state(session_id, slug)})


class DockerSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        docker_drop_session(session_id)
        return Response({"released": True})
