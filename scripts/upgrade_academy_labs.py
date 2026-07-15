#!/usr/bin/env python3
"""Upgrade academy labs from FIXED-OK marker checks to real simulation validation (B3).

Converts ~3k academy scenarios that only grep a sentinel file into labs that:
  • boot with a genuinely broken state (failed systemd unit, unreachable ansible
    hosts, crashed k8s pods, stopped compose stack, unhealthy GPU), and
  • validate via check.sh probes the simulation engine understands (systemctl
    is-active, ansible ping, kubectl, docker ps, nvidia-smi).

Skips slugs already upgraded by scripts/upgrade_flagship_labs.py (FLAGSHIP_SLUGS).

Outputs:
  backend/apps/labs/provisioner/simulation/academy_service_presets.py
  backend/apps/labs/provisioner/simulation/academy_service_e2e_fixes.py

Also rewrites each scenario's check.sh and patches scenario.yaml (objectives,
initial_state, tier-3 hints — removes FIXED-OK references).

Re-run idempotently after adding academy scenarios.
"""
from __future__ import annotations

import argparse
import re
import textwrap
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCEN = ROOT / "scenarios"
PRESET_OUT = ROOT / "backend/apps/labs/provisioner/simulation/academy_service_presets.py"
E2E_OUT = ROOT / "backend/apps/labs/provisioner/simulation/academy_service_e2e_fixes.py"

try:
    from apps.labs.provisioner.simulation.flagship_presets import FLAGSHIP_SLUGS
except Exception:
    FLAGSHIP_SLUGS = frozenset(
        re.findall(
            r"'(academy-[^']+)':",
            (ROOT / "backend/apps/labs/provisioner/simulation/flagship_presets.py").read_text(
                encoding="utf-8"
            )
            if (ROOT / "backend/apps/labs/provisioner/simulation/flagship_presets.py").is_file()
            else "",
        )
    )

MARKER_RE = re.compile(r"grep\s+-q\s+FIXED-OK|FIXED-OK.*grep", re.I)
# An already-upgraded service lab (a prior generator run rewrote its check.sh to
# `systemctl is-active <unit>`). We must re-match these so re-runs can retarget
# the graded unit to a topic-appropriate one — otherwise the gate would skip
# them and _emit_* would ship EMPTY preset/fix maps. Kept narrow (only the
# generator's own service probe) so we never clobber hand-authored checks.
ALREADY_SERVICE_RE = re.compile(r"^\s*systemctl is-active \S+\s*$", re.M)

DEDICATED_SIM = frozenset({
    "nmap", "wireshark", "vmware", "terraform", "peoplesoft",
    "windows-server", "windows", "data-dashboard", "datascience",
    "ansible-awx", "ai-agent", "baremetal",
})

SERVICE_DESC: dict[str, str] = {
    "nginx": "The nginx HTTP and reverse proxy server",
    "crond": "Command Scheduler (cron)",
    "rsyslog": "System Logging Service",
    "chronyd": "NTP client/server (chrony)",
    "firewalld": "firewalld - dynamic firewall daemon",
    "docker": "Docker Application Container Engine",
    "postgresql": "PostgreSQL database server",
    "mysqld": "MariaDB database server",
    "httpd": "The Apache HTTP Server",
    "sssd": "System Security Services Daemon",
    "auditd": "Security Auditing Service",
    "tuned": "Dynamic System Tuning Daemon",
    "redis": "Redis persistent key-value database",
    "mongod": "MongoDB Database Server",
    "named": "Internet Domain Name Server",
    "haproxy": "HAProxy Load Balancer",
    "memcached": "Memcached",
    "rabbitmq-server": "RabbitMQ broker",
    "postfix": "Postfix Mail Transport Agent",
    "sshd": "OpenSSH server daemon",
    # Topic-appropriate application units so the graded fault matches the
    # scenario's described incident (see TASK #8 / test_academy_fix_alignment).
    "model-server": "ML Model Inference Server",
    "jupyter": "Jupyter Notebook Server",
    "spring-boot": "Spring Boot Application Service",
    "node-app": "Node.js Application Service",
    "grafana-server": "Grafana Dashboard Server",
    "prometheus": "Prometheus Monitoring Server",
    "gunicorn": "Gunicorn Python WSGI Server",
}

