"""VyOS ops dashboard API — thin companion to Lab Terminal CLI."""

from __future__ import annotations

import json

from django.core.cache import cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.labs.models import LabSession
from apps.labs.provisioner.simulation.networking_state import NetworkingState

SESSION_TTL = 60 * 60 * 6  # 6 hours


def _cache_key(session_id) -> str:
    return f"vyos_net:{session_id}"


def load_networking(session_id, scenario_slug: str = "") -> NetworkingState:
    raw = cache.get(_cache_key(session_id))
    if raw:
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, dict):
                return NetworkingState.from_dict(data)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    net = NetworkingState(scenario_slug or "")
    save_networking(session_id, net)
    return net


def save_networking(session_id, net: NetworkingState) -> None:
    cache.set(_cache_key(str(session_id)), json.dumps(net.to_dict(), default=str), SESSION_TTL)


def drop_networking(session_id) -> None:
    cache.delete(_cache_key(str(session_id)))


def apply_cli_line(net: NetworkingState, line: str, shell_state=None) -> str:
    """Apply a single VyOS-style CLI line against NetworkingState."""
    line = (line or "").strip()
    if not line:
        return ""
    low = line.lower()
    if shell_state is not None:
        net.bind_shell(shell_state)

    if low == "configure" or low.startswith("configure "):
        return net.vyos_enter_configure()
    if low == "exit" and net.vyos_configure_mode:
        return net.vyos_exit_configure()
    if low in ("discard",) or low.startswith("discard "):
        return net.vyos_discard()
    if low == "compare" or low.startswith("compare"):
        return net.vyos_compare()
    if low.startswith("show system commit"):
        return net.vyos_show_history()
    if low.startswith("commit-confirm"):
        parts = line.split()
        minutes = 10
        if len(parts) > 1 and parts[1].isdigit():
            minutes = int(parts[1])
        return net.vyos_commit_confirm(minutes)
    if low == "confirm" or low.startswith("confirm "):
        return net.vyos_confirm()
    if low == "commit" or low.startswith("commit "):
        return net.vyos_commit()
    if low.startswith("rollback"):
        parts_r = line.split()
        steps = 1
        if len(parts_r) > 1 and parts_r[1].lstrip("-").isdigit():
            steps = abs(int(parts_r[1]))
        return net.vyos_rollback(steps)
    if low == "save" or low.startswith("save "):
        return net.vyos_save(shell_state)
    if low == "load" or low.startswith("load "):
        return net.vyos_load(shell_state)
    if low.startswith("set "):
        return net.vyos_set(line[4:].strip())
    if low.startswith("delete "):
        return net.vyos_delete(line[7:].strip())
    if low.startswith("edit "):
        return net.vyos_edit(line[5:].strip())
    if low == "edit":
        return net.vyos_edit("")
    if low == "up":
        return net.vyos_up()
    if low == "top":
        return net.vyos_top()
    if low in ("show", "show ") or low == "show pending" or "show pending" in low:
        return net.vyos_show_pending()
    if "show conf" in low or "configuration" in low:
        cand = "candidate" in low or net.vyos_configure_mode
        return net.vyos_show_config(candidate=cand)
    if "show ip bgp" in low or "bgp summary" in low or "show protocols bgp" in low:
        return net.show_ip_bgp_summary()
    if "show ip route" in low:
        return net.show_ip_route()
    if "show interfaces" in low:
        return net.show_interfaces()
    if "show vrrp" in low or "show high-availability" in low:
        return net.show_vrrp()
    if "show nat" in low:
        return net.show_nat()
    if "show firewall" in low:
        return net.show_firewall()
    if "show dhcp" in low:
        return net.show_dhcp_leases()
    if "show version" in low:
        return net.show_version()
    return f"Invalid command: {line}"


class VyosSimStateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        session = LabSession.objects.select_related("scenario").filter(
            pk=session_id, user=request.user
        ).first()
        if not session:
            return Response({"error": "Session not found"}, status=404)
        slug = session.scenario.slug if session.scenario_id else (
            request.query_params.get("scenario", "") or ""
        )
        net = load_networking(session_id, slug)
        dash = net.to_dashboard()
        save_networking(session_id, net)  # persist any auto-rollback side effects
        return Response({"ok": True, "dashboard": dash, "state": net.to_dict()})


class VyosSimActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = LabSession.objects.select_related("scenario").filter(
            pk=session_id, user=request.user, status="RUNNING"
        ).first()
        if not session:
            return Response({"error": "Lab session not running"}, status=400)
        slug = session.scenario.slug if session.scenario_id else ""
        net = load_networking(session_id, slug)
        action = (request.data.get("action") or "").strip().lower()
        payload = request.data.get("payload") or {}
        output = ""
        if action in ("cli", "apply_cli_line", "run"):
            line = payload.get("line") or payload.get("command") or request.data.get("line") or ""
            output = apply_cli_line(net, line)
        elif action == "get_state":
            pass
        elif action == "reset":
            net = NetworkingState(slug)
        else:
            return Response({"ok": False, "error": f"Unknown action: {action}"}, status=400)
        save_networking(session_id, net)
        return Response({
            "ok": True,
            "output": output,
            "dashboard": net.to_dashboard(),
            "state": net.to_dict(),
        })


class VyosSimReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        if not LabSession.objects.filter(pk=session_id, user=request.user).exists():
            return Response({"error": "Session not found"}, status=404)
        drop_networking(session_id)
        return Response({"released": True})
