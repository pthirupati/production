"""Simulation provisioner — single unified engine for all simulation labs."""

from __future__ import annotations

import logging
import uuid

from .simulation.rhel_os import SimUser
from .simulation.rhel_shell import RHELShell
from .simulation.shell import (
    SimulationStreamHolder,
    drop_sim_session,
    get_sim_session,
    get_sim_session_by_resource,
    register_sim_session,
)
from .simulation.sim_types import normalize_sim_type
from .simulation.simulation_modules import register_modules
from .simulation.unified_sim import UnifiedSimulationEngine
from .simulation.validation import (
    validate_simulation_state,
    resolve_simulation_validation_script,
    is_trivial_validation_script,
)

logger = logging.getLogger(__name__)


def _build_lab_hosts(scenario, resource_id: str, sim_type: str) -> list[dict]:
    lab_hosts = []
    if sim_type == "ansible" or getattr(scenario, "requires_companion_hosts", False):
        if sim_type == "ansible":
            lab_hosts = [
                {"name": "primary", "role": "control", "container_id": resource_id, "ip": "10.0.0.10", "ssh_user": "ansible"},
                {"name": "web1", "role": "client", "container_id": f"{resource_id}-web1", "ip": "10.0.0.11", "ssh_user": "root"},
                {"name": "web2", "role": "client", "container_id": f"{resource_id}-web2", "ip": "10.0.0.12", "ssh_user": "root"},
            ]
        else:
            lab_hosts = [
                {"name": "primary", "role": "server-a", "container_id": resource_id, "ip": "10.0.0.10", "ssh_user": "root"},
                {"name": "companion", "role": "server-b", "container_id": f"{resource_id}-companion", "ip": "10.0.0.11", "ssh_user": "root"},
            ]
    if not lab_hosts:
        lab_hosts = [{
            "name": "primary",
            "role": "Primary",
            "container_id": resource_id,
            "ip": "10.0.0.10",
            "ssh_user": "root",
        }]
    return lab_hosts


def _attach_ssh_client_host(lab_hosts: list[dict], resource_id: str) -> list[dict]:
    if len(lab_hosts) < 2:
        return lab_hosts
    hosts = list(lab_hosts)
    hosts.append({
        "name": "ssh_client",
        "role": "SSH Client",
        "container_id": resource_id,
        "ip": "10.0.0.5",
        "ssh_user": "labuser",
        "ssh_targets": [
            {"name": h["name"], "ip": h.get("ip", ""), "user": h.get("ssh_user", "root")}
            for h in hosts if h.get("name") not in ("primary", "ssh_client") and h.get("ip")
        ],
    })
    return hosts


def ensure_sim_session(lab_session) -> dict | None:
    """Re-register in-memory simulation state after worker restart."""
    session_id = str(lab_session.id)
    existing = get_sim_session(session_id)
    if existing:
        return existing

    scenario = lab_session.scenario
    resource_id = lab_session.container_id
    if not resource_id or not scenario:
        return None

    raw_type = getattr(scenario, "simulation_type", "generic") or "generic"
    sim_type = normalize_sim_type(raw_type)
    slug = scenario.slug
    engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type)
    lab_hosts = lab_session.lab_hosts or _build_lab_hosts(scenario, resource_id, sim_type)
    if len(lab_hosts) >= 2 and not any(h.get("name") == "ssh_client" for h in lab_hosts):
        lab_hosts = _attach_ssh_client_host(lab_hosts, resource_id)

    register_sim_session(
        session_id,
        resource_id,
        sim_type,
        {
            "engine": engine,
            "scenario_slug": slug,
            "simulation_type": sim_type,
            "hosts": {h["name"]: h for h in lab_hosts},
            "host_ips": {h.get("ip", ""): h["name"] for h in lab_hosts if h.get("ip")},
            "validation_marker": f"/opt/fixitlab/sim-valid-{slug}",
        },
    )
    logger.info("Rehydrated simulation session %s resource=%s", session_id, resource_id)
    return get_sim_session(session_id)


def evict_sim_stream(session_key: str, host_key: str = "primary", stream_key: str | None = None) -> None:
    """Remove one simulation stream (or all for host when stream_key omitted)."""
    entry = get_sim_session(session_key)
    if not entry:
        return
    streams = entry.get("streams") or {}
    if stream_key:
        holder = streams.pop(stream_key, None)
        if holder:
            try:
                holder.close()
            except Exception:
                pass
        return
    prefix = f"{session_key}:{host_key or 'primary'}"
    for key in list(streams.keys()):
        if key == prefix or key.startswith(f"{prefix}:"):
            holder = streams.pop(key)
            try:
                holder.close()
            except Exception:
                pass