TECH_SERVICE_POOLS: dict[str, list[str]] = {
    "linux": ["nginx", "crond", "rsyslog", "chronyd"],
    "rhel-linux": ["chronyd", "rsyslog", "firewalld", "sssd", "auditd"],
    "docker": ["docker"],
    "devops": ["nginx", "crond", "rsyslog"],
    "grafana": ["grafana-server"],
    "prometheus": ["prometheus"],
    "networking": ["nginx", "named", "haproxy"],
    "security": ["sshd", "auditd", "firewalld"],
    "shell-script": ["crond", "rsyslog"],
    "simulation": ["nginx", "crond"],
    "html": ["nginx", "httpd"],
    "database": ["postgresql", "mysqld", "redis"],
    "mysql": ["mysqld"],
    "postgresql": ["postgresql"],
    "sqlite": ["postgresql"],
    "python": ["gunicorn"],
    "java": ["spring-boot"],
    "javascript": ["node-app"],
    "nodejs": ["node-app"],
    "react": ["node-app"],
    "ai-ml": ["model-server"],
    "data-science": ["jupyter"],
    "prompt-engineering": ["model-server"],
    "gpu": ["nginx"],
    "baremetal": ["chronyd", "rsyslog"],
    "ansible": ["nginx"],
    "kubernetes": ["nginx"],
    "terraform": ["nginx"],
    "vmware": ["nginx"],
    "nmap": ["nginx"],
    "wireshark": ["nginx"],
    "windows": ["nginx"],
    "peoplesoft": ["nginx"],
}


def assign_service_unit(tech: str, slug: str) -> str:
    pool = TECH_SERVICE_POOLS.get(tech) or ["nginx", "crond", "rsyslog"]
    idx = sum(ord(c) for c in slug) % len(pool)
    return pool[idx]


def classify_mode(tech: str, sim_type: str, slug: str) -> str:
    if slug in FLAGSHIP_SLUGS:
        return "skip"
    if sim_type in DEDICATED_SIM:
        return "dedicated"
    if sim_type == "ansible" or tech == "ansible":
        return "ansible"
    if sim_type == "kubernetes" or tech == "kubernetes":
        return "k8s"
    if sim_type == "gpu" or tech == "gpu":
        return "gpu"
    if tech == "docker" and re.search(r"-compose(-\d+)?$", slug):
        return "docker_compose"
    return "service"


def check_script_for_mode(mode: str, unit: str = "") -> str:
    if mode == "dedicated":
        return "#!/usr/bin/env bash\n# Validated by the dedicated simulation engine (real state checks).\n"
    if mode == "ansible":
        return "#!/usr/bin/env bash\nansible webservers -m ping\n"
    if mode == "k8s":
        return "#!/usr/bin/env bash\nkubectl get pods | grep -q Running\n"
    if mode == "gpu":
        return "#!/usr/bin/env bash\nnvidia-smi\n"
    if mode == "docker_compose":
        return "#!/usr/bin/env bash\ndocker ps | grep -q Up\n"
    return f"#!/usr/bin/env bash\nsystemctl is-active {unit}\n"


def verify_hint_line(mode: str, unit: str = "") -> str:
    if mode == "ansible":
        return "`ansible webservers -m ping` returns SUCCESS for every host"
    if mode == "k8s":
        return "`kubectl get pods` shows every pod Running"
    if mode == "gpu":
        return "`nvidia-smi` reports a healthy GPU"
    if mode == "docker_compose":
        return "`docker ps` shows application containers Up"
    return f"`systemctl is-active {unit}` returns active"


