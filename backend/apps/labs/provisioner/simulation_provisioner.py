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


def _is_vmware_lab(slug: str, raw_type: str) -> bool:
    return raw_type == "vmware" or "vmware" in (slug or "").lower()


def _seed_state_from_vmware_vm(engine, session_id, slug: str) -> None:
    """Unified-server model: seed the backend RHEL shell so it IS the VMware VM
    the learner sees — same hostname, IP, CPU and RAM. That way the VM's console
    and the lab terminal are one server (hardware/reboots already bridge across).

    VMware-only and best-effort: any failure is logged and swallowed so it can
    never break provisioning of a lab. Pure-Linux labs never call this.
    """
    try:
        from apps.vmware_sim.engine import get_state, _ensure_session
        from apps.labs.provisioner.simulation.vmware_bridge import cross_tech_config

        sid = str(session_id)
        _ensure_session(sid, slug)
        inv = (get_state(sid, slug) or {}).get("inventory", {}) or {}
        vms = inv.get("vms") or []
        if not vms:
            return
        # Pick the VM this terminal represents: a cross-tech-pinned VM first, then
        # the graded target, then the first VM in the inventory.
        pin = (cross_tech_config(slug) or {}).get("vmware_vm")
        target = (inv.get("validation", {}) or {}).get("target_vm")
        vm = None
        for want in (pin, target):
            if want:
                vm = next((v for v in vms if v.get("name") == want), None)
                if vm:
                    break
        if vm is None:
            vm = vms[0]

        state = engine.shell.state
        host = vm.get("hostname") or vm.get("name")
        if host:
            state.set_hostname(host)
        state.set_hardware(cpu=vm.get("cpu"), mem_mb=vm.get("memory_mb"))
        ip = vm.get("ip")
        if ip:
            state.set_host_ip(ip)
        try:
            from .simulation.server_identity import seed_from_vmware_vm
            seed_from_vmware_vm(sid, vm, role="primary")
        except Exception:
            logger.exception("ServerIdentity VMware seed skipped for session %s", session_id)
    except Exception:
        logger.exception("VMware VM seed skipped for session %s", session_id)


_EC2_TYPE_HW = {
    "t2.micro": (1, 1024),
    "t2.small": (1, 2048),
    "t3.micro": (2, 1024),
    "t3.small": (2, 2048),
    "t3.medium": (2, 4096),
    "t3.large": (2, 8192),
    "m5.large": (2, 8192),
    "m5.xlarge": (4, 16384),
}


def _seed_hostname_for_persona(engine, slug: str, raw_type: str) -> None:
    """Light-touch hostname seed for personas with no dedicated seed function.

    Best-effort: gives the AWX / monitoring lab terminal a hostname matching
    the console it is paired with (control-node / monitoring-node style)
    instead of the generic rhel-sim default, without changing CPU/RAM/IP.
    """
    low = (slug or "").lower()
    try:
        if "awx" in low or "tower" in low or raw_type == "ansible-awx":
            engine.shell.state.set_hostname("ansible-control")
        elif raw_type in ("monitoring", "grafana", "prometheus") or low.startswith(
            ("monitoring-", "grafana-", "prometheus-", "promql-", "alertmanager-", "loki-")
        ):
            engine.shell.state.set_hostname("monitoring-node")
    except Exception:
        logger.exception("Hostname seed skipped for slug %s", slug)


def _is_aws_lab(slug: str, raw_type: str) -> bool:
    low = (slug or "").lower()
    return (raw_type or "").lower() == "aws" or low.startswith(
        ("aws-", "ec2-", "s3-", "iam-", "academy-aws-")
    )


def _seed_state_from_aws_ec2(engine, session_id, slug: str) -> None:
    """Unified-server model (AWS): seed the lab terminal so it IS the primary EC2
    guest — hostname/IP/CPU/RAM match the instance the learner SSHs to from the
    AWS console. Best-effort; never breaks provisioning.
    """
    try:
        from apps.vmware_sim.aws_engine import get_state, _ensure

        sid = str(session_id)
        _ensure(sid, slug)
        state_inv = get_state(sid, slug) or {}
        # aws_engine.get_state wraps inventory under "state" (not top-level).
        inventory = state_inv.get("state") or state_inv
        instances = inventory.get("instances") or []
        if not instances:
            return
        # Prefer a running instance named in broken/goal hints, else first running, else first.
        want_names = set()
        broken = inventory.get("broken") or {}
        for key in ("require_stopped", "require_running"):
            if isinstance(broken.get(key), str):
                want_names.add(broken[key])
        tag = broken.get("require_tag") or {}
        if isinstance(tag, dict) and tag.get("name"):
            want_names.add(tag["name"])

        inst = None
        for name in want_names:
            inst = next((i for i in instances if i.get("name") == name), None)
            if inst:
                break
        if inst is None:
            inst = next((i for i in instances if i.get("state") == "running"), None) or instances[0]

        private_ip = inst.get("privateIp") or ""
        hostname = f"ip-{private_ip.replace('.', '-')}" if private_ip else (inst.get("name") or "ec2-sim")
        itype = (inst.get("type") or "t3.micro").lower()
        cpu, mem_mb = _EC2_TYPE_HW.get(itype, (2, 1024))

        shell_state = engine.shell.state
        shell_state.set_hostname(hostname)
        shell_state.set_hardware(cpu=cpu, mem_mb=mem_mb)
        if private_ip:
            shell_state.set_host_ip(private_ip)
        try:
            from .simulation.server_identity import seed_from_aws_instance
            seed_from_aws_instance(sid, inst, role="primary")
        except Exception:
            logger.exception("ServerIdentity AWS seed skipped for session %s", session_id)
    except Exception:
        logger.exception("AWS EC2 seed skipped for session %s", session_id)


