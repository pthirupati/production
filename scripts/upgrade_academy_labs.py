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
ALREADY_CLOUD_RE = re.compile(r"systemctl is-failed", re.M)

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
    "gitlab-runner": "GitLab Runner",
    "jenkins": "Jenkins Automation Server",
    "memcached": "Memcached",
    "rabbitmq-server": "RabbitMQ broker",
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

# Keyword → graded systemd unit (must match topic_faults planting).
# First match wins. Keep in sync with topic_faults.py keyword lists.
TOPIC_UNIT_RULES: list[tuple[tuple[str, ...], str]] = [
    (("git-flow", "git-merge", "learn-git", "ci-pipeline", "cicd", "gitlab-ci",
      "jenkins", "artifacts", "cd-release", "change-management", "incident-response"),
     "gitlab-runner"),
    (("firewall",), "firewalld"),
    (("dns", "resolv"), "named"),
    (("ntp", "chrony"), "chronyd"),
    (("selinux", "audit"), "auditd"),
    (("ssh",), "sshd"),
    (("postgres", "postgresql"), "postgresql"),
    (("mysql", "mariadb"), "mysqld"),
    (("redis",), "redis"),
    (("mongo",), "mongod"),
    (("memcached", "memcache"), "memcached"),
    (("rabbitmq", "amqp"), "rabbitmq-server"),
    (("docker", "compose", "containerd"), "docker"),
    (("haproxy", "load-balanc"), "haproxy"),
    (("spring-boot", "jvm", "tomcat", "springboot"), "spring-boot"),
    (("prometheus",), "prometheus"),
    (("grafana",), "grafana-server"),
]

PERM_KEYWORDS = ("permissions", "acl", "chmod", "chown", "sudoers")
GITOPS_KEYWORDS = ("gitops", "argocd", "flux", "outofsync", "kustomize", "drift")
MARKER_TOPIC_KEYWORDS = PERM_KEYWORDS + ("secrets", "vault", "tls-", "cert-", "rbac", "owasp",
                                           "vlan", "bonding", "mtu", "nat", "terraform", "tfstate")
CLOUD_ACADEMY_PREFIXES = (
    "academy-aws", "academy-azure", "academy-gcp", "academy-openstack",
)
CLOUD_SLUG_PREFIXES = ("aws-", "azure-", "gcp-", "openstack-")


def assign_service_unit(tech: str, slug: str) -> str:
    low = (slug or "").lower()
    # Avoid matching "java" inside "javascript"
    if "javascript" in low or tech == "javascript":
        return "node-app"
    for keys, unit in TOPIC_UNIT_RULES:
        if any(k in low for k in keys):
            return unit
    pool = TECH_SERVICE_POOLS.get(tech) or ["nginx", "crond", "rsyslog"]
    idx = sum(ord(c) for c in slug) % len(pool)
    return pool[idx]


def classify_mode(tech: str, sim_type: str, slug: str) -> str:
    if slug in FLAGSHIP_SLUGS:
        return "skip"
    low = (slug or "").lower()
    # Cloud academies: grade via is-failed + planted sentinel (same contract as AWS).
    if low.startswith(CLOUD_ACADEMY_PREFIXES) or (
        low.startswith(CLOUD_SLUG_PREFIXES) and "terraform" not in low
    ) or tech in ("aws", "azure", "gcp", "openstack"):
        return "topic_cloud"
    # Permission / secrets / IaC topics are graded via FIXED-OK sentinel that
    # topic_faults plants — not a recycled nginx unit.
    if any(k in low for k in MARKER_TOPIC_KEYWORDS) or any(k in low for k in GITOPS_KEYWORDS):
        return "topic_marker"
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


def check_script_for_mode(mode: str, unit: str = "", slug: str = "") -> str:
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
    if mode == "topic_marker":
        return f"#!/usr/bin/env bash\ngrep -q FIXED-OK /opt/fixitlab/academy/{slug}.conf\n"
    if mode == "topic_cloud":
        return (
            "#!/usr/bin/env bash\n"
            "systemctl is-failed --quiet 2>/dev/null; test $? -ne 0\n"
        )
    return f"#!/usr/bin/env bash\nsystemctl is-active {unit}\n"


def verify_hint_line(mode: str, unit: str = "", slug: str = "") -> str:
    if mode == "ansible":
        return "`ansible webservers -m ping` returns SUCCESS for every host"
    if mode == "k8s":
        return "`kubectl get pods` shows every pod Running"
    if mode == "gpu":
        return "`nvidia-smi` reports a healthy GPU"
    if mode == "docker_compose":
        return "`docker ps` shows application containers Up"
    if mode == "topic_marker":
        return f"`grep -q FIXED-OK /opt/fixitlab/academy/{slug}.conf` succeeds after the documented fix"
    if mode == "topic_cloud":
        return "cloud Lab Server health check passes (`systemctl is-failed` finds no failed units / config repaired)"
    return f"`systemctl is-active {unit}` returns active"