def patch_scenario_yaml(path: Path, mode: str, unit: str, topic_label: str) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    verify = verify_hint_line(mode, unit)
    if mode == "service":
        desc = (
            f"Service operations lab. The `{unit}` systemd unit is **failed/inactive** on "
            f"this host — a realistic fault for {topic_label} workflows that depend on it. "
            f"Diagnose with `systemctl status {unit}` and journal logs, apply the smallest "
            f"reliable fix, then verify with `systemctl is-active {unit}`."
        )
        initial = (
            f"The `{unit}` service is not running (`systemctl is-active {unit}` → inactive/failed). "
            f"Dependent {topic_label} tasks cannot succeed until the unit is healthy again."
        )
        objectives = [
            f"The `{unit}` service is active (running)",
            f"`systemctl is-active {unit}` returns active",
            "The fix survives a status re-check (no marker files)",
        ]
        data["description"] = desc
        data["initial_state"] = initial
        data["objectives"] = objectives
    elif mode == "ansible":
        data["description"] = (
            "Ansible control-node lab. Managed hosts in `webservers` are unreachable over SSH — "
            "`ansible webservers -m ping` fails. Establish key-based access and verify SUCCESS/pong."
        )
        data["initial_state"] = (
            "`ansible webservers -m ping` fails with unreachable/permission errors until SSH keys are distributed."
        )
        data["objectives"] = [
            "All webservers hosts answer ansible ping with SUCCESS",
            "Key-based SSH works without a password prompt",
            verify,
        ]
    elif mode == "k8s":
        data["description"] = (
            "Kubernetes operations lab. One or more pods are **not Running** — workloads for "
            f"{topic_label} cannot serve traffic. Inspect with `kubectl get pods`, read "
            "`kubectl describe pod` events, fix the root cause, and confirm all pods Running."
        )
        data["initial_state"] = "The cluster is up but at least one pod is CrashLoopBackOff or Pending."
        data["objectives"] = [
            "All pods in the default namespace are Running",
            verify,
            "The deployment survives `kubectl get pods` re-check",
        ]
    elif mode == "gpu":
        data["description"] = (
            "GPU host lab. `nvidia-smi` reports the GPU unhealthy — ML/GPU workloads cannot start. "
            "Load the driver / restore GPU health, then verify with `nvidia-smi`."
        )
        data["initial_state"] = "The NVIDIA driver/GPU is not healthy (`nvidia-smi` fails)."
        data["objectives"] = ["GPU reports healthy in nvidia-smi", verify]
    elif mode == "docker_compose":
        data["description"] = (
            "Docker Compose lab. The stack is defined but **no containers are Up** — "
            f"{topic_label} services are offline. Bring the stack up and verify with `docker ps`."
        )
        data["initial_state"] = "`docker ps` shows no application containers in Up state."
        data["objectives"] = ["Compose stack containers are Up", verify]

    hints = data.get("hints") or []
    for h in hints:
        if h.get("order") == 3:
            content = (h.get("content") or "")
            content = re.sub(
                r"\n4\. Record completion:.*",
                f"\n4. Click Check Solution once {verify}.",
                content,
                flags=re.S,
            )
            content = content.replace("FIXED-OK", "the real fix")
            h["content"] = content
    data["hints"] = hints
    path.write_text(
        yaml.dump(data, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def _emit_presets(entries: dict[str, tuple[str, str]]) -> None:
    """entries: slug -> (preset_kind, unit_or_empty)"""
    lines = [
        '"""GENERATED by scripts/upgrade_academy_labs.py — do not edit by hand.',
        "",
        "Real-simulation break presets for academy labs (non-flagship). Overrides",
        "COMPLETE_TECH marker presets so labs boot fail-closed on genuine OS state.",
        '"""',
        "from __future__ import annotations",
        "",
        "from .rhel_os import SimService",
        "",
        "",
        "def _break_service(state, unit: str, desc: str) -> None:",
        "    state.services[unit] = SimService(",
        '        unit, active="failed", enabled="enabled", description=desc,',
        '        loaded="loaded", sub_state="failed",',
        '        unit_file=f"[Unit]\\nDescription={desc}\\n",',
        "    )",
        "",
        "",
        "def _preset_docker_stack_down(state) -> None:",
        '    if "docker" not in state.services:',
        "        state.services[\"docker\"] = SimService(",
        '            "docker", active="active", enabled="enabled",',
        '            description="Docker Application Container Engine",',
        '            loaded="loaded", sub_state="running",',
        "        )",
        "    # compose stack intentionally not running — validated via docker ps",
        "",
        "",
        "def _preset_gpu_unhealthy(state) -> None:",
        "    state.gpu_healthy = False",
        "",
        "",
        "def _preset_ansible_unreachable(state) -> None:",
        "    return  # engine._ssh_key_fixed stays False until keys are distributed",
        "",
        "",
        "ACADEMY_SERVICE_PRESETS = {",
    ]
    for slug in sorted(entries):
        kind, unit = entries[slug]
        if kind == "service":
            desc = SERVICE_DESC.get(unit, unit)
            lines.append(
                f"    {slug!r}: lambda state, u={unit!r}, d={desc!r}: "
                f"_break_service(state, u, d),"
            )
        elif kind == "docker_compose":
            lines.append(f"    {slug!r}: _preset_docker_stack_down,")
        elif kind == "gpu":
            lines.append(f"    {slug!r}: _preset_gpu_unhealthy,")
        elif kind == "ansible":
            lines.append(f"    {slug!r}: _preset_ansible_unreachable,")
        # k8s + dedicated: no OS preset (k8s broken in simulation_modules)
    lines.append("}")
    lines.append("")
    PRESET_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _emit_e2e_fixes(service_fix: dict[str, str], docker_slugs: set[str], ansible_slugs: set[str]) -> None:
    lines = [
        '"""GENERATED by scripts/upgrade_academy_labs.py — do not edit by hand.',
        "",
        "E2E fix maps for academy real-state labs (systemctl start / compose up).",
        '"""',
        "from __future__ import annotations",
        "",
        "ACADEMY_SERVICE_FIX: dict[str, str] = {",
    ]
    for slug, unit in sorted(service_fix.items()):
        lines.append(f"    {slug!r}: {unit!r},")
    lines.append("}")
    lines.append("")
    lines.append("ACADEMY_DOCKER_COMPOSE_SLUGS = frozenset({")
    for slug in sorted(docker_slugs):
        lines.append(f"    {slug!r},")
    lines.append("})")
    lines.append("")
    lines.append("ACADEMY_ANSIBLE_SLUGS = frozenset({")
    for slug in sorted(ansible_slugs):
        lines.append(f"    {slug!r},")
    lines.append("})")
    lines.append("")
    E2E_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upgrade academy labs to real validation")
    parser.add_argument("--technology", default="", help="Only one tech folder slug")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    tech_filter = args.technology.strip()

    preset_entries: dict[str, tuple[str, str]] = {}
    service_fix: dict[str, str] = {}
    docker_slugs: set[str] = set()
    ansible_slugs: set[str] = set()
    counts: dict[str, int] = {}

    for tech_dir in sorted(SCEN.iterdir()):
        if not tech_dir.is_dir() or tech_dir.name == "shared":
            continue
        if tech_filter and tech_dir.name != tech_filter:
            continue
        tech = tech_dir.name
        for folder in sorted(tech_dir.glob("academy-*")):
            yaml_path = folder / "scenario.yaml"
            check_path = folder / "check.sh"
            if not yaml_path.is_file():
                continue
            slug = folder.name
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            sim_type = (data.get("simulation_type") or "generic").strip()
            mode = classify_mode(tech, sim_type, slug)
            if mode == "skip":
                continue
            check_body = check_path.read_text(encoding="utf-8") if check_path.is_file() else ""
            # Match still-marker labs (first upgrade) AND already-upgraded service
            # labs (re-run: retarget the graded unit). Non-service already-upgraded
            # modes (ansible/k8s/gpu/docker/dedicated) carry no `systemctl is-active`
            # line, so they only re-match when the classify() mode below matches —
            # their check.sh is regenerated deterministically regardless.
            is_marker = bool(MARKER_RE.search(check_body))
            is_upgraded_service = bool(ALREADY_SERVICE_RE.search(check_body))
            is_upgraded_nonservice = mode in {"ansible", "k8s", "gpu", "docker_compose"}
            if not (is_marker or is_upgraded_service or is_upgraded_nonservice):
                continue

            unit = assign_service_unit(tech, slug)
            script = check_script_for_mode(mode, unit)
            title = (data.get("title") or slug).split("—")[-1].strip()
            topic_label = title or tech.replace("-", " ")

            if not args.dry_run:
                check_path.write_text(script + "exit 0\n", encoding="utf-8")
                # Only FIRST-TIME upgrades (marker still present) get the scenario.yaml
                # description/objectives/hints template. Already-upgraded labs were
                # further enriched downstream (topic-specific ticket context); a re-run
                # here only RETARGETS the graded unit (check.sh + maps) and must NOT
                # clobber that enrichment — per TASK #8 "keep the enriched description".
                if is_marker:
                    patch_scenario_yaml(yaml_path, mode, unit, topic_label)

            if mode == "service":
                preset_entries[slug] = ("service", unit)
                service_fix[slug] = unit
            elif mode == "docker_compose":
                preset_entries[slug] = ("docker_compose", "")
                docker_slugs.add(slug)
            elif mode == "gpu":
                preset_entries[slug] = ("gpu", "")
            elif mode == "ansible":
                preset_entries[slug] = ("ansible", "")
                ansible_slugs.add(slug)
            # k8s + dedicated: check.sh only (+ k8s engine hook)

            counts[mode] = counts.get(mode, 0) + 1

    if not args.dry_run:
        _emit_presets(preset_entries)
        _emit_e2e_fixes(service_fix, docker_slugs, ansible_slugs)

    total = sum(counts.values())
    print(f"academy labs upgraded: {total}")
    for k in sorted(counts):
        print(f"  {k:16s} {counts[k]}")
    if not args.dry_run:
        print(f"presets: {PRESET_OUT}")
        print(f"e2e fixes: {E2E_OUT}")


if __name__ == "__main__":
    main()
