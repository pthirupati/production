"""Simulation provisioner — single unified engine for all simulation labs."""

from __future__ import annotations

import logging
import uuid

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
from .simulation.validation import validate_simulation_state

logger = logging.getLogger(__name__)


class SimulationProvisioner:
    """Provisioner for lab_mode=simulation — one engine, scenario-driven behavior."""

    def provision(self, lab_session):
        scenario = lab_session.scenario
        raw_type = getattr(scenario, "simulation_type", "generic") or "generic"
        sim_type = normalize_sim_type(raw_type)
        slug = scenario.slug

        engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type)
        resource_id = f"sim-{uuid.uuid4().hex[:12]}"

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

        register_sim_session(
            str(lab_session.id),
            resource_id,
            sim_type,
            {
                "engine": engine,
                "scenario_slug": slug,
                "simulation_type": sim_type,
                "hosts": {h["name"]: h for h in lab_hosts},
                "validation_marker": f"/opt/fixitlab/sim-valid-{slug}",
            },
        )

        lab_session.lab_hosts = lab_hosts
        lab_session.save(update_fields=["lab_hosts"])

        logger.info("Simulation lab %s persona=%s resource=%s", lab_session.id, sim_type, resource_id)
        return resource_id, f"sim-{slug}"

    def create_exec_stream(self, resource_id, session_key: str = "", host_key: str = "primary"):
        entry = get_sim_session(session_key)
        if not entry:
            raise RuntimeError(f"Simulation session {session_key} not found")

        engine = entry["state"]["engine"]
        hk = host_key or "primary"
        stream_key = f"{session_key}:{hk}"

        if hk not in ("primary", "") and hk != "primary":
            hostname = hk
            companion_state = engine.state.clone_for_host(hostname)
            shell = RHELShell(
                state=companion_state,
                scenario_slug=entry["state"].get("scenario_slug", ""),
                hostname=hostname,
            )
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
        return holder.exec_id, holder

    def execute_command(self, resource_id, command):
        if "check.sh" in (command or ""):
            return 127, "simulation: use validation_script"
        return 0, f"[simulation] {command}"

    def run_validation(self, resource_id, validation_script):
        entry = get_sim_session_by_resource(resource_id)
        engine = entry.get("state", {}).get("engine") if entry else None
        if engine and hasattr(engine, "state"):
            return validate_simulation_state(engine.state, validation_script)
        script = (validation_script or "").strip()
        if not script:
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