def _seed_gpu_identity_if_needed(engine, session_id, slug: str, sim_type: str) -> None:
    """Register a virtualized GPU node in ServerIdentity for GPU-track labs."""
    low = (slug or "").lower()
    if sim_type != "gpu" and "gpu" not in low and "nvidia" not in low:
        return
    try:
        from .simulation import server_identity as si
        healthy = bool(getattr(getattr(engine, "shell", None), "state", None) and engine.shell.state.gpu_healthy)
        hostname = getattr(engine.shell.state, "hostname", None) or "gpu-node-01"
        primary_ip = "10.20.40.10"
        for nic in getattr(engine.shell.state, "nics", []) or []:
            if getattr(nic, "ip", None) or (isinstance(nic, dict) and nic.get("ip")):
                primary_ip = getattr(nic, "ip", None) or nic.get("ip")
                break
        si.seed_gpu_node(
            str(session_id),
            hostname=hostname,
            primary_ip=primary_ip,
            healthy=healthy,
        )
        engine.lab_session_id = str(session_id)
    except Exception:
        logger.exception("GPU identity seed skipped for session %s", session_id)


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
    fresh = True
    if snapshot and snapshot.get("version") == 1:
        from .simulation.sim_persistence import restore_engine
        restored = restore_engine(snapshot)
        if restored:
            engine = restored
            fresh = False  # keep the persisted (already-seeded) state
        else:
            engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type)
            _apply_initial_host_state(engine, slug)
    else:
        engine = UnifiedSimulationEngine(scenario_slug=slug, simulation_type=sim_type)
        _apply_initial_host_state(engine, slug)
    engine.lab_session_id = session_id
    if fresh and _is_vmware_lab(slug, raw_type):
        _seed_state_from_vmware_vm(engine, session_id, slug)
    elif fresh and _is_aws_lab(slug, raw_type):
        _seed_state_from_aws_ec2(engine, session_id, slug)
    if fresh:
        _seed_gpu_identity_if_needed(engine, session_id, slug, sim_type)
        try:
            from .simulation.server_identity import seed_scenario_lab_servers
            seed_scenario_lab_servers(session_id, sim_type=sim_type, slug=slug, engine=engine)
        except Exception:
            logger.exception("LabServer seed skipped for session %s", session_id)
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
        engine.lab_session_id = str(lab_session.id)
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
            _seed_state_from_vmware_vm(engine, lab_session.id, slug)
        elif _is_aws_lab(slug, raw_type):
            from apps.vmware_sim.aws_engine import _ensure as aws_ensure
            aws_ensure(str(lab_session.id), slug)
            _seed_state_from_aws_ec2(engine, lab_session.id, slug)
        else:
            _seed_hostname_for_persona(engine, slug, raw_type)
            _seed_gpu_identity_if_needed(engine, lab_session.id, slug, sim_type)

        # Scenario-scoped LabServer: terminal OS identity for this session only.
        try:
            from .simulation.server_identity import seed_scenario_lab_servers
            seed_scenario_lab_servers(
                str(lab_session.id),
                sim_type=sim_type,
                slug=slug,
                engine=engine,
            )
        except Exception:
            logger.exception("LabServer seed skipped for session %s", lab_session.id)

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
            "-----BEGIN OPENSSH PRIVATE KEY-----\n(lab-training-key)\n-----END OPENSSH PRIVATE KEY-----\n",
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
        # Cross-technology LINUX/K8s labs whose slug merely CONTAINS "vmware"
        # (e.g. linux-lvm-extend-vmware-disk-rescan) are NOT pure vCenter labs:
        # the VMware step is one leg, but the graded objective lives in the RHEL
        # terminal engine. Routing them to validate_vmware_lab auto-passed on the
        # fresh vCenter world (the generic "issue resolved" fall-through) — a
        # fail-open grader. Let them fall through to validate_simulation_state,
        # which carries the correct fail-closed cross-tech logic (disk revealed +
        # PV/VG/LV extended, NIC configured, guest reset + service healthy).
        try:
            from apps.labs.provisioner.simulation.vmware_bridge import (
                is_cross_tech_scenario as _is_cross_tech,
            )
        except Exception:  # pragma: no cover - defensive
            _is_cross_tech = lambda _s: False  # noqa: E731
        if "vmware" in low_slug and not _is_cross_tech(low_slug):
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
        if (
            low_slug.startswith(("win-gui-", "windows-", "academy-windows-"))
            or _raw_win_type in ("windows", "windows-server")
        ):
            # audit P0-2: the whole Windows track carries simulation_type
            # "windows" (not "windows-server") and slugs like academy-windows-*;
            # gate on the raw type + those prefixes so "Check" routes to the
            # Windows grader instead of falling through to the Linux validator.
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
        # Commvault CommCell (backup/restore). Raw simulation_type "commvault"
        # may normalize to "generic"; gate on that OR a commvault-* slug.
        _raw_cv_type = sim_type
        if not _raw_cv_type or _raw_cv_type == "generic":
            from apps.labs.models import LabSession
            try:
                _cv_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                _raw_cv_type = (getattr(_cv_session.scenario, "simulation_type", "") or "")
            except LabSession.DoesNotExist:
                _raw_cv_type = ""
        if _raw_cv_type == "commvault" or low_slug.startswith(("commvault-", "cv-")):
            from apps.labs.models import LabSession
            from apps.vmware_sim.commvault_engine import validate_commvault_lab, _ensure as cv_ensure
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                cv_ensure(str(lab_session.id), slug)
                return validate_commvault_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "Commvault simulation session not found"
        # NetApp ONTAP System Manager.
        _raw_na_type = sim_type
        if not _raw_na_type or _raw_na_type == "generic":
            from apps.labs.models import LabSession
            try:
                _na_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                _raw_na_type = (getattr(_na_session.scenario, "simulation_type", "") or "")
            except LabSession.DoesNotExist:
                _raw_na_type = ""
        if _raw_na_type == "netapp" or low_slug.startswith(("netapp-", "ontap-")):
            from apps.labs.models import LabSession
            from apps.vmware_sim.netapp_engine import validate_netapp_lab, _ensure as na_ensure
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                na_ensure(str(lab_session.id), slug)
                return validate_netapp_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "NetApp simulation session not found"
        # Dell EMC Unisphere / PowerMax.
        _raw_de_type = sim_type
        if not _raw_de_type or _raw_de_type == "generic":
            from apps.labs.models import LabSession
            try:
                _de_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                _raw_de_type = (getattr(_de_session.scenario, "simulation_type", "") or "")
            except LabSession.DoesNotExist:
                _raw_de_type = ""
        if _raw_de_type == "dellemc" or low_slug.startswith(("dellemc-", "powermax-")):
            from apps.labs.models import LabSession
            from apps.vmware_sim.dellemc_engine import validate_dellemc_lab, _ensure as de_ensure
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                de_ensure(str(lab_session.id), slug)
                return validate_dellemc_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "Dell EMC simulation session not found"
        # Physical datacenter (DCIM) break/fix.
        _raw_dc_type = sim_type
        if not _raw_dc_type or _raw_dc_type == "generic":
            from apps.labs.models import LabSession
            try:
                _dc_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                _raw_dc_type = (getattr(_dc_session.scenario, "simulation_type", "") or "")
            except LabSession.DoesNotExist:
                _raw_dc_type = ""
        if _raw_dc_type == "datacenter" or low_slug.startswith(("datacenter-", "dc-")):
            from apps.labs.models import LabSession
            from apps.vmware_sim.datacenter_engine import validate_datacenter_lab, _ensure as dc_ensure
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                dc_ensure(str(lab_session.id), slug)
                return validate_datacenter_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "Datacenter simulation session not found"
        # SOC / SIEM (cybersecurity) triage.
        _raw_soc_type = sim_type
        if not _raw_soc_type or _raw_soc_type == "generic":
            from apps.labs.models import LabSession
            try:
                _soc_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                _raw_soc_type = (getattr(_soc_session.scenario, "simulation_type", "") or "")
            except LabSession.DoesNotExist:
                _raw_soc_type = ""
        if _raw_soc_type == "soc" or low_slug.startswith("soc-"):
            from apps.labs.models import LabSession
            from apps.vmware_sim.soc_engine import validate_soc_lab, _ensure as soc_ensure
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                soc_ensure(str(lab_session.id), slug)
                return validate_soc_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "SOC simulation session not found"
        # Monitoring (Grafana / Prometheus observability). Legacy simulation_type
        # "monitoring"/"loki"/"alertmanager"/"promql" normalize to grafana/prometheus;
        # gate on the normalized persona, the RAW scenario type, or the slug. The
        # audit found this track was routed here but had NO validator, so "Check"
        # fell through to the generic path and could fail-open on a fresh world.
        _raw_mon_type = sim_type
        if not _raw_mon_type or _raw_mon_type == "generic":
            from apps.labs.models import LabSession
            try:
                _mon_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                _raw_mon_type = (getattr(_mon_session.scenario, "simulation_type", "") or "")
            except LabSession.DoesNotExist:
                _raw_mon_type = ""
        if (
            sim_type in ("grafana", "prometheus")
            or _raw_mon_type in ("monitoring", "grafana", "prometheus", "loki", "alertmanager", "promql")
            or low_slug.startswith(("monitoring-", "grafana-", "prometheus-", "promql-",
                                    "alertmanager-", "loki-"))
        ):
            from apps.labs.models import LabSession
            from apps.vmware_sim.monitoring_engine import (
                validate_monitoring_lab, _ensure_session as mon_ensure,
            )
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                mon_ensure(str(lab_session.id), slug)
                return validate_monitoring_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "Monitoring simulation session not found"
        # CI/CD pipeline (DevOps). Raw simulation_type "devops" normalizes to
        # itself; gate on that + a cicd/pipeline slug. The audit found the CI/CD
        # track had no engine and no validator (the pipeline player is fully
        # client-side), so it could not be graded server-side at all.
        _raw_cicd_type = sim_type
        if not _raw_cicd_type or _raw_cicd_type == "generic":
            from apps.labs.models import LabSession
            try:
                _cicd_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                _raw_cicd_type = (getattr(_cicd_session.scenario, "simulation_type", "") or "")
            except LabSession.DoesNotExist:
                _raw_cicd_type = ""
        if (
            sim_type == "devops"
            or _raw_cicd_type in ("devops", "cicd", "ci-cd", "ci_cd")
            or low_slug.startswith(("cicd-", "ci-cd-", "pipeline-", "devops-", "gitlab-ci-",
                                    "github-actions-"))
        ):
            from apps.labs.models import LabSession
            from apps.vmware_sim.cicd_engine import (
                validate_cicd_lab, _ensure_session as cicd_ensure,
            )
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                cicd_ensure(str(lab_session.id), slug)
                return validate_cicd_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "CI/CD simulation session not found"
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
        # AWS console simulator: sim_type "aws" (may normalize to "generic") or an
        # aws-* / ec2-* / s3-* slug. Gate on the raw type read off the scenario.
        _raw_aws_type = sim_type
        if not _raw_aws_type or _raw_aws_type == "generic":
            from apps.labs.models import LabSession
            try:
                _aws_session = LabSession.objects.select_related("scenario").get(container_id=resource_id)
                _raw_aws_type = (getattr(_aws_session.scenario, "simulation_type", "") or "")
            except LabSession.DoesNotExist:
                _raw_aws_type = ""
        if _raw_aws_type == "aws" or low_slug.startswith(("aws-", "ec2-", "s3-", "iam-")):
            from apps.labs.models import LabSession
            from apps.vmware_sim.aws_engine import validate_aws_lab, _ensure as aws_ensure
            try:
                lab_session = LabSession.objects.get(container_id=resource_id)
                aws_ensure(str(lab_session.id), slug)
                return validate_aws_lab(str(lab_session.id), slug)
            except LabSession.DoesNotExist:
                return False, "AWS simulation session not found"
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
        try:
            from apps.labs.provisioner.simulation.vmware_bridge import clear as clear_vmware_bridge

            clear_vmware_bridge(str(session.id))
        except Exception:  # noqa: BLE001
            pass
        try:
            from apps.vmware_sim import aws_engine as ae

            ae.clear_session(str(session.id))
        except Exception:  # noqa: BLE001
            pass
        try:
            from apps.labs.provisioner.simulation.aws_bridge import clear as clear_aws_bridge

            clear_aws_bridge(str(session.id))
        except Exception:  # noqa: BLE001
            pass
        for engine_module in ("commvault_engine", "netapp_engine", "dellemc_engine",
                               "datacenter_engine", "soc_engine"):
            try:
                mod = __import__(f"apps.vmware_sim.{engine_module}", fromlist=["drop_session"])
                mod.drop_session(str(session.id))
            except Exception:  # noqa: BLE001
                pass
        drop_sim_session(str(session.id))
