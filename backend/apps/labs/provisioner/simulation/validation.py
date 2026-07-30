"""Evaluate check.sh-style validation against simulated RHEL state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .rhel_os import RHELOSState
from .rhel_shell import RHELShell

if TYPE_CHECKING:
    from .unified_sim import UnifiedSimulationEngine

_MARKER_PATHS: dict[str, str] | None = None


def _marker_paths_by_slug() -> dict[str, str]:
    global _MARKER_PATHS
    if _MARKER_PATHS is not None:
        return _MARKER_PATHS
    import importlib.util
    from pathlib import Path

    e2e_path = Path(__file__).resolve().parents[5] / "scripts" / "e2e_simulation_fix.py"
    spec = importlib.util.spec_from_file_location("e2e_simulation_fix", e2e_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _MARKER_PATHS = dict(mod._RS_MARKER_FIX)
    return _MARKER_PATHS

CANONICAL_NGINX_CHECK = """#!/bin/bash
nginx -t 2>/dev/null
pgrep -x nginx
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80)
exit 0
"""

CANONICAL_NGINX_ROOT_CHECK = """#!/bin/bash
nginx -t 2>/dev/null
grep -q 'root /var/www/html' /etc/nginx/sites-enabled/default
pgrep -x nginx
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:80)
exit 0
"""

CANONICAL_USERADD_CHECK = """#!/bin/bash
pwck
getent passwd appuser
exit 0
"""

CANONICAL_GPU_CHECK = """#!/bin/bash
nvidia-smi
exit 0
"""

CANONICAL_MYSQL_CHECK = """#!/bin/bash
systemctl is-active mysqld
mysqladmin ping
exit 0
"""

CANONICAL_POSTGRES_CHECK = """#!/bin/bash
systemctl is-active postgresql
exit 0
"""

CANONICAL_K8S_POD_CHECK = """#!/bin/bash
kubectl get pods | grep -q Running
exit 0
"""

CANONICAL_K8S_ENDPOINTS_CHECK = """#!/bin/bash
kubectl get endpoints api -o jsonpath='{.subsets[*].addresses[*].ip}'
exit 0
"""

CANONICAL_ANSIBLE_CHECK = """#!/bin/bash
ansible webservers -m ping
exit 0
"""

CANONICAL_FIREWALL_CHECK = """#!/bin/bash
firewall-cmd --list-ports | grep -q 80/tcp
pgrep -x nginx
exit 0
"""

CANONICAL_DOCKER_CHECK = """#!/bin/bash
systemctl is-active docker
docker ps | grep -q Up
exit 0
"""

CANONICAL_PYTHON_CHECK = """#!/bin/bash
python3 -m py_compile /opt/app/main.py
exit 0
"""

CANONICAL_SHELL_CHECK = """#!/bin/bash
bash -n /opt/scripts/deploy.sh
exit 0
"""

CANONICAL_LVM_CHECK = """#!/bin/bash
pvs | grep -q /dev/sdb
lvs
exit 0
"""

CANONICAL_INITRAMFS_CHECK = """#!/bin/bash
dracut -f
exit 0
"""

CANONICAL_GRUB_CHECK = """#!/bin/bash
grub2-mkconfig
exit 0
"""

CANONICAL_PATCHING_CHECK = """#!/bin/bash
/opt/fixitlab/precheck.sh
dnf update -y
reboot
uname -r
/opt/fixitlab/postcheck.sh
exit 0
"""

CANONICAL_NETWORK_NIC_CHECK = """#!/bin/bash
ip addr show dev eth0 | grep -q 10.0.0.20
exit 0
"""

CANONICAL_BAREMETAL_CHECK = """#!/bin/bash
ipmitool power status | grep -qi on
exit 0
"""

CANONICAL_SSHD_CHECK = """#!/bin/bash
systemctl is-active sshd
exit 0
"""

CANONICAL_LDCONFIG_CHECK = """#!/bin/bash
ldconfig -p 2>/dev/null | grep -q libfixit
/usr/local/bin/myapp
exit 0
"""

CANONICAL_TERRAFORM_CHECK = """#!/bin/bash
terraform validate
exit 0
"""

CANONICAL_WINDOWS_CHECK = """#!/bin/bash
Get-Service
exit 0
"""

CANONICAL_DEVOPS_CHECK = """#!/bin/bash
gitlab-runner status
helm history webapp
exit 0
"""

CANONICAL_NETWORKING_CHECK = """#!/bin/bash
vtysh -c "show ip bgp summary"
chronyc tracking
exit 0
"""


def is_trivial_validation_script(script: str) -> bool:
    """True when script would always pass without checking lab state."""
    substantive: list[str] = []
    for line in (script or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped in ("true", ":", "exit 0", "exit 0;"):
            continue
        if stripped.startswith("exit ") and stripped.split()[1] == "0":
            continue
        substantive.append(stripped)
    return len(substantive) == 0


def resolve_simulation_validation_script(scenario_slug: str, validation_script: str) -> str:
    """Replace stub check.sh content with real validation rules."""
    script = (validation_script or "").strip()
    if not is_trivial_validation_script(script):
        return script
    slug = (scenario_slug or "").lower()
    # Order matters: specific technology markers are matched BEFORE generic
    # substring rules. Otherwise "ci-pipeline" matches the "pip" python rule,
    # "terraform-state" never reaches its rule, etc.
    rules: list[tuple[Any, str]] = [
        # --- Specific technology families (checked first) ---
        (lambda s: "devops-" in s or "ci-pipeline" in s or "helm-release" in s or "helm-" in s or "gitlab" in s, CANONICAL_DEVOPS_CHECK),
        (lambda s: "networking-" in s or "bgp" in s or "ntp-drift" in s, CANONICAL_NETWORKING_CHECK),
        (lambda s: (
            ("terraform" in s or s.startswith("iac-") or "aws-" in s or "cloudwatch" in s
             or "lambda" in s or "s3-" in s or "eks" in s or "iam-" in s or "ec2-" in s
             or "elb" in s or "ecr" in s or "rds" in s or "vpc" in s or "kinesis" in s
             or "sqs" in s or "secrets-manager" in s)
            and not s.startswith("academy-aws-")
        ), CANONICAL_TERRAFORM_CHECK),
        (lambda s: "windows" in s or "win-" in s or "iis" in s or "hyper-v" in s or "kerberos" in s or "gpo" in s or "ntfs" in s or "smb-" in s or "winrm" in s or "wmi" in s or "sql-server" in s or "dhcp-" in s or "replication-" in s or "dns-zone" in s, CANONICAL_WINDOWS_CHECK),
        (lambda s: "ldconfig" in s or "missing-library" in s, CANONICAL_LDCONFIG_CHECK),
        # --- Generic Linux/infra rules ---
        (lambda s: "nginx" in s and ("root" in s or "html" in s), CANONICAL_NGINX_ROOT_CHECK),
        (lambda s: "nginx" in s or ("firewall" in s and "nginx" in s), CANONICAL_NGINX_CHECK),
        (lambda s: "useradd" in s or "broken-user" in s, CANONICAL_USERADD_CHECK),
        (lambda s: "gpu" in s or "nvidia" in s, CANONICAL_GPU_CHECK),
        (lambda s: "mysql" in s, CANONICAL_MYSQL_CHECK),
        (lambda s: "postgres" in s, CANONICAL_POSTGRES_CHECK),
        (lambda s: "endpoint" in s or "service-not-ready" in s, CANONICAL_K8S_ENDPOINTS_CHECK),
        (lambda s: "pod" in s or "crashloop" in s or "k8s" in s or "kubernetes" in s, CANONICAL_K8S_POD_CHECK),
        (lambda s: "ansible" in s, CANONICAL_ANSIBLE_CHECK),
        (lambda s: "firewall" in s or "firewalld" in s, CANONICAL_FIREWALL_CHECK),
        (lambda s: "docker" in s, CANONICAL_DOCKER_CHECK),
        (lambda s: "pip-" in s or "-pip" in s or ("python" in s and "shell" not in s), CANONICAL_PYTHON_CHECK),
        (lambda s: "bash" in s or "shell-script" in s or "unbound" in s, CANONICAL_SHELL_CHECK),
        (lambda s: "lvm" in s, CANONICAL_LVM_CHECK),
        (lambda s: "network-nic" in s, CANONICAL_NETWORK_NIC_CHECK),
        (lambda s: "initramfs" in s or "dracut" in s, CANONICAL_INITRAMFS_CHECK),
        (lambda s: "grub" in s or "mbr" in s or "kernel-panic" in s or "kernel" in s or "boot" in s, CANONICAL_GRUB_CHECK),
        (lambda s: "patch" in s, CANONICAL_PATCHING_CHECK),
        (lambda s: "ssh-stop" in s or "sshd-down" in s, CANONICAL_SSHD_CHECK),
        (lambda s: "ipmi" in s or "baremetal" in s or s.startswith("sim-bm-") or s.startswith("sim-vmware-guest"), CANONICAL_BAREMETAL_CHECK),
    ]
    for pred, canonical in rules:
        try:
            if pred(slug):
                return canonical
        except TypeError:
            continue
    return script


def validate_simulation_state(
    state: RHELOSState,
    script: str,
    engine: UnifiedSimulationEngine | None = None,
) -> tuple[bool, str]:
    """Run simplified validation checks against in-memory OS state."""
    script = (script or "").strip()
    if not script or is_trivial_validation_script(script):
        return False, "Validation not configured — fix the scenario before checking"

    # ── Marker-fix scenarios are authoritative & fail-closed (audit P0-1) ──
    # Scenarios whose documented remediation is "apply the fix and append the
    # FIXED-OK sentinel to a specific file" are registered in the e2e marker-fix
    # map. Validate them ONLY by that sentinel: this keeps them fail-closed on
    # the broken state AND on a "touched the file without the sentinel" shortcut,
    # and stops a coarse/`exit 0` check.sh from auto-passing regardless of topic.
    _mslug = (getattr(state, "scenario_slug", "") or "").strip()
    if _mslug:
        _marker_path = _marker_paths_by_slug().get(_mslug)
        if _marker_path:
            _content = state.read_file(_marker_path) or ""
            if "FIXED-OK" in _content:
                return True, "Lab validation passed (documented fix applied)"
            return False, (
                f"{_marker_path} not corrected — apply the documented remediation "
                "and append the FIXED-OK marker, then re-run Check Solution"
            )

    shell = RHELShell(state=state)
    failures: list[str] = []
    checks_run = 0

    for line in script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("echo "):
            continue
        # Skip shell block keywords. Match the `fi` keyword exactly — NOT a prefix
        # — so real check commands like `firewall-cmd ...` or `find ...` are not
        # silently dropped (which would make the lab pass fail-open).
        if (
            stripped.startswith("if ")
            or stripped.startswith("then")
            or stripped == "fi"
            or stripped.startswith("fi ")
            or stripped.startswith("fi;")
        ):
            continue
        if stripped.startswith("exit "):
            code = stripped.split()[1].rstrip(";")
            if code == "0":
                break
            # Conditional exit (e.g. inside if [ $? -ne 0 ]) — only fail when a check failed
            if failures:
                return False, failures[0]
            continue

        if "|| exit" in stripped:
            cmd = stripped.split("||")[0].strip()
            if cmd.startswith("[") and cmd.endswith("]"):
                continue
            if _run_line_check(cmd, state, shell, engine, failures):
                checks_run += 1
            continue

        if _run_line_check(stripped, state, shell, engine, failures):
            checks_run += 1
        elif "sim-valid" in stripped:
            continue

    if checks_run == 0:
        return False, "No validation checks matched this simulation script"
    if failures:
        return False, failures[0]

    # Engine-driven repairs (terraform_fixed, Windows GUI, helm/k8s/networking
    # state) do not rewrite planted academy sentinels. Honor those flags and
    # skip the sweep for non-academy heroes so CrossTech / helm / MTU labs can
    # pass after a real engine fix. Academy packs still require FIXED-OK below.
    if getattr(state, "terraform_fixed", False) or getattr(state, "windows_fixed", False):
        return True, "Lab validation passed"

    slug = (getattr(state, "scenario_slug", "") or "").strip()
    low = slug.lower()
    # Engine-driven heroes heal in-memory state (VMware node join, helm rollback,
    # MTU/BGP/NTP) without rewriting planted FIXED-OK sentinels — skip the sweep.
    _engine_hero = (
        (low.startswith("k8s-") and "vmware" in low)
        or low.startswith(("networking-bgp", "networking-ntp", "networking-mtu"))
        or low.startswith(("devops-helm", "devops-ci-pipeline"))
        or low.startswith("k8s-crashloop")
    )
    if _engine_hero:
        return True, "Lab validation passed"

    # ── Fail-closed sweep for preset-planted broken config files ──
    # Hundreds of scenario presets plant a file whose content is the sentinel
    # "# broken configuration for <slug>". Many of those scenarios ship a
    # check.sh that only probes a coarse health flag (e.g. `nvidia-smi`,
    # `docker ps`) which is healthy by default — so the lab auto-passed without
    # any fix. As long as the planted file still carries the sentinel for THIS
    # scenario, the incident is by definition unresolved: fail with a pointer
    # to the exact file the learner must repair.
    if slug:
        sentinel = f"# broken configuration for {slug}"
        for path, node in state.vfs.items():
            if not isinstance(node, dict) or node.get("type") != "file":
                continue
            content = node.get("content") or ""
            # FIXED-OK anywhere in the file counts as repaired (marker labs let
            # the learner append the sentinel fix rather than rewrite the file).
            if sentinel in content and "FIXED-OK" not in content:
                return False, (
                    f"{path} still contains the broken configuration — edit the file "
                    "and apply the documented fix, then re-run Check Solution"
                )
    return True, "Lab validation passed"


def _run_line_check(
    stripped: str,
    state: RHELOSState,
    shell: RHELShell,
    engine: Any,
    failures: list[str],
) -> bool:
    """Return True if this line was recognized as a validation check."""
    # ── Config-repair marker (grep -q FIXED-OK <file>) runs FIRST ──
    # The marker file path can contain tech keywords (e.g. an academy GPU lab's
    # path holds "nvidia-smi", a docker lab's holds "docker"), which would
    # otherwise be grabbed by a substring matcher below (gpu_healthy, etc.) and
    # auto-pass. Handle the unambiguous marker line up front so it stays
    # fail-closed until the file genuinely carries the FIXED-OK sentinel.
    if "grep" in stripped and "FIXED-OK" in stripped:
        path = next((p for p in stripped.split() if p.startswith("/")), "")
        content = state.read_file(path) if path else None
        if content is None or "FIXED-OK" not in content:
            failures.append(f"{path or 'target file'} not corrected — apply the documented fix")
        return True

    # ── Cross-technology (VMware ⇄ terminal) checks run FIRST ──
    # These scenarios reuse common probes (systemctl is-active nginx, ip addr)
    # whose generic handlers appear later in this function; running the cross-tech
    # logic up front keeps the bridge semantics (fail-closed until the VMware
    # action + terminal fix) from being shadowed.
    _xslug0 = (getattr(state, "scenario_slug", "") or "").lower()
    if _xslug0.startswith("linux-server-hung-needs-vmware-reset") and (
        "is-active nginx" in stripped or "uptime" in stripped or "pgrep" in stripped
    ):
        if state.recover_from_vmware_reset() and "nginx" in state.services:
            state.services["nginx"].active = "active"
            state.services["nginx"].sub_state = "running"
        if getattr(state, "server_hung", False):
            failures.append("guest is hung — reset web-prod-01 from the VMware simulator (Power → Reset)")
        else:
            nginx = state.services.get("nginx")
            if not nginx or nginx.active != "active":
                failures.append("nginx not running after reset — start it from the recovered terminal")
        return True
    if _xslug0 == "linux-nic-add-vmware-rescan" and ("ip addr" in stripped or "10.0.0.30" in stripped):
        if "10.0.0.30" not in state.format_ip_addr():
            failures.append(
                "secondary interface not up — add a NIC in VMware, rescan, then configure 10.0.0.30/24"
            )
        return True

    # ── Cross-technology Kubernetes-on-VMware (worker node is a VMware VM) ──
    # Fail-closed chain: a worker node only becomes Ready / pods only schedule
    # once the matching VMware VM is powered on / created / reset. We re-fold the
    # bridge state here (validation may run in a worker that never issued kubectl)
    # so `kubectl get nodes|pods|hpa` reflects the genuine VMware action.
    try:
        from .vmware_bridge import is_k8s_cross_tech_scenario as _is_k8s_xtech
    except Exception:
        _is_k8s_xtech = lambda _s: False  # noqa: E731
    if _is_k8s_xtech(_xslug0) and (
        "kubectl get nodes" in stripped or "kubectl get pods" in stripped
        or "kubectl get hpa" in stripped or "kubectl get ds" in stripped
        or "kubectl get daemonset" in stripped
    ):
        cluster = engine.cluster if engine else None
        if cluster is None:
            failures.append("kubernetes cluster not available")
            return True
        if not getattr(cluster, "session_id", ""):
            cluster.session_id = getattr(state, "session_id", "") or ""
        cluster.sync_from_vmware_bridge()
        node = (getattr(cluster, "_xtech", None) or {}).get("node", "the worker")
        kind = (getattr(cluster, "_xtech", None) or {}).get("kind", "add")
        if "kubectl get nodes" in stripped and "Ready" in stripped:
            if any(n.status != "Ready" for n in cluster.nodes):
                if kind == "reset":
                    failures.append(f"{node} still NotReady — reset its VM in the VMware simulator")
                else:
                    failures.append(f"{node} not joined — power on its worker VM in the VMware simulator")
            return True
        if "kubectl get hpa" in stripped:
            unsatisfied = [h for h in cluster.hpas if h.current_replicas < h.desired_replicas]
            if unsatisfied:
                failures.append("HPA not satisfied — add a worker node in VMware so the extra pods schedule")
            elif not cluster.is_healthy():
                failures.append("cluster not healthy — ensure all pods are Running across the nodes")
            return True
        if "kubectl get ds" in stripped or "kubectl get daemonset" in stripped:
            if any(p.status != "Running" for p in cluster.pods if p.owner in
                   {d.name for d in getattr(cluster, "daemonsets", [])}):
                failures.append("DaemonSet pod Pending — power on the worker VM in VMware so it gets a node")
            return True
        # kubectl get pods | grep Running
        if any(p.status != "Running" for p in cluster.pods):
            failures.append("pods still Pending — add/recover the worker node VM in the VMware simulator")
        elif not cluster.is_healthy():
            failures.append("cluster not healthy yet — complete the node + scheduling fix")
        return True

    if stripped.startswith("HTTP_CODE=") or stripped.startswith("HTTP_CODE=$(curl"):
        code = _curl_http_code(state)
        if code != "200":
            failures.append(f"nginx not responding on port 80 (got HTTP {code})")
        return True

    if "grep" in stripped and "root /var/www/html" in stripped:
        sites = state.read_file("/etc/nginx/sites-enabled/default") or ""
        if "root /var/www/html" not in sites:
            failures.append("nginx document root must be /var/www/html")
        return True

    if "nginx -t" in stripped:
        out = shell.run("nginx -t")
        if "test is successful" not in out:
            failures.append("nginx configuration is invalid")
        return True

    if "pgrep -x nginx" in stripped or "pgrep nginx" in stripped:
        nginx = state.services.get("nginx")
        if not nginx or nginx.active != "active":
            failures.append("nginx is not running")
        return True

    if "systemctl is-active nginx" in stripped:
        nginx = state.services.get("nginx")
        if not nginx or nginx.active != "active":
            failures.append("nginx service inactive")
        return True

    if "getent passwd" in stripped:
        parts = stripped.split()
        # The username is the first token after the db keyword that isn't a
        # flag, a getent database keyword, or a shell redirect/operator token.
        # A trailing redirect like `getent passwd appuser 2>&1` must NOT be
        # mistaken for the username (that produced spurious "user '2>&1' not
        # found" grader failures).
        user = ""
        for tok in parts:
            if tok in ("getent", "passwd", "group", "shadow"):
                continue
            if tok.startswith("-"):
                continue
            if any(c in tok for c in "<>|&;") or tok in ("2>&1", "1>&2"):
                continue
            user = tok
            break
        if user:
            passwd = state.read_file("/etc/passwd") or ""
            if not any(line.startswith(f"{user}:") for line in passwd.splitlines()):
                failures.append(f"user '{user}' not found — complete the lab objective")
            return True

    if stripped.startswith("test -f ") or stripped.startswith("test -d "):
        is_dir = stripped.startswith("test -d ")
        path = stripped.split(maxsplit=2)[-1].strip()
        node = state.vfs.get(path)
        if node is None:
            failures.append(f"{'directory' if is_dir else 'file'} {path} does not exist yet")
            return True
        if is_dir and not isinstance(node, dict):
            failures.append(f"{path} is not a directory")
        elif not is_dir and isinstance(node, dict):
            failures.append(f"{path} is a directory, expected a file")
        return True

    if "[ -f " in stripped or "[ -d " in stripped:
        is_dir = "[ -d " in stripped
        path = stripped.split("[ -", 1)[-1].split("]", 1)[0]
        path = path.lstrip("fd ").strip()
        node = state.vfs.get(path)
        if node is None:
            failures.append(f"{'directory' if is_dir else 'file'} {path} does not exist yet")
            return True
        return True

    if "pwck" in stripped:
        out = shell.run("pwck")
        if out and "no errors" not in out.lower():
            failures.append(out)
        return True

    if "nvidia-smi" in stripped:
        slug = (getattr(state, "scenario_slug", "") or "").strip()
        if slug:
            marker_path = _marker_paths_by_slug().get(slug)
            if marker_path:
                content = state.read_file(marker_path) or ""
                if "FIXED-OK" in content:
                    return True
                if f"# broken configuration for {slug}" in content:
                    failures.append(f"{marker_path} not corrected — apply the documented fix")
                    return True
        # Fail-closed: a scenario only passes when the fix genuinely marked the
        # GPU healthy. An uninitialised flag must NOT count as resolved.
        if not getattr(state, "gpu_healthy", False):
            failures.append("GPU still unhealthy — load the nvidia driver first")
        return True

    if "systemctl is-active mysqld" in stripped or "systemctl is-active mysql" in stripped:
        slug = (getattr(state, "scenario_slug", "") or "").strip()
        if slug:
            marker_path = _marker_paths_by_slug().get(slug)
            if marker_path:
                content = state.read_file(marker_path) or ""
                if "FIXED-OK" in content:
                    return True
                if f"# broken configuration for {slug}" in content:
                    failures.append(f"{marker_path} not corrected — apply the documented fix")
                    return True
        svc = state.services.get("mysqld") or state.services.get("mysql")
        if not svc or svc.active != "active":
            failures.append("mysqld is not running")
        return True

    if "mysqladmin" in stripped and "ping" in stripped:
        svc = state.services.get("mysqld") or state.services.get("mysql")
        if not svc or svc.active != "active":
            failures.append("mysqladmin: connect to server failed")
        return True

    if "systemctl is-active postgresql" in stripped:
        svc = state.services.get("postgresql")
        if not svc or svc.active != "active":
            failures.append("postgresql is not running")
        return True

    if "systemctl is-active docker" in stripped and "docker-" not in stripped.split("is-active", 1)[-1]:
        svc = state.services.get("docker")
        if not svc or svc.active != "active":
            failures.append("docker service is not running")
        return True

    if "docker ps" in stripped:
        slug = (getattr(state, "scenario_slug", "") or "").strip()
        if slug:
            marker_path = _marker_paths_by_slug().get(slug)
            if marker_path:
                content = state.read_file(marker_path) or ""
                if "FIXED-OK" in content:
                    return True
                if f"# broken configuration for {slug}" in content:
                    failures.append(f"{marker_path} not corrected — apply the documented fix")
                    return True
        running = engine and getattr(engine, "_container_running", False)
        if not running:
            failures.append("no running docker containers")
        return True

    if "kubectl get pods" in stripped and "Running" in stripped:
        slug = (getattr(state, "scenario_slug", "") or "").strip()
        if slug:
            marker_path = _marker_paths_by_slug().get(slug)
            if marker_path:
                content = state.read_file(marker_path) or ""
                if "FIXED-OK" in content:
                    return True
                if f"# broken configuration for {slug}" in content:
                    failures.append(f"{marker_path} not corrected — apply the documented fix")
                    return True
        cluster = engine.cluster if engine else None
        if not cluster:
            failures.append("kubernetes cluster not available")
        elif not all(p.status == "Running" for p in cluster.pods):
            failures.append("not all pods are Running")
        elif not cluster.is_healthy():
            failures.append("kubernetes cluster is not healthy — apply the required fix")
        return True

    if "kubectl get nodes" in stripped and "Ready" in stripped:
        cluster = engine.cluster if engine else None
        if not cluster or any(n.status != "Ready" for n in cluster.nodes):
            failures.append("not all nodes are Ready")
        return True

    if "kubectl get endpoints" in stripped:
        cluster = engine.cluster if engine else None
        if not cluster:
            failures.append("kubernetes cluster not available")
        else:
            for svc in cluster.services:
                if svc.name in stripped or "api" in stripped:
                    if not svc.endpoints:
                        failures.append(f"service {svc.name} has no endpoints")
        return True

    if "ansible" in stripped and "ping" in stripped:
        slug = (getattr(state, "scenario_slug", "") or "").strip()
        if slug:
            sentinel = f"# broken configuration for {slug}"
            for path, node in state.vfs.items():
                if not isinstance(node, dict) or node.get("type") != "file":
                    continue
                content = node.get("content") or ""
                if sentinel in content:
                    if "FIXED-OK" not in content:
                        failures.append(f"{path} not corrected — apply the documented fix")
                    return True
        # Fail-closed: without an engine we cannot prove SSH keys were distributed.
        if engine is None:
            failures.append("ansible lab engine unavailable — cannot verify host reachability")
            return True
        if not getattr(engine, "_ssh_key_fixed", False):
            failures.append("ansible hosts unreachable — distribute SSH keys first")
            return True
        # Playbook-oriented labs must actually succeed a playbook run, not just ping.
        if "playbook" in stripped or getattr(engine, "_ansible_requires_playbook", False):
            if not getattr(engine, "_ansible_playbook_ok", False):
                failures.append("ansible-playbook has not completed successfully yet")
        return True

    if "firewall-cmd --list-ports" in stripped or ("80/tcp" in stripped and "firewall" in stripped):
        if not state.firewall.is_port_open(80):
            failures.append("port 80 not open in firewall")
        return True

    if "firewall-cmd --state" in stripped:
        slug = (getattr(state, "scenario_slug", "") or "").strip()
        if slug:
            marker_path = _marker_paths_by_slug().get(slug)
            if marker_path:
                content = state.read_file(marker_path) or ""
                if "FIXED-OK" in content:
                    return True
                if f"# broken configuration for {slug}" in content:
                    failures.append(f"{marker_path} not corrected — apply the documented fix")
                    return True
        # Match check.sh: `firewall-cmd --state | grep -q running` — do not
        # auto-pass when firewalld is failed/stopped (grader-integrity fail-open).
        fw = (getattr(state, "services", {}) or {}).get("firewalld")
        active = (getattr(fw, "active", None) or "").strip().lower() if fw is not None else ""
        if active not in ("active", "running"):
            failures.append("firewalld is not running")
            return True
        return True

    if "python3 -m py_compile" in stripped or "py_compile" in stripped:
        path = "/opt/app/main.py"
        if "main.py" in stripped:
            for part in stripped.split():
                if part.endswith(".py"):
                    path = part
                    break
        content = state.read_file(path)
        if content is None:
            failures.append(f"{path} does not exist — create a valid Python program first")
        else:
            # Actually compile the file (don't just look for the literal text
            # "SyntaxError") so a genuinely broken program stays fail-closed.
            try:
                compile(content, path, "exec")
            except (SyntaxError, ValueError):
                failures.append(f"syntax error in {path}")
        return True

    if "bash -n" in stripped:
        path = "/opt/scripts/deploy.sh"
        for part in stripped.split():
            if part.endswith(".sh"):
                path = part
                break
        content = state.read_file(path)
        if content is None:
            failures.append(f"{path} does not exist — create a valid shell script first")
        elif "$" in content and "set -u" in content and ":-}" not in content:
            failures.append(f"unbound variable risk in {path}")
        return True

    # ── Cross-technology VMware-disk LVM extend (rescan / reboot / datastore) ──
    # Fail-closed chain: the disk must be (1) added in VMware → revealed in the
    # guest (visible /dev/sdc), (2) initialised as a PV inside vgdata, and (3) the
    # lvdata LV genuinely grown past its original 20G. Any earlier step missing
    # keeps the check failing.
    _xslug = (state.scenario_slug or "").lower()
    _IS_CROSS_LVM = _xslug in (
        "linux-lvm-extend-vmware-disk-rescan",
        "linux-lvm-extend-vmware-disk-reboot",
        "linux-datastore-full-add-disk-vmware",
    )
    if _IS_CROSS_LVM and ("lvextend" in stripped or "lvs" in stripped or "vgs" in stripped
                          or ("pvs" in stripped and ("sdc" in stripped or "vgdata" in stripped))):
        from .lvm_state import LVMState
        sdc = state.find_block_device("/dev/sdc")
        pv = state.lvm.pvs.get("/dev/sdc")
        lv = state.lvm.lvs.get("vgdata/lvdata")
        if sdc is None:
            failures.append("/dev/sdc not visible — add a disk in VMware, then rescan the SCSI bus (or reboot)")
        elif not pv or pv.vg != "vgdata":
            failures.append("/dev/sdc not added to vgdata — pvcreate /dev/sdc && vgextend vgdata /dev/sdc")
        elif not lv or LVMState._size_to_kb(lv.size) <= LVMState._size_to_kb("20.00g"):
            failures.append("lvdata not extended — lvextend -r -l +100%FREE /dev/vgdata/lvdata")
        return True

    if "lvextend" in stripped or ("pvs" in stripped and "sdb" in stripped):
        slug = (state.scenario_slug or "").lower()
        if "grow-xfs" in slug and "lvextend" in stripped and "vgdata/lvdata" in stripped:
            from .lvm_state import LVMState

            lv = state.lvm.lvs.get("vgdata/lvdata")
            if not lv or LVMState._size_to_kb(lv.size) <= LVMState._size_to_kb("20.00g"):
                failures.append("lvdata not extended — lvextend -l +100%FREE /dev/vgdata/lvdata")
            fstab = state.read_file("/etc/fstab") or ""
            if "FIXED-OK" not in fstab:
                failures.append("/etc/fstab not marked fixed — run xfs_growfs /data after lvextend")
            return True
        if "lvm" in slug and not getattr(state, "storage_disk_provisioned", False):
            failures.append("new disk not attached — request @storage team in Jira")
            return True
        pv = state.lvm.pvs.get("/dev/sdb")
        if pv and not pv.vg:
            failures.append("PV /dev/sdb not in volume group")
        return True

    if "ip addr" in stripped or "10.0.0.20" in stripped:
        slug = (state.scenario_slug or "").lower()
        if "network-nic" in slug:
            if not getattr(state, "network_nic_provisioned", False):
                failures.append("secondary IP not provisioned — request @network team in Jira")
            elif "10.0.0.20" not in state.format_ip_addr():
                failures.append("secondary IP 10.0.0.20 not visible on eth0")
            return True

    if "dracut" in stripped:
        boot = getattr(engine, "boot", None) if engine else None
        fixed = getattr(state, "initramfs_fixed", False) or (boot and boot.initramfs_fixed)
        if not fixed:
            failures.append("initramfs not regenerated")
        return True

    if "grub2-mkconfig" in stripped or "grub-mkconfig" in stripped:
        boot = getattr(engine, "boot", None) if engine else None
        fixed = (
            getattr(state, "grub_fixed", False)
            or getattr(state, "mbr_fixed", False)
            or getattr(state, "kernel_fixed", False)
            or (boot and (boot.grub_fixed or boot.mbr_fixed or boot.kernel_fixed))
        )
        # Fail-closed: only treat the boot issue as resolved when a fix flag is
        # set OR the machine has actually reached a shell/login prompt. A missing
        # boot object must NOT be read as "already fixed".
        booted_through = bool(boot and boot.phase in ("shell", "login"))
        if not fixed and not booted_through:
            failures.append("boot issue not resolved")
        return True

    if "dnf check-update" in stripped or "yum check-update" in stripped:
        if not getattr(state, "patching_done", False):
            failures.append("system patching not completed")
        return True

    if "precheck.sh" in stripped or "/opt/fixitlab/precheck" in stripped:
        slug = (state.scenario_slug or "").lower()
        if "patch" in slug:
            from .ops_state import ops_ready_for_patching
            if not ops_ready_for_patching(state):
                failures.append(
                    "change window not ready — coordinate @backup @database @application teams in Jira first"
                )
                return True
        if not getattr(state, "precheck_ran", False):
            failures.append("precheck script was not run")
        return True

    if "postcheck.sh" in stripped or "/opt/fixitlab/postcheck" in stripped:
        slug = (state.scenario_slug or "").lower()
        if "patch" in slug and not getattr(state, "ops_services_restarted", False):
            failures.append(
                "services not restored — ask @database team and @application team to start in Jira"
            )
            return True
        if not getattr(state, "postcheck_ran", False):
            failures.append("postcheck script was not run")
        return True

    if stripped.startswith("uname -r") or "uname -r" in stripped:
        from .boot_sequence import NEW_KERNEL
        if not getattr(state, "rebooted_after_patch", False):
            failures.append("system was not rebooted after patching")
            return True
        if state.kernel != NEW_KERNEL:
            failures.append(f"expected kernel {NEW_KERNEL}, got {state.kernel}")
        return True

    if "dnf update" in stripped or "yum update" in stripped:
        if not getattr(state, "patching_done", False):
            failures.append("dnf update was not applied")
        return True

    if stripped == "reboot" or stripped.endswith(" reboot"):
        if not getattr(state, "rebooted_after_patch", False):
            failures.append("reboot after patching required")
        return True

    if "ipmitool power status" in stripped:
        power = getattr(engine, "_power_state", "on") if engine else "on"
        if str(power).lower() not in ("on", "up"):
            failures.append("host power is off")
        return True

    if "is-active sshd" in stripped or "systemctl is-active sshd" in stripped:
        svc = state.services.get("sshd")
        if not svc or svc.active != "active":
            failures.append("sshd is not active")
        return True

    if "terraform" in stripped or stripped.startswith("aws "):
        # Fail-closed: any terraform/aws validation line requires the fix flag.
        # Previously this only enforced the flag when the slug matched a hard-coded
        # keyword list, so terraform scenarios with other slugs passed for free.
        if not getattr(state, "terraform_fixed", False):
            failures.append("Terraform/AWS issue not resolved — apply the required fix first")
        return True

    # Unambiguous Windows-only tokens (PowerShell cmdlets / net / wmic). Cross-platform
    # commands like netstat/ipconfig are intentionally excluded so Linux checks that use
    # them are not mis-routed here.
    if any(cmd in stripped for cmd in ("Get-Service", "Get-Website", "Start-WebAppPool", "Start-Website", "Get-EventLog", "Get-Process", "Set-Service", "Restart-Service", "Get-NetAdapter", "Get-ADUser", "net user", "net localgroup", "wmic", "Get-WindowsFeature", "sc.exe")):
        if not getattr(state, "windows_fixed", False):
            failures.append("Windows issue not resolved — apply the required fix first")
        return True

    # Dedicated devops probe (`gitlab-runner status` / pipeline status). Do NOT
    # hijack `systemctl is-active gitlab-runner` — that is a real unit grade used
    # by topic_faults academy CI labs.
    if "systemctl is-active" not in stripped and (
        "gitlab-runner status" in stripped
        or ("pipeline" in stripped and "status" in stripped)
    ):
        devops = getattr(engine, "devops", None) if engine else None
        if not devops or not devops.is_healthy():
            failures.append("CI/CD pipeline not healthy — fix KUBECONFIG and redeploy")
        return True

    if "helm history" in stripped:
        devops = getattr(engine, "devops", None) if engine else None
        if not devops or devops.helm_release_status != "deployed":
            failures.append("Helm release stuck — rollback to a deployed revision")
        return True

    if "bgp summary" in stripped or "show ip bgp" in stripped:
        net = getattr(engine, "networking", None) if engine else None
        if not net or any(n["state"] != "Established" for n in net.bgp_neighbors):
            failures.append("BGP session not established")
        return True

    # ── Interface MTU aligned to the path (ip link show … mtu 1500) ──
    # Fail-closed: a jumbo-misconfigured interface (mtu 9000 on a 1500 path)
    # must not pass until the MTU is corrected back to the path value.
    if ("ip link show" in stripped or "ip -d link" in stripped) and "mtu 1500" in stripped:
        net = getattr(engine, "networking", None) if engine else None
        if net is not None and getattr(net, "interface_mtu", 1500) != 1500:
            failures.append("interface MTU mismatch — align it to the path MTU (1500)")
        return True

    if "chronyc tracking" in stripped or "ntpq" in stripped:
        net = getattr(engine, "networking", None) if engine else None
        if not net or not net.ntp_synced:
            failures.append("NTP not synchronized")
        return True

    if "/usr/local/bin/myapp" in stripped or ("ldconfig" in stripped and "libfixit" in stripped):
        working = getattr(state, "myapp_working", False) or getattr(state, "ldconfig_updated", False)
        if not working:
            conf = state.read_file("/etc/ld.so.conf.d/fixitlab.conf") or ""
            if "/usr/local/lib" not in conf:
                failures.append("FAIL: restore /etc/ld.so.conf.d/fixitlab.conf and run ldconfig")
        return True

    # ── SELinux: getenforce must stay Enforcing for the SELinux-port scenario ──
    if stripped == "getenforce" or stripped.endswith(" getenforce"):
        slug = (state.scenario_slug or "").lower()
        if "selinux" in slug and "port" in slug:
            if state.selinux_mode != "Enforcing":
                failures.append("SELinux must remain Enforcing — do not disable it to fix the port")
        return True

    # ── SELinux port label (semanage port -l | grep http_port_t ... 8080) ──
    if "semanage port" in stripped and "http_port_t" in stripped:
        ports = state.selinux_ports.get("http_port_t", [])
        if 8080 not in ports:
            failures.append("port 8080 not in http_port_t — semanage port -a -t http_port_t -p tcp 8080")
        return True

    # ── New block device discovered + formatted (blkid | grep /dev/sdc) ──
    if "blkid" in stripped and "/dev/sdc" in stripped:
        dev = state.find_block_device("/dev/sdc")
        if dev is None:
            failures.append("/dev/sdc not visible — rescan the SCSI bus first")
        elif not dev.fstype:
            failures.append("/dev/sdc has no filesystem — run mkfs on it")
        return True

    # ── LVM provisioned on /dev/sdc (pvs | grep /dev/sdc) ──
    # Fail-closed: the spare disk may be a known device, but it counts as solved
    # only once it has been initialised AND added to the new volume group.
    if "pvs" in stripped and "/dev/sdc" in stripped:
        pv = state.lvm.pvs.get("/dev/sdc")
        if not pv or not pv.vg:
            failures.append("/dev/sdc is not in a volume group — pvcreate then vgcreate vgdata /dev/sdc")
        return True

    # ── LVM logical volume created (lvs | grep lvdata) ──
    if "lvs" in stripped and "lvdata" in stripped:
        has_lv = any("lvdata" in name for name in state.lvm.lvs)
        if not has_lv:
            failures.append("logical volume lvdata not found — create it with lvcreate")
        return True

    # ── Filesystem mounted at /data (mount | grep /data) ──
    # Scoped to the new disk/LVM-creation scenarios. Other scenarios legitimately
    # use /data with their own mount model, so for them we must NOT recognize this
    # line (return False) or we'd turn a previously-ignored line into a failure.
    _slug = (getattr(state, "scenario_slug", "") or "").lower()
    _DATA_FS_SLUGS = ("lvm-create-mount", "disk-missing-rescan", "mkfs-mount")
    if "mount" in stripped and "/data" in stripped and "fstab" not in stripped:
        if not any(m in _slug for m in _DATA_FS_SLUGS):
            return False
        mounted = "/data" in state.mounts or any(
            d.mountpoint == "/data" for d in state.block_devices.values()
        )
        if not mounted:
            failures.append("/data is not mounted")
        return True

    # ── fstab persistence for /data (grep /data /etc/fstab) ──
    if "grep" in stripped and "/data" in stripped and "/etc/fstab" in stripped:
        if not any(m in _slug for m in _DATA_FS_SLUGS):
            return False
        fstab = state.read_file("/etc/fstab") or ""
        if "/data" not in fstab:
            failures.append("/data not in /etc/fstab — it will not remount on reboot")
        return True

    # ── Active swap (swapon --show | grep /dev/sdc…) ──
    if "swapon" in stripped and "/dev/sdc" in stripped:
        dev_path = "/dev/sdc1" if "/dev/sdc1" in stripped else "/dev/sdc"
        active = dev_path in state.swaps or any(
            p.startswith(dev_path) for p in state.swaps
        )
        if not active:
            failures.append(f"{dev_path} is not active swap — run mkswap then swapon")
        return True

    # ── fstab persistence for swap (grep swap /etc/fstab or grep /dev/sdc /etc/fstab) ──
    if "grep" in stripped and "/etc/fstab" in stripped and (
        "swap" in stripped or "/dev/sdc" in stripped
    ):
        fstab = state.read_file("/etc/fstab") or ""
        if "swap" not in fstab:
            failures.append("swap not in /etc/fstab — it will not activate on reboot")
        return True

    # ── Persistent default gateway (grep GATEWAY /etc/sysconfig/network) ──
    if "grep" in stripped and "GATEWAY" in stripped:
        net = state.read_file("/etc/sysconfig/network") or ""
        if "GATEWAY=" not in net:
            failures.append("no GATEWAY= line in /etc/sysconfig/network — default route not persisted")
        return True

    # ── Persistent sysctl ip_forward (sysctl net.ipv4.ip_forward) ──
    if "sysctl" in stripped and "ip_forward" in stripped:
        def _forward_enabled(content: str) -> bool:
            for raw in content.splitlines():
                line = raw.split("#", 1)[0].strip()
                if line.startswith("net.ipv4.ip_forward") and "=" in line:
                    if line.split("=", 1)[1].strip() == "1":
                        return True
            return False

        persisted = _forward_enabled(state.read_file("/etc/sysctl.conf") or "")
        # Any drop-in under /etc/sysctl.d that enables forwarding also counts.
        for path, node in state.vfs.items():
            if path.startswith("/etc/sysctl.d/") and isinstance(node, dict) and node.get("type") == "file":
                if _forward_enabled(node.get("content", "")):
                    persisted = True
        if not persisted:
            failures.append("net.ipv4.ip_forward not persistently set to 1 in sysctl config")
        return True

    # ── Kernel module persisted (grep -r br_netfilter /etc/modules-load.d) ──
    if "br_netfilter" in stripped and "modules-load.d" in stripped:
        loaded = False
        for path, node in state.vfs.items():
            if path.startswith("/etc/modules-load.d/") and isinstance(node, dict) and node.get("type") == "file":
                if "br_netfilter" in node.get("content", ""):
                    loaded = True
        if not loaded:
            failures.append("br_netfilter not configured to load at boot under /etc/modules-load.d")
        return True

    # ── Postgres max_connections raised above the broken default ──
    if "max_connections" in stripped and "postgresql.conf" in stripped:
        conf = state.read_file("/var/lib/pgsql/data/postgresql.conf") or ""
        value = None
        for line in conf.splitlines():
            if line.strip().startswith("max_connections"):
                try:
                    value = int(line.split("=", 1)[1].strip())
                except (ValueError, IndexError):
                    value = None
        if value is None or value <= 20:
            failures.append("max_connections still too low — raise it in postgresql.conf and restart")
        return True

    # ── MySQL crashed-table repair (mysqlcheck --check appdb orders) ──
    if "mysqlcheck" in stripped or ("appdb" in stripped and "orders" in stripped):
        if state.read_file("/var/lib/mysql/appdb/orders.CRASHED") is not None:
            failures.append("orders table still marked crashed — repair it before restarting mysqld")
        return True

    # ── Postgres WAL archive backlog cleared (ls /var/lib/pgsql/archive | grep wal) ──
    if "/var/lib/pgsql/archive" in stripped:
        backlog = [
            p for p, node in state.vfs.items()
            if p.startswith("/var/lib/pgsql/archive/") and isinstance(node, dict)
            and node.get("type") == "file" and p.endswith(".wal")
        ]
        if backlog:
            failures.append("stale archived WAL still present — reclaim disk space before restart")
        return True

    # ── systemctl is-failed (marker / config-repair labs) ──
    # check.sh pattern: `systemctl is-failed --quiet; test $? -ne 0` — pass only
    # when no units are failed AND no broken-configuration sentinel remains.
    if "systemctl is-failed" in stripped:
        if getattr(state, "terraform_fixed", False) or getattr(state, "windows_fixed", False):
            return True
        slug = (getattr(state, "scenario_slug", "") or "").strip()
        found_break = False
        if slug:
            sentinel = f"# broken configuration for {slug}"
            for path, node in state.vfs.items():
                if not isinstance(node, dict) or node.get("type") != "file":
                    continue
                content = node.get("content") or ""
                if sentinel in content and "FIXED-OK" not in content:
                    failures.append(
                        f"{path} still contains the broken configuration — edit the file "
                        "and apply the documented fix, then re-run Check Solution"
                    )
                    found_break = True
                    break
            marker_path = _marker_paths_by_slug().get(slug)
            if marker_path:
                marker_content = state.read_file(marker_path) or ""
                if "FIXED-OK" not in marker_content:
                    failures.append(f"{marker_path} not corrected — apply the documented fix")
                    found_break = True
        # Fail-closed: if check.sh only asks is-failed but the lab never planted
        # a break (common academy-aws gap), treat as still broken until FIXED-OK
        # exists on a topic file under /opt/fixitlab or /opt/aws.
        if not found_break and not failures:
            failed_units = [
                n for n, svc in (state.services or {}).items()
                if getattr(svc, "active", "") == "failed"
            ]
            if failed_units:
                failures.append(
                    f"failed units still present: {', '.join(failed_units[:5])} — repair and re-check"
                )
            else:
                # No failed units and no sentinel → previously auto-passed. Require
                # at least one FIXED-OK marker under /opt for academy packs.
                has_fixed = any(
                    isinstance(node, dict) and node.get("type") == "file"
                    and "FIXED-OK" in (node.get("content") or "")
                    for path, node in state.vfs.items()
                    if path.startswith("/opt/")
                )
                if not has_fixed and slug.startswith(("academy-", "aws-", "azure-", "gcp-")):
                    failures.append(
                        "lab issue not resolved yet — apply the documented fix "
                        "(append FIXED-OK to the broken config under /opt) then re-check"
                    )
        return True

    # ── Postgres readiness (pg_isready) ──
    if "pg_isready" in stripped:
        for path, node in state.vfs.items():
            if "postgresql.conf" not in path or not isinstance(node, dict):
                continue
            content = node.get("content") or ""
            if "# broken configuration" in content:
                if "FIXED-OK" not in content:
                    failures.append(f"{path} not corrected — apply the documented fix")
                return True
        pg = state.services.get("postgresql")
        if not pg or pg.active != "active":
            failures.append("postgresql is not accepting connections")
        return True

    # ── Secondary mount at /mnt/data2 (two-partition fdisk labs) ──
    if "mount" in stripped and "/mnt/data2" in stripped and "fstab" not in stripped:
        mounted = "/mnt/data2" in state.mounts or any(
            d.mountpoint == "/mnt/data2" for d in state.block_devices.values()
        )
        if not mounted:
            failures.append("/mnt/data2 is not mounted")
        return True
    if "grep" in stripped and "/mnt/data2" in stripped and "/etc/fstab" in stripped:
        fstab = state.read_file("/etc/fstab") or ""
        if "/mnt/data2" not in fstab:
            failures.append("/mnt/data2 not in /etc/fstab — it will not remount on reboot")
        return True

    # ── Generic service active check (any unit) — reads real service state.
    # Placed AFTER the specific service branches above so nginx/mysqld/etc keep
    # their tailored messages. Fail-closed: an inactive/missing unit fails.
    if stripped.startswith("systemctl is-active ") or " systemctl is-active " in stripped:
        parts = stripped.replace("systemctl is-active", "").split()
        unit = next((p for p in parts if not p.startswith("-")), "")
        unit = unit.replace(".service", "")
        if unit:
            svc = state.services.get(unit)
            if not svc or svc.active != "active":
                failures.append(f"{unit} is not active")
            return True

    # (The grep -q FIXED-OK marker check is handled at the top of this function
    # so tech keywords in the marker path can't shadow it.)
    return False


def _curl_http_code(state: RHELOSState) -> str:
    nginx = state.services.get("nginx")
    if nginx and nginx.active == "active":
        if not state.firewall.is_port_open(80):
            return "000"
        sites = state.read_file("/etc/nginx/sites-enabled/default") or ""
        if "listn" in sites:
            return "502"
        if "root /var/www/wrong" in sites:
            return "200"
        return "200"
    return "000"