def _topic_hint_blocks(mode: str, unit: str, slug: str) -> dict[int, str]:
    """Replace diagnostic/fix hint tiers so they match planted topic faults."""
    low = (slug or "").lower()
    if mode == "topic_marker" and any(k in low for k in GITOPS_KEYWORDS):
        return {
            3: (
                "WHICH TOOL — the diagnostic command(s):\n"
                "Inspect GitOps state: `cat /opt/gitops/application.yaml` and "
                "`cat /opt/gitops/flux-kustomization.yaml`. Look for OutOfSync / Ready=False."
            ),
            4: (
                "NARROW DOWN — isolate the subsystem:\n"
                "1. Confirm sync/health status in the Application manifest.\n"
                "2. Check `syncPolicy` and source path/repoURL.\n"
                "3. Compare with the Flux Kustomization Ready condition."
            ),
            5: (
                "NEAR-SOLUTION — the fix shape + verify (you still apply it):\n"
                "1. Repair `/opt/gitops/application.yaml` so sync is healthy (Synced/Healthy).\n"
                "2. Fix Flux reconciliation errors in `/opt/gitops/flux-kustomization.yaml`.\n"
                "3. Click Check Solution once the documented remediation is applied "
                f"(grader: {verify_hint_line(mode, unit, slug)})."
            ),
        }
    if unit == "gitlab-runner" or any(
        k in low for k in ("git-flow", "ci-pipeline", "cicd", "jenkins", "artifacts", "cd-release")
    ):
        return {
            3: (
                "WHICH TOOL — the diagnostic command(s):\n"
                "Check the runner: `systemctl status gitlab-runner`. Inspect CI config under "
                "`/opt/ci/.gitlab-ci.yml` and `/opt/ci/Jenkinsfile` for failing stages."
            ),
            4: (
                "NARROW DOWN — isolate the subsystem:\n"
                "1. Confirm `gitlab-runner` is failed/inactive.\n"
                "2. Read `/opt/ci/.gitlab-ci.yml` for BROKEN_PIPELINE / exit 1 steps.\n"
                "3. Check `/root/app/.git/config` for a usable remote/branch setup."
            ),
            5: (
                "NEAR-SOLUTION — the fix shape + verify (you still apply it):\n"
                "1. Repair the CI pipeline YAML so the build stage succeeds.\n"
                "2. `systemctl enable --now gitlab-runner`.\n"
                "3. Verify with `systemctl is-active gitlab-runner` (expect active)."
            ),
        }
    if mode == "topic_marker" and any(k in low for k in PERM_KEYWORDS):
        return {
            3: (
                "WHICH TOOL — the diagnostic command(s):\n"
                "Inspect permissions: `ls -la /opt/app/secret.env` and "
                "`cat /etc/sudoers.d/app`. World-writable secrets and NOPASSWD ALL are the faults."
            ),
            4: (
                "NARROW DOWN — isolate the subsystem:\n"
                "1. Confirm secret.env mode is 777 (too open).\n"
                "2. Review sudoers.d for overly broad privileges.\n"
                "3. Decide least-privilege mode/owner for the app secret."
            ),
            5: (
                "NEAR-SOLUTION — the fix shape + verify (you still apply it):\n"
                "1. `chmod 600 /opt/app/secret.env` (and chown if needed).\n"
                "2. Lock down `/etc/sudoers.d/app` to the minimum required.\n"
                "3. Click Check Solution once the documented remediation is applied."
            ),
        }
    if mode == "topic_cloud":
        cloud = "aws"
        if "azure" in low:
            cloud = "azure"
        elif "gcp" in low:
            cloud = "gcp"
        elif "openstack" in low or "nova" in low or "neutron" in low:
            cloud = "openstack"
        paths = {
            "aws": "`/opt/aws/lab-state.json` and the AWS CLI profile",
            "azure": "`/opt/azure/config` and `az account show`",
            "gcp": "`/opt/gcp/config` and `gcloud config list`",
            "openstack": "`/opt/openstack/clouds.yaml` and `openstack server list`",
        }
        return {
            3: (
                f"WHICH TOOL — the diagnostic command(s):\n"
                f"Inspect the planted {cloud} Lab Server fault: {paths[cloud]}. "
                f"Do not chase unrelated nginx/rsyslog units."
            ),
            4: (
                f"NARROW DOWN — isolate the subsystem:\n"
                f"1. Confirm the {cloud} config under /opt/{cloud}/ is broken.\n"
                f"2. Repair credentials/project/region (or OpenStack clouds.yaml).\n"
                f"3. Re-check with the cloud CLI until the profile is healthy."
            ),
            5: (
                f"NEAR-SOLUTION — the fix shape + verify (you still apply it):\n"
                f"1. Fix the broken {cloud} configuration on this Lab Server.\n"
                f"2. Apply the documented remediation (config + FIXED-OK where required).\n"
                f"3. Click Check Solution once {verify_hint_line(mode, unit, slug)}."
            ),
        }
    if mode == "service" and unit:
        return {
            3: (
                f"WHICH TOOL — the diagnostic command(s):\n"
                f"Run `systemctl status {unit}` and `journalctl -u {unit} -n 50`."
            ),
            4: (
                f"NARROW DOWN — isolate the subsystem:\n"
                f"1. Confirm `{unit}` is failed/inactive.\n"
                f"2. Read the unit journal for the root cause.\n"
                f"3. Apply the smallest fix that restores the unit."
            ),
            5: (
                f"NEAR-SOLUTION — the fix shape + verify (you still apply it):\n"
                f"1. Repair the underlying config/cause for `{unit}`.\n"
                f"2. `systemctl enable --now {unit}`.\n"
                f"3. Verify with `systemctl is-active {unit}` (expect active)."
            ),
        }
    return {}


