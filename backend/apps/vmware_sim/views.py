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
from .monitoring_engine import apply_action as monitoring_apply_action
from .monitoring_engine import drop_session as monitoring_drop_session
from .monitoring_engine import get_state as monitoring_get_state
from .nmap_engine import apply_action as nmap_apply_action
from .nmap_engine import drop_session as nmap_drop_session
from .nmap_engine import get_state as nmap_get_state
from .wireshark_engine import apply_action as wireshark_apply_action
from .wireshark_engine import drop_session as wireshark_drop_session
from .wireshark_engine import get_state as wireshark_get_state
from .datascience_engine import apply_action as datascience_apply_action
from .datascience_engine import drop_session as datascience_drop_session
from .datascience_engine import get_state as datascience_get_state
from .aiml_engine import apply_action as aiml_apply_action
from .aiml_engine import drop_session as aiml_drop_session
from .aiml_engine import get_state as aiml_get_state
from .windows_engine import apply_action as windows_apply_action
from .windows_engine import drop_session as windows_drop_session
from .windows_engine import get_state as windows_get_state
from .peoplesoft_engine import apply_action as peoplesoft_apply_action
from .peoplesoft_engine import drop_session as peoplesoft_drop_session
from .peoplesoft_engine import get_state as peoplesoft_get_state
from .awx_engine import apply_action as awx_apply_action
from .awx_engine import drop_session as awx_drop_session
from .awx_engine import get_state as awx_get_state
from .cicd_engine import apply_action as cicd_apply_action
from .cicd_engine import drop_session as cicd_drop_session
from .cicd_engine import get_state as cicd_get_state
from .terraform_engine import apply_action as terraform_apply_action
from .terraform_engine import drop_session as terraform_drop_session
from .terraform_engine import get_state as terraform_get_state
from .baremetal_engine import apply_action as baremetal_apply_action
from .baremetal_engine import drop_session as baremetal_drop_session
from .baremetal_engine import get_state as baremetal_get_state
from .aws_engine import apply_action as aws_apply_action
from .aws_engine import drop_session as aws_drop_session
from .aws_engine import get_state as aws_get_state
from .azure_engine import apply_action as azure_apply_action
from .azure_engine import drop_session as azure_drop_session
from .azure_engine import get_state as azure_get_state
from .gcp_engine import apply_action as gcp_apply_action
from .gcp_engine import drop_session as gcp_drop_session
from .gcp_engine import get_state as gcp_get_state
from .openstack_engine import apply_action as openstack_apply_action
from .openstack_engine import drop_session as openstack_drop_session
from .openstack_engine import get_state as openstack_get_state
from .commvault_engine import apply_action as commvault_apply_action
from .commvault_engine import drop_session as commvault_drop_session
from .commvault_engine import get_state as commvault_get_state
from .netapp_engine import apply_action as netapp_apply_action
from .netapp_engine import drop_session as netapp_drop_session
from .netapp_engine import get_state as netapp_get_state
from .dellemc_engine import apply_action as dellemc_apply_action
from .dellemc_engine import drop_session as dellemc_drop_session
from .dellemc_engine import get_state as dellemc_get_state
from .datacenter_engine import apply_action as datacenter_apply_action
from .datacenter_engine import drop_session as datacenter_drop_session
from .datacenter_engine import get_state as datacenter_get_state
from .soc_engine import apply_action as soc_apply_action
from .soc_engine import drop_session as soc_drop_session
from .soc_engine import get_state as soc_get_state


def _demo_session_id(user) -> str:
    """Stable per-user key for standalone VMware console (no lab session)."""
    return f"demo-{user.pk}"


def _require_tech_access(request, technology_slug: str):
    """403 when the user lacks a subscription for a standalone console."""
    from apps.billing.subscription_utils import technology_access_denied_response

    return technology_access_denied_response(request.user, technology_slug)


