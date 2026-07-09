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
    slug = (getattr(scenario, "slug", "") or "").lower()
    if "ssh-stop" in slug or "sshd-down" in slug:
        return [
            {
                "name": "primary",
                "role": "Server (console)",
                "container_id": resource_id,
                "ip": "10.0.0.10",
                "ssh_user": "root",
            },
            {
                "name": "ssh_client",
                "role": "SSH Client",
                "container_id": resource_id,
                "ip": "10.0.0.5",
                "ssh_user": "labuser",
                "ssh_targets": [{"name": "primary", "ip": "10.0.0.10", "user": "root"}],
            },
        ]
    if "firewalld-dual" in slug or "mysql-dual" in slug:
        role = "Database server" if "mysql" in slug else "Web server"
        return [
            {
                "name": "primary",
                "role": role,
                "container_id": resource_id,
                "ip": "10.0.0.10",
                "ssh_user": "root",
            },
            {
                "name": "ssh_client",
                "role": "SSH Client",
                "container_id": resource_id,
                "ip": "10.0.0.5",
                "ssh_user": "labuser",
                "ssh_targets": [{"name": "primary", "ip": "10.0.0.10", "user": "root"}],
            },
        ]
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
    """Append an SSH jump box so learners connect with ssh user@ip (realistic workflow)."""
    if any(h.get("name") == "ssh_client" for h in lab_hosts):
        return lab_hosts
    if not lab_hosts:
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


def _should_use_ssh_client_default(scenario, sim_type: str) -> bool:
    """True when the lab should open on the jump box instead of a root shell."""
    slug = (getattr(scenario, "slug", "") or "").lower()
    if sim_type in ("vmware", "windows", "coding", "prompt", "monitoring"):
        return False
    if any(k in slug for k in ("boot", "grub", "initramfs", "kernel-panic")):
        return False
    if "ssh-stop" in slug or "sshd-down" in slug:
        return False
    return True


def _wire_engine_hosts(engine, entry: dict) -> None:
    """Attach multi-host SSH map to primary shell."""
    hosts = entry.get("state", {}).get("hosts", {})
    host_ips = entry.get("state", {}).get("host_ips", {})
    engine.shell._host_ips = host_ips  # noqa: SLF001
    engine.shell._host_names = hosts  # noqa: SLF001
    engine.shell._engine = engine  # noqa: SLF001


def _apply_companion_host_state(shell, host_key: str, host_meta: dict, slug: str) -> None:
    ip = host_meta.get("ip")
    if ip:
        shell.state.set_host_ip(ip)
    low = slug.lower()
    if "ssh-stop" in low or "sshd-down" in low:
        if host_key == "primary" and "sshd" in shell.state.services:
            shell.state.services["sshd"].active = "inactive"
            shell.state.services["sshd"].sub_state = "dead"


def _apply_initial_host_state(engine, slug: str) -> None:
    low = (slug or "").lower()
    if "ssh-stop" in low or "sshd-down" in low:
        svc = engine.shell.state.services.get("sshd")
        if svc:
            svc.active = "inactive"
            svc.sub_state = "dead"
    if "mysql-dual" in low or ("mysql" in low and "dual" in low):
        from .simulation.scenario_presets import _preset_mysql_down
        _preset_mysql_down(engine.shell.state)
    if "firewalld-dual" in low or ("firewalld" in low and "dual" in low):
        from .simulation.scenario_presets import _preset_firewalld_blocked
        _preset_firewalld_blocked(engine.shell.state)