def retarget_verify_and_hints(
    path: Path, mode: str, unit: str, slug: str, *, full_rewrite: bool = False
) -> None:
    """Update verify language + diagnostic hints without wiping ticket CONTEXT."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    verify = verify_hint_line(mode, unit, slug)
    desc = data.get("description") or ""
    if isinstance(desc, str) and mode == "service" and unit:
        # Preserve backticks around the verify phrase.
        desc = re.sub(
            r"`systemctl is-active \S+` returns active",
            f"`systemctl is-active {unit}` returns active",
            desc,
        )
        desc = re.sub(
            r"(?<!`)systemctl is-active \S+(?!`)",
            f"systemctl is-active {unit}",
            desc,
        )
        data["description"] = desc

    if full_rewrite:
        patch_scenario_yaml(path, mode, unit, topic_label=slug, slug=slug)
        return

    blocks = _topic_hint_blocks(mode, unit, slug)
    hints = data.get("hints") or []
    for h in hints:
        order = h.get("order")
        if order in blocks:
            h["content"] = blocks[order]
        elif order == 3 and unit:
            content = (h.get("content") or "")
            content = content.replace("nginx -t", f"systemctl status {unit}")
            content = re.sub(r"systemctl status \S+", f"systemctl status {unit}", content)
            h["content"] = content
    data["hints"] = hints

    # Retarget tasks / solution / guided_mode that still name a stale unit (nginx).
    if mode == "service" and unit:
        text = yaml.dump(data, sort_keys=False, allow_unicode=True, width=100)
        # Only swap common academy recycled units when the graded unit differs.
        for stale in ("nginx", "crond", "rsyslog"):
            if stale == unit:
                continue
            text = text.replace(f"systemctl is-active {stale}", f"systemctl is-active {unit}")
            text = text.replace(f"systemctl status {stale}", f"systemctl status {unit}")
            text = text.replace(f"`{stale}` service", f"`{unit}` service")
            text = text.replace(f"-u {stale}", f"-u {unit}")
        data = yaml.safe_load(text) or data
        sol = data.get("solution") or {}
        if isinstance(sol, dict) and unit:
            summary = sol.get("summary") or ""
            if "nginx" in summary and unit != "nginx":
                sol["summary"] = (
                    f"The root cause is an unhealthy `{unit}` service; repair it and verify active state."
                )
            cmds = sol.get("commands_run") or []
            sol["commands_run"] = [
                c.replace("nginx", unit) if isinstance(c, str) else c for c in cmds
            ]
            data["solution"] = sol
        for task in data.get("tasks") or []:
            val = (task or {}).get("validation") or {}
            if isinstance(val, dict) and "command" in val and unit:
                cmd = val.get("command") or ""
                if "systemctl is-active" in cmd:
                    val["command"] = f"systemctl is-active {unit}"
                    val["error_message"] = (
                        f"The {unit} service is not active yet. "
                        f"Check `systemctl status {unit}` and `journalctl -u {unit} -n 50`."
                    )
                    task["validation"] = val
        guided = data.get("guided_mode") or {}
        for step in guided.get("steps") or []:
            cmd = step.get("command") or ""
            if "systemctl is-active" in cmd and unit:
                step["command"] = f"systemctl is-active {unit}"
            exp = step.get("expected_output") or ""
            if "systemctl is-active" in exp and unit:
                step["expected_output"] = f"`systemctl is-active {unit}` returns active"

    path.write_text(
        yaml.dump(data, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def patch_scenario_yaml(
    path: Path, mode: str, unit: str, topic_label: str, slug: str = ""
) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    slug = slug or path.parent.name
    verify = verify_hint_line(mode, unit, slug)
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
    elif mode == "topic_marker":
        data["description"] = (
            f"Topic lab for {topic_label}. The Lab Server has a planted configuration fault "
            f"under `/opt` (and/or `/etc`). Diagnose from evidence, apply the smallest reliable "
            f"fix, then verify with the documented checker ({verify})."
        )
        data["initial_state"] = (
            "A topic-specific configuration fault is present on this host; dependent workflows fail until repaired."
        )
        data["objectives"] = [
            "Identify the planted configuration fault from evidence",
            "Apply the minimal documented remediation",
            verify,
        ]
    elif mode == "topic_cloud":
        data["description"] = (
            f"Cloud Lab Server operations for {topic_label}. A planted cloud CLI/API "
            f"configuration fault keeps the environment unhealthy. Repair the cloud profile "
            f"under `/opt`, then verify with the documented checker ({verify})."
        )
        data["initial_state"] = (
            "Cloud CLI/API configuration on this Lab Server is broken; console and CLI workflows fail until repaired."
        )
        data["objectives"] = [
            "Identify the planted cloud configuration fault",
            "Repair the cloud profile with the minimal change",
            verify,
        ]

    hints = data.get("hints") or []
    blocks = _topic_hint_blocks(mode, unit, slug)
    for h in hints:
        order = h.get("order")
        if order in blocks:
            h["content"] = blocks[order]
            continue
        if order == 3:
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
    parser.add_argument(
        "--force-hints",
        action="store_true",
        help="Retarget verify language + diagnostic hints even for already-upgraded labs",
    )
    args = parser.parse_args()
    tech_filter = args.technology.strip()

    preset_entries: dict[str, tuple[str, str]] = {}
    service_fix: dict[str, str] = {}
    docker_slugs: set[str] = set()
    ansible_slugs: set[str] = set()
    counts: dict[str, int] = {}

    # When filtering to one technology, preserve maps for other techs so we
    # don't wipe the generated preset/e2e files.
    if tech_filter and PRESET_OUT.is_file() and E2E_OUT.is_file():
        try:
            from apps.labs.provisioner.simulation.academy_service_e2e_fixes import (
                ACADEMY_ANSIBLE_SLUGS as _EXISTING_ANSIBLE,
                ACADEMY_DOCKER_COMPOSE_SLUGS as _EXISTING_DOCKER,
                ACADEMY_SERVICE_FIX as _EXISTING_FIX,
            )
            service_fix.update(_EXISTING_FIX)
            docker_slugs.update(_EXISTING_DOCKER)
            ansible_slugs.update(_EXISTING_ANSIBLE)
            for slug, unit in _EXISTING_FIX.items():
                if not slug.startswith(f"academy-{tech_filter}"):
                    preset_entries[slug] = ("service", unit)
            for slug in _EXISTING_DOCKER:
                if not slug.startswith(f"academy-{tech_filter}"):
                    preset_entries[slug] = ("docker_compose", "")
            for slug in _EXISTING_ANSIBLE:
                if not slug.startswith(f"academy-{tech_filter}"):
                    preset_entries[slug] = ("ansible", "")
        except Exception:
            pass

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
            # Drop prior entries for this tech when re-emitting under --technology
            if tech_filter:
                preset_entries.pop(slug, None)
                service_fix.pop(slug, None)
                docker_slugs.discard(slug)
                ansible_slugs.discard(slug)
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            sim_type = (data.get("simulation_type") or "generic").strip()
            mode = classify_mode(tech, sim_type, slug)
            if mode == "skip":
                continue
            check_body = check_path.read_text(encoding="utf-8") if check_path.is_file() else ""
            # Match still-marker labs (first upgrade) AND already-upgraded service
            # labs (re-run: retarget the graded unit). Non-service already-upgraded
            # modes (ansible/k8s/gpu/docker/dedicated/topic_marker) carry no
            # `systemctl is-active` line, so they re-match via classify() mode.
            is_marker = bool(MARKER_RE.search(check_body))
            is_upgraded_service = bool(ALREADY_SERVICE_RE.search(check_body))
            is_upgraded_cloud = bool(ALREADY_CLOUD_RE.search(check_body))
            is_upgraded_nonservice = mode in {
                "ansible", "k8s", "gpu", "docker_compose", "topic_marker",
                "topic_cloud", "dedicated",
            }
            if not (is_marker or is_upgraded_service or is_upgraded_cloud or is_upgraded_nonservice):
                continue

            unit = assign_service_unit(tech, slug)
            script = check_script_for_mode(mode, unit, slug)
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
                    patch_scenario_yaml(yaml_path, mode, unit, topic_label, slug=slug)
                elif args.force_hints:
                    retarget_verify_and_hints(yaml_path, mode, unit, slug)

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
            # k8s + dedicated + topic_marker: check.sh only (topic_faults plants state)

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