def _require_session_console_access(request, session, technology_slug: str):
    """Allow session-scoped console only for that scenario's tech or a declared cross-tech link.

    Prevents a Linux-only subscriber from opening an unrelated VMware/AWS console
    by guessing another session id, while still allowing intentional cross-tech labs.

    Critical: ``cross_technology`` alone must NOT unlock VMware (or monitoring).
    Academy “integration” stamps set ``cross_technology`` widely; only explicit
    ``vmware_link`` / ``datacenter_link`` may surface companion consoles — and
    those still require a matching technology subscription (revenue protection).
    """
    scenario = getattr(session, "scenario", None)
    if scenario is None:
        return _require_tech_access(request, technology_slug)

    tech = getattr(scenario, "technology", None)
    scen_slug = (getattr(tech, "slug", None) or "").strip().lower()
    if scen_slug == technology_slug:
        return None
    sim_type = (getattr(scenario, "simulation_type", None) or "").strip().lower()
    if sim_type == technology_slug:
        return None
    # Monitoring family aliases (scenario tech or simulation_type).
    if technology_slug in ("grafana", "prometheus", "monitoring"):
        if scen_slug in ("grafana", "prometheus", "monitoring") or sim_type in (
            "grafana", "prometheus", "monitoring",
        ):
            return None

    # Opt-in companion consoles: scenario must declare the link AND the learner
    # must hold a subscription for that console technology.
    if technology_slug == "vmware" and bool(getattr(scenario, "vmware_link", False)):
        return _require_tech_access(request, "vmware")
    if technology_slug == "datacenter" and bool(getattr(scenario, "datacenter_link", False)):
        return _require_tech_access(request, "datacenter")

    # Session belongs to another technology — require a real subscription.
    return _require_tech_access(request, technology_slug)


def _session_console_or_deny(request, session_id, technology_slug: str, *, running_only: bool = False):
    """Load a lab session and enforce per-technology console entitlement."""
    qs = LabSession.objects.select_related("scenario", "scenario__technology").filter(
        pk=session_id, user=request.user,
    )
    if running_only:
        qs = qs.filter(status="RUNNING")
    session = qs.first()
    if not session:
        return None, Response(
            {"error": "Lab session not running" if running_only else "Session not found"},
            status=400 if running_only else 404,
        )
    denied = _require_session_console_access(request, session, technology_slug)
    if denied:
        return None, denied
    return session, None


def _require_any_tech_access(request, *technology_slugs: str):
    """Allow if the user has access to any of the listed technologies."""
    last = None
    for slug in technology_slugs:
        denied = _require_tech_access(request, slug)
        if denied is None:
            return None
        last = denied
    return last


# ---------------------------------------------------------------------------
# VMware views
# ---------------------------------------------------------------------------

class VMwareSimDemoStateView(APIView):
    """Standalone VMware console — no LabSession required (e.g. /vmware-sim)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        denied = _require_tech_access(request, "vmware")
        if denied:
            return denied
        slug = request.query_params.get("scenario", "") or ""
        sid = _demo_session_id(request.user)
        return Response(get_state(sid, slug))


class VMwareSimDemoActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        denied = _require_tech_access(request, "vmware")
        if denied:
            return denied
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
        denied = _require_session_console_access(request, session, "vmware")
        if denied:
            return denied
        # Prefer slug from DB; fall back to query param (e.g. when redirected from LabRunner)
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(get_state(session_id, slug))


class VMwareSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.select_related("scenario", "scenario__technology").filter(
            pk=session_id, user=request.user, status="RUNNING",
        ).first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        denied = _require_session_console_access(request, session, "vmware")
        if denied:
            return denied
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


# ---------------------------------------------------------------------------
# Monitoring views (Grafana + Prometheus simulator)
# ---------------------------------------------------------------------------

def _monitoring_demo_session_id(user) -> str:
    """Stable per-user key for standalone monitoring console (no lab session)."""
    return f"mon-demo-{user.pk}"


class MonitoringSimDemoStateView(APIView):
    """Standalone monitoring console — no LabSession required."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        denied = _require_any_tech_access(request, "grafana", "prometheus", "monitoring")
        if denied:
            return denied
        slug = request.query_params.get("scenario", "") or ""
        sid = _monitoring_demo_session_id(request.user)
        return Response(monitoring_get_state(sid, slug))


class MonitoringSimDemoActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        denied = _require_any_tech_access(request, "grafana", "prometheus", "monitoring")
        if denied:
            return denied
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        sid = _monitoring_demo_session_id(request.user)
        slug = request.data.get("scenario", "") or request.query_params.get("scenario", "") or ""
        monitoring_get_state(sid, slug)
        result = monitoring_apply_action(sid, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": monitoring_get_state(sid, slug)})


class MonitoringSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario", "scenario__technology").filter(
            pk=session_id, user=request.user,
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(monitoring_get_state(session_id, slug))


class MonitoringSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        monitoring_get_state(session_id, slug)
        result = monitoring_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": monitoring_get_state(session_id, slug)})


class MonitoringSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        monitoring_drop_session(session_id)
        return Response({"released": True})


# ---------------------------------------------------------------------------
# Nmap views (network scanning simulator)
# ---------------------------------------------------------------------------

class NmapSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario", "scenario__technology").filter(
            pk=session_id, user=request.user,
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(nmap_get_state(session_id, slug))


class NmapSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        # Ensure the simulation session is initialized in Redis before applying any action
        nmap_get_state(session_id, slug)
        result = nmap_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": nmap_get_state(session_id, slug)})


class NmapSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        nmap_drop_session(session_id)
        return Response({"released": True})


# ---------------------------------------------------------------------------
# Wireshark views (packet capture / analysis simulator)
# ---------------------------------------------------------------------------

class WiresharkSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario", "scenario__technology").filter(
            pk=session_id, user=request.user,
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(wireshark_get_state(session_id, slug))


class WiresharkSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        # Ensure the simulation session is initialized in Redis before applying any action
        wireshark_get_state(session_id, slug)
        result = wireshark_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": wireshark_get_state(session_id, slug)})


class WiresharkSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        wireshark_drop_session(session_id)
        return Response({"released": True})


# ---------------------------------------------------------------------------
# Data Science views (BI dashboard builder simulator)
# ---------------------------------------------------------------------------

class DatascienceSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario", "scenario__technology").filter(
            pk=session_id, user=request.user,
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(datascience_get_state(session_id, slug))


class DatascienceSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        # Ensure the simulation session is initialized in the cache before applying any action
        datascience_get_state(session_id, slug)
        result = datascience_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": datascience_get_state(session_id, slug)})


class DatascienceSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        datascience_drop_session(session_id)
        return Response({"released": True})


# ---------------------------------------------------------------------------
# AI / ML views (n8n-style agent / workflow simulator)
# ---------------------------------------------------------------------------

class AimlSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario", "scenario__technology").filter(
            pk=session_id, user=request.user,
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(aiml_get_state(session_id, slug))


class AimlSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        # Ensure the simulation session is initialized in the cache before applying any action
        aiml_get_state(session_id, slug)
        result = aiml_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": aiml_get_state(session_id, slug)})


class AimlSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        aiml_drop_session(session_id)
        return Response({"released": True})


# ---------------------------------------------------------------------------
# Windows Server views (Server Manager / AD / Windows Update GUI simulator)
# ---------------------------------------------------------------------------

class WindowsSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario", "scenario__technology").filter(
            pk=session_id, user=request.user,
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(windows_get_state(session_id, slug))


class WindowsSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        # Ensure the simulation session is initialized in the cache before applying any action
        windows_get_state(session_id, slug)
        result = windows_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": windows_get_state(session_id, slug)})


class WindowsSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        windows_drop_session(session_id)
        return Response({"released": True})


# ── PeopleSoft (D6) views — mirror the Windows non-demo pattern ───────────────
class PeoplesoftSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario", "scenario__technology").filter(
            pk=session_id, user=request.user,
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(peoplesoft_get_state(session_id, slug))


class PeoplesoftSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        peoplesoft_get_state(session_id, slug)
        result = peoplesoft_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": peoplesoft_get_state(session_id, slug)})


class PeoplesoftSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        peoplesoft_drop_session(session_id)
        return Response({"released": True})


# ── Ansible AWX / Tower simulator ─────────────────────────────────────────────
class AwxSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario").filter(pk=session_id, user=request.user).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else ""
        return Response(awx_get_state(session_id, slug))


class AwxSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        awx_get_state(session_id, slug)
        result = awx_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": awx_get_state(session_id, slug)})


class AwxSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        awx_drop_session(session_id)
        return Response({"released": True})


class CicdSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario").filter(pk=session_id, user=request.user).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(cicd_get_state(session_id, slug))


class CicdSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        cicd_get_state(session_id, slug)
        result = cicd_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": cicd_get_state(session_id, slug)})


class CicdSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        cicd_drop_session(session_id)
        return Response({"released": True})


# ── Terraform + AWS CLI simulator ─────────────────────────────────────────────
class TerraformSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario").filter(pk=session_id, user=request.user).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else ""
        return Response(terraform_get_state(session_id, slug))


class TerraformSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        terraform_get_state(session_id, slug)
        result = terraform_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": terraform_get_state(session_id, slug)})


class TerraformSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        terraform_drop_session(session_id)
        return Response({"released": True})


# ── MAAS / LXD / KVM bare-metal simulator ─────────────────────────────────────
class BaremetalSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario").filter(pk=session_id, user=request.user).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else ""
        return Response(baremetal_get_state(session_id, slug))


class BaremetalSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.filter(pk=session_id, user=request.user, status="RUNNING").first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        baremetal_get_state(session_id, slug)
        result = baremetal_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": baremetal_get_state(session_id, slug)})


class BaremetalSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        baremetal_drop_session(session_id)
        return Response({"released": True})


# ── AWS console simulator ─────────────────────────────────────────────────────
class AwsSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "aws")
        if err:
            return err
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(aws_get_state(session_id, slug))


class AwsSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "aws", running_only=True)
        if err:
            return err
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        aws_get_state(session_id, slug)

        # Bridge actions: the frontend AWS console can't reach the Linux lab
        # terminal directly, so these variants update aws_engine state AND
        # publish the intended end-state to the shared AWS/Linux bridge (see
        # apps.labs.provisioner.simulation.aws_bridge) for the terminal to reveal.
        if action == "bridge_attach_volume":
            return self._bridge_attach_volume(session_id, payload, slug)
        if action == "bridge_detach_volume":
            return self._bridge_detach_volume(session_id, payload, slug)
        if action == "bridge_power":
            return self._bridge_power(session_id, payload, slug)

        result = aws_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": aws_get_state(session_id, slug)})

    def _bridge_attach_volume(self, session_id, payload, slug):
        from apps.labs.provisioner.simulation import aws_bridge

        result = aws_apply_action(session_id, "attach_volume", payload)
        if not result.get("ok"):
            return Response(result, status=400)
        try:
            aws_bridge.record_volume_attach(
                str(session_id),
                result.get("volume_id") or payload.get("volume_id") or "",
                size_gb=int(payload.get("size_gb") or 20),
                device=result.get("device") or payload.get("device"),
                instance_id=payload.get("instance_id"),
            )
        except Exception:
            pass
        return Response({**result, "state": aws_get_state(session_id, slug)})

    def _bridge_detach_volume(self, session_id, payload, slug):
        from apps.labs.provisioner.simulation import aws_bridge

        result = aws_apply_action(session_id, "detach_volume", payload)
        if not result.get("ok"):
            return Response(result, status=400)
        try:
            aws_bridge.record_volume_detach(
                str(session_id),
                result.get("device") or payload.get("device") or "",
                instance_id=payload.get("instance_id"),
            )
        except Exception:
            pass
        return Response({**result, "state": aws_get_state(session_id, slug)})

    def _bridge_power(self, session_id, payload, slug):
        from apps.labs.provisioner.simulation import aws_bridge

        op = payload.get("op") or payload.get("action") or "start"
        result = aws_apply_action(session_id, "instance_action", {**payload, "op": op})
        if not result.get("ok"):
            return Response(result, status=400)
        try:
            aws_bridge.record_instance_power(str(session_id), op)
        except Exception:
            pass
        return Response({**result, "state": aws_get_state(session_id, slug)})


class AwsSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        aws_drop_session(session_id)
        return Response({"released": True})


# ── Azure Portal simulator ──────────────────────────────────────────────────
class AzureSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "azure")
        if err:
            return err
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(azure_get_state(session_id, slug))


class AzureSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "azure", running_only=True)
        if err:
            return err
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        result = azure_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": azure_get_state(session_id, slug)})


class AzureSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        azure_drop_session(session_id)
        return Response({"released": True})


# ── Commvault CommCell simulator ──────────────────────────────────────────────
class CommvaultSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "commvault")
        if err:
            return err
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(commvault_get_state(session_id, slug))


class CommvaultSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "commvault", running_only=True)
        if err:
            return err
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        commvault_get_state(session_id, slug)
        result = commvault_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": commvault_get_state(session_id, slug)})


class CommvaultSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        commvault_drop_session(session_id)
        return Response({"released": True})


# ── NetApp ONTAP System Manager simulator ─────────────────────────────────────
class NetappSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "netapp")
        if err:
            return err
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(netapp_get_state(session_id, slug))


class NetappSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "netapp", running_only=True)
        if err:
            return err
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        netapp_get_state(session_id, slug)
        result = netapp_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": netapp_get_state(session_id, slug)})


class NetappSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        netapp_drop_session(session_id)
        return Response({"released": True})


# ── Dell EMC Unisphere / PowerMax simulator ───────────────────────────────────
class DellemcSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "dellemc")
        if err:
            return err
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(dellemc_get_state(session_id, slug))


class DellemcSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "dellemc", running_only=True)
        if err:
            return err
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        dellemc_get_state(session_id, slug)
        result = dellemc_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": dellemc_get_state(session_id, slug)})


class DellemcSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        dellemc_drop_session(session_id)
        return Response({"released": True})


# ── Physical Datacenter (DCIM) simulator ──────────────────────────────────────
class ActiveFaultsView(APIView):
    """Cross-console fault ledger (Phase 3.2/3.4). Any lab session's open
    consoles can call this to answer "what is currently broken here" without
    each engine needing to know about every other engine — a VMware NIC drop,
    a Windows service stop, and a NetApp volume-near-full all show up here
    for the same session, with a correlating fault id and timestamp."""

    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        from apps.labs.provisioner.simulation.chaos_engine import list_faults

        active_only = request.query_params.get("active", "true").lower() != "false"
        return Response({"faults": list_faults(str(session_id), active_only=active_only)})


class GcpSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "gcp")
        if err:
            return err
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(gcp_get_state(session_id, slug))


class GcpSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "gcp", running_only=True)
        if err:
            return err
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        result = gcp_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": gcp_get_state(session_id, slug)})


class GcpSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        gcp_drop_session(session_id)
        return Response({"released": True})


# ── OpenStack Horizon ────────────────────────────────────────────────────────
class OpenStackSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "openstack")
        if err:
            return err
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(openstack_get_state(session_id, slug))


class OpenStackSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "openstack", running_only=True)
        if err:
            return err
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        result = openstack_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": openstack_get_state(session_id, slug)})


class OpenStackSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        openstack_drop_session(session_id)
        return Response({"released": True})


class DatacenterSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "datacenter")
        if err:
            return err
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(datacenter_get_state(session_id, slug))


class DatacenterSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "datacenter", running_only=True)
        if err:
            return err
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        datacenter_get_state(session_id, slug)
        result = datacenter_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": datacenter_get_state(session_id, slug)})


class DatacenterSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        datacenter_drop_session(session_id)
        return Response({"released": True})


# ── SOC / SIEM simulator (cybersecurity) ──────────────────────────────────────
class SocSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "soc")
        if err:
            return err
        slug = session.scenario.slug if session.scenario_id else (request.query_params.get("scenario", "") or "")
        return Response(soc_get_state(session_id, slug))


class SocSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session, err = _session_console_or_deny(request, session_id, "soc", running_only=True)
        if err:
            return err
        action = request.data.get("action", "")
        payload = request.data.get("payload") or {}
        slug = session.scenario.slug if session.scenario_id else ""
        soc_get_state(session_id, slug)
        result = soc_apply_action(session_id, action, payload)
        if not result.get("ok"):
            return Response(result, status=400)
        return Response({**result, "state": soc_get_state(session_id, slug)})


class SocSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        soc_drop_session(session_id)
        return Response({"released": True})