def ensure_sim_session(lab_session) -> dict | None:
    """Re-register in-memory simulation state after worker restart."""
    session_id = str(lab_session.id)
    existing = get_sim_session(session_id)
    if existing:
        return existing

    scenario = lab_session.scenario
    resource_id = lab_session.container_id or lab_session.instance_id
    if not resource_id or not scenario:
        return None

    raw_type = getattr(scenario, "simulation_type", "generic") or "generic"
    sim_type = normalize_sim_type(raw_type)
    slug = scenario.slug
    snapshot = getattr(lab_session, "simulation_snapshot", None) or {}
    if snapshot and snapshot.get("version") == 1:
        from .simulation.sim_persistence import restore_engine
        restored = restore_engine(snapshot)
        if restored:
            engine = restored
        else:
            engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type)
            _apply_initial_host_state(engine, slug)
    else:
        engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type)
        _apply_initial_host_state(engine, slug)
    lab_hosts = lab_session.lab_hosts or _build_lab_hosts(scenario, resource_id, sim_type)
    if _should_use_ssh_client_default(scenario, sim_type):
        lab_hosts = _attach_ssh_client_host(lab_hosts, resource_id)
    elif len(lab_hosts) >= 2 and not any(h.get("name") == "ssh_client" for h in lab_hosts):
        lab_hosts = _attach_ssh_client_host(lab_hosts, resource_id)

    if lab_hosts != (lab_session.lab_hosts or []):
        lab_session.lab_hosts = lab_hosts
        lab_session.save(update_fields=["lab_hosts"])

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
    entry = get_sim_session(session_id)
    if entry:
        _wire_engine_hosts(engine, entry)
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
        _apply_initial_host_state(engine, slug)
        resource_id = f"sim-{uuid.uuid4().hex[:12]}"

        lab_hosts = _build_lab_hosts(scenario, resource_id, sim_type)
        if _should_use_ssh_client_default(scenario, sim_type):
            lab_hosts = _attach_ssh_client_host(lab_hosts, resource_id)
        elif len(lab_hosts) >= 2:
            lab_hosts = _attach_ssh_client_host(lab_hosts, resource_id)
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
        entry = get_sim_session(str(lab_session.id))
        if entry:
            _wire_engine_hosts(engine, entry)

        if "vmware" in slug.lower() or raw_type == "vmware":
            from apps.vmware_sim.engine import _ensure_session
            _ensure_session(str(lab_session.id), slug)

        if slug.lower().startswith("ds-dashboard-") or raw_type == "data-dashboard":
            from apps.vmware_sim.datascience_engine import _ensure_session as _ensure_ds_session
            _ensure_ds_session(str(lab_session.id), slug)

        logger.info("Simulation lab %s persona=%s resource=%s", lab_session.id, sim_type, resource_id)
        return resource_id, f"sim-{slug}"

    def _setup_ssh_client_shell(self, engine, entry, hostname: str = "ssh-client") -> RHELShell:
        cached = entry.get("state", {}).get("ssh_client_shell")
        if isinstance(cached, RHELShell):
            return cached
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
        entry.setdefault("state", {})["ssh_client_shell"] = shell
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
            cached = entry.get("state", {}).get("ssh_client_shell")
            shell = cached if isinstance(cached, RHELShell) else self._setup_ssh_client_shell(engine, entry)
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
            host_meta = entry["state"].get("hosts", {}).get(hk, {})
            companion_state = engine.state.clone_for_host(hostname)
            shell = RHELShell(
                state=companion_state,
                scenario_slug=entry["state"].get("scenario_slug", ""),
                hostname=hostname,
            )
            shell._host_ips = entry["state"].get("host_ips", {})
            shell._host_names = entry["state"].get("hosts", {})
            shell._engine = engine
            _apply_companion_host_state(shell, hk, host_meta, entry["state"].get("scenario_slug", ""))
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
            _wire_engine_hosts(engine, entry)
            holder = engine.create_stream()

        entry.setdefault("streams", {})[stream_key] = holder
        holder._stream_key = stream_key
        return holder.exec_id, holder

    def execute_command(self, resource_id, command):
        if "check.sh" in (command or ""):
            return 127, "simulation: use validation_script"
        entry = get_sim_session_by_resource(resource_id)
        if not entry:
            from apps.labs.models import LabSession
            try:
                lab_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                entry = ensure_sim_session(lab_session)
            except LabSession.DoesNotExist:
                return 1, "simulation session not found"
        engine = entry.get("state", {}).get("engine") if entry else None
        if not engine:
            return 1, "simulation engine not ready"
        from .simulation.rhel_shell import RHELShell
        from .simulation.simulation_modules import register_modules
        shell = RHELShell(
            state=engine.shell.state,
            scenario_slug=entry["state"].get("scenario_slug", ""),
            hostname=engine.shell.state.hostname,
        )
        shell._engine = engine
        register_modules(engine, shell)
        cmd = (command or "").strip()
        if not cmd or cmd.startswith("#"):
            return 1, "no command to run"
        out = shell.run(cmd) or ""
        code = getattr(shell.state, "last_exit_code", 0)
        return code, out

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
        sim_type = (entry.get("state", {}).get("simulation_type", "") if entry else "") or ""
        low_slug = (slug or "").lower()
        if "vmware" in low_slug:
            from apps.labs.models import LabSession
            from apps.vmware_sim.engine import validate_vmware_lab, _ensure_session
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                _ensure_session(str(lab_session.id), slug)
                return validate_vmware_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "VMware simulation session not found"
        if low_slug.startswith("nmap-") or sim_type == "nmap":
            from apps.labs.models import LabSession
            from apps.vmware_sim.nmap_engine import validate_nmap_lab, _ensure_session
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                _ensure_session(str(lab_session.id), slug)
                return validate_nmap_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "Nmap simulation session not found"
        if low_slug.startswith("wireshark-") or sim_type == "wireshark":
            from apps.labs.models import LabSession
            from apps.vmware_sim.wireshark_engine import validate_wireshark_lab, _ensure_session
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                _ensure_session(str(lab_session.id), slug)
                return validate_wireshark_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "Wireshark simulation session not found"
        # ai-agent normalizes to "generic", so gate on the slug prefix OR the RAW
        # (pre-normalize) simulation_type. Read the raw type off the scenario when
        # the cached entry doesn't carry it (e.g. after a worker restart).
        _raw_agent_type = sim_type
        if not _raw_agent_type or _raw_agent_type == "generic":
            from apps.labs.models import LabSession
            try:
                _agent_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                _raw_agent_type = (getattr(_agent_session.scenario, "simulation_type", "") or "")
            except LabSession.DoesNotExist:
                _raw_agent_type = ""
        if low_slug.startswith("agent-") or _raw_agent_type == "ai-agent":
            from apps.labs.models import LabSession
            from apps.vmware_sim.aiml_engine import validate_aiml_lab, _ensure_session
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                _ensure_session(str(lab_session.id), slug)
                return validate_aiml_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "Agent simulation session not found"
        # windows-server normalizes to "generic", so gate on the slug prefix
        # (win-gui-, reliable) OR the RAW (pre-normalize) simulation_type read off
        # the scenario when the cached entry doesn't carry it (e.g. worker restart).
        _raw_win_type = sim_type
        if not _raw_win_type or _raw_win_type == "generic":
            from apps.labs.models import LabSession
            try:
                _win_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                _raw_win_type = (getattr(_win_session.scenario, "simulation_type", "") or "")
            except LabSession.DoesNotExist:
                _raw_win_type = ""
        if low_slug.startswith("win-gui-") or _raw_win_type == "windows-server":
            from apps.labs.models import LabSession
            from apps.vmware_sim.windows_engine import validate_windows_lab, _ensure_session
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                _ensure_session(str(lab_session.id), slug)
                return validate_windows_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "Windows Server simulation session not found"
        # peoplesoft normalizes to "generic"; gate on the slug prefix (ps-, reliable)
        # OR the RAW (pre-normalize) simulation_type read off the scenario.
        _raw_ps_type = sim_type
        if not _raw_ps_type or _raw_ps_type == "generic":
            from apps.labs.models import LabSession
            try:
                _ps_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                _raw_ps_type = (getattr(_ps_session.scenario, "simulation_type", "") or "")
            except LabSession.DoesNotExist:
                _raw_ps_type = ""
        if low_slug.startswith("ps-") or _raw_ps_type == "peoplesoft":
            from apps.labs.models import LabSession
            from apps.vmware_sim.peoplesoft_engine import validate_peoplesoft_lab, _ensure_session
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                _ensure_session(str(lab_session.id), slug)
                return validate_peoplesoft_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "PeopleSoft simulation session not found"
        # data-dashboard normalizes to "generic", so gate on the slug prefix OR the
        # RAW (pre-normalize) simulation_type read off the scenario.
        if low_slug.startswith("ds-dashboard-"):
            from apps.labs.models import LabSession
            from apps.vmware_sim.datascience_engine import validate_datascience_lab, _ensure_session
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                _ensure_session(str(lab_session.id), slug)
                return validate_datascience_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "Data dashboard simulation session not found"
        from apps.labs.models import LabSession
        try:
            _ds_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
            _raw_sim_type = (getattr(_ds_session.scenario, "simulation_type", "") or "")
        except LabSession.DoesNotExist:
            _ds_session = None
            _raw_sim_type = ""
        if _raw_sim_type == "data-dashboard" and _ds_session is not None:
            from apps.vmware_sim.datascience_engine import validate_datascience_lab, _ensure_session
            _ensure_session(str(_ds_session.id), slug)
            return validate_datascience_lab(str(_ds_session.id), slug)
        _raw_awx_type = sim_type
        if not _raw_awx_type or _raw_awx_type == "generic":
            from apps.labs.models import LabSession
            try:
                _awx_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                _raw_awx_type = (getattr(_awx_session.scenario, "simulation_type", "") or "")
            except LabSession.DoesNotExist:
                _raw_awx_type = ""
        if "awx" in low_slug or "tower" in low_slug or _raw_awx_type == "ansible-awx":
            from apps.labs.models import LabSession
            from apps.vmware_sim.awx_engine import validate_awx_lab, _ensure as awx_ensure
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                awx_ensure(str(lab_session.id), slug)
                return validate_awx_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "AWX simulation session not found"
        _raw_tf_type = sim_type
        if not _raw_tf_type or _raw_tf_type == "generic":
            from apps.labs.models import LabSession
            try:
                _tf_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                _raw_tf_type = (getattr(_tf_session.scenario, "simulation_type", "") or "")
            except LabSession.DoesNotExist:
                _raw_tf_type = ""
        if _raw_tf_type == "terraform" or low_slug.startswith("terraform-"):
            from apps.labs.models import LabSession
            from apps.vmware_sim.terraform_engine import validate_terraform_lab, _ensure as tf_ensure
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                tf_ensure(str(lab_session.id), slug)
                return validate_terraform_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "IaC simulation session not found"
        _raw_bm_type = sim_type
        if not _raw_bm_type or _raw_bm_type == "generic":
            from apps.labs.models import LabSession
            try:
                _bm_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                _raw_bm_type = (getattr(_bm_session.scenario, "simulation_type", "") or "")
            except LabSession.DoesNotExist:
                _raw_bm_type = ""
        if _raw_bm_type == "baremetal" and any(k in low_slug for k in ("maas", "lxd", "lxc", "kvm", "virsh", "ipmi")):
            from apps.labs.models import LabSession
            from apps.vmware_sim.baremetal_engine import validate_baremetal_lab, _ensure as bm_ensure
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                bm_ensure(str(lab_session.id), slug)
                return validate_baremetal_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "Bare metal simulation session not found"
        script = resolve_simulation_validation_script(slug, validation_script or "")
        if engine and hasattr(engine, "state"):
            return validate_simulation_state(engine.state, script, engine=engine)
        if not script or is_trivial_validation_script(script):
            return False, "NO_VALIDATION_SCRIPT"
        return False, "Simulation session not found"

    def get_status(self, resource_id):
        if get_sim_session_by_resource(resource_id):
            return "running"
        from apps.labs.models import LabSession
        try:
            lab_session = LabSession.objects.get(container_id=resource_id, status="RUNNING")
            if ensure_sim_session(lab_session):
                return "running"
        except LabSession.DoesNotExist:
            pass
        return "stopped"

    def terminate(self, resource_id, session_id=None):
        if session_id:
            drop_sim_session(str(session_id))
        return True

    def terminate_lab(self, session):
        try:
            from apps.vmware_sim import terraform_engine as te

            te.clear_session(str(session.id))
        except Exception:  # noqa: BLE001
            pass
        drop_sim_session(str(session.id))