class SimulationProvisioner:
    """Provisioner for lab_mode=simulation — one engine, scenario-driven behavior."""

    def provision(self, lab_session):
        scenario = lab_session.scenario
        raw_type = getattr(scenario, "simulation_type", "generic") or "generic"
        sim_type = normalize_sim_type(raw_type)
        slug = scenario.slug

        engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type)
        resource_id = f"sim-{uuid.uuid4().hex[:12]}"

        lab_hosts = _build_lab_hosts(scenario, resource_id, sim_type)
        lab_session.lab_hosts = lab_hosts
        lab_session.save(update_fields=["lab_hosts"])

        if len(lab_hosts) >= 2:
            lab_hosts = _attach_ssh_client_host(list(lab_session.lab_hosts or []), resource_id)
            lab_session.lab_hosts = lab_hosts
            lab_session.save(update_fields=["lab_hosts"])

        register_sim_session(
            str(lab_session.id),
            resource_id,
            sim_type,
            {
                "engine": engine,
                "scenario_slug": slug,
                "simulation_type": sim_type,
                "hosts": {h["name"]: h for h in lab_hosts},
                "host_ips": {h.get("ip", ""): h["name"] for h in lab_hosts if h.get("ip")},
                "validation_marker": f"/opt/fixitlab/sim-valid-{slug}",
            },
        )

        logger.info("Simulation lab %s persona=%s resource=%s", lab_session.id, sim_type, resource_id)
        return resource_id, f"sim-{slug}"

    def _setup_ssh_client_shell(self, engine, entry, hostname: str = "ssh-client") -> RHELShell:
        client_state = engine.state.clone_for_host(hostname)
        if "labuser" not in client_state.users:
            client_state.users["labuser"] = SimUser(
                "labuser", 1002, 1002, "/home/labuser", "/bin/bash", "Lab SSH User",
            )
        client_state._mkdir("/home/labuser")
        client_state._mkdir("/home/labuser/.ssh")
        client_state._write_file(
            "/home/labuser/.ssh/id_rsa",
            "-----BEGIN OPENSSH PRIVATE KEY-----\n(simulated-key)\n-----END OPENSSH PRIVATE KEY-----\n",
        )
        client_state.set_prompt_user("labuser")
        shell = RHELShell(
            state=client_state,
            scenario_slug=entry["state"].get("scenario_slug", ""),
            hostname=hostname,
        )
        shell._host_ips = entry["state"].get("host_ips", {})
        shell._host_names = entry["state"].get("hosts", {})
        shell._engine = entry["state"]["engine"]
        register_modules(entry["state"]["engine"], shell)
        return shell

    def create_exec_stream(self, resource_id, session_key: str = "", host_key: str = "primary"):
        from apps.labs.models import LabSession

        entry = get_sim_session(session_key)
        if not entry:
            try:
                lab_session = LabSession.objects.select_related("scenario").get(id=session_key)
            except LabSession.DoesNotExist:
                raise RuntimeError(f"Simulation session {session_key} not found")
            entry = ensure_sim_session(lab_session)
            if not entry:
                raise RuntimeError(f"Simulation session {session_key} not found")

        engine = entry["state"]["engine"]
        hk = host_key or "primary"
        stream_key = f"{session_key}:{hk}:{uuid.uuid4().hex[:8]}"

        if hk == "ssh_client":
            shell = self._setup_ssh_client_shell(engine, entry)
            holder = SimulationStreamHolder(
                shell.run,
                prompt=shell.prompt,
                dynamic_prompt=lambda: shell.prompt,
            )
            entry.setdefault("streams", {})[stream_key] = holder
            holder._stream_key = stream_key
            return holder.exec_id, holder

        if hk not in ("primary", "") and hk != "primary":
            hostname = hk
            companion_state = engine.state.clone_for_host(hostname)
            shell = RHELShell(
                state=companion_state,
                scenario_slug=entry["state"].get("scenario_slug", ""),
                hostname=hostname,
            )
            shell._host_ips = entry["state"].get("host_ips", {})
            shell._host_names = entry["state"].get("hosts", {})
            shell._engine = engine
            register_modules(engine, shell)

            def get_ed():
                return shell.state.editor

            def save_ed(path, content):
                shell.state.write_file(path, content)
                shell.state.editor = None

            def clear_ed():
                shell.state.editor = None

            holder = SimulationStreamHolder(
                shell.run,
                prompt=shell.prompt,
                dynamic_prompt=lambda: shell.prompt,
                get_editor_state=get_ed,
                save_editor=save_ed,
                clear_editor=clear_ed,
            )
        else:
            holder = engine.create_stream()

        entry.setdefault("streams", {})[stream_key] = holder
        holder._stream_key = stream_key
        return holder.exec_id, holder

    def execute_command(self, resource_id, command):
        if "check.sh" in (command or ""):
            return 127, "simulation: use validation_script"
        return 0, f"[simulation] {command}"

    def run_validation(self, resource_id, validation_script, scenario_slug: str = ""):
        entry = get_sim_session_by_resource(resource_id)
        if not entry:
            from apps.labs.models import LabSession
            try:
                lab_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                entry = ensure_sim_session(lab_session)
            except LabSession.DoesNotExist:
                entry = None
        engine = entry.get("state", {}).get("engine") if entry else None
        slug = scenario_slug or (entry.get("state", {}).get("scenario_slug", "") if entry else "")
        script = resolve_simulation_validation_script(slug, validation_script or "")
        if engine and hasattr(engine, "state"):
            return validate_simulation_state(engine.state, script, engine=engine)
        if not script or is_trivial_validation_script(script):
            return False, "NO_VALIDATION_SCRIPT"
        return False, "Simulation session not found"

    def get_status(self, resource_id):
        if get_sim_session_by_resource(resource_id):
            return "running"
        return "stopped"

    def terminate(self, resource_id, session_id=None):
        if session_id:
            drop_sim_session(str(session_id))
        return True

    def terminate_lab(self, session):
        drop_sim_session(str(session.id))
