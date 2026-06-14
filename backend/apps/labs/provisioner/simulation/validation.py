"""Evaluate check.sh-style validation against simulated RHEL state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .rhel_os import RHELOSState
from .rhel_shell import RHELShell

if TYPE_CHECKING:
    from .unified_sim import UnifiedSimulationEngine

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
dnf check-update
exit 0
"""

CANONICAL_BAREMETAL_CHECK = """#!/bin/bash
ipmitool power status | grep -qi on
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
    rules: list[tuple[Any, str]] = [
        (lambda s: "nginx" in s and ("root" in s or "html" in s), CANONICAL_NGINX_ROOT_CHECK),
        (lambda s: "nginx" in s or "firewall" in s and "nginx" in s, CANONICAL_NGINX_CHECK),
        (lambda s: "useradd" in s or "broken-user" in s, CANONICAL_USERADD_CHECK),
        (lambda s: "gpu" in s or "nvidia" in s, CANONICAL_GPU_CHECK),
        (lambda s: "mysql" in s, CANONICAL_MYSQL_CHECK),
        (lambda s: "postgres" in s, CANONICAL_POSTGRES_CHECK),
        (lambda s: "endpoint" in s, CANONICAL_K8S_ENDPOINTS_CHECK),
        (lambda s: "pod" in s or "crashloop" in s or "k8s" in s or "kubernetes" in s, CANONICAL_K8S_POD_CHECK),
        (lambda s: "ansible" in s, CANONICAL_ANSIBLE_CHECK),
        (lambda s: "firewall" in s or "firewalld" in s, CANONICAL_FIREWALL_CHECK),
        (lambda s: "docker" in s, CANONICAL_DOCKER_CHECK),
        (lambda s: "pip" in s or ("python" in s and "shell" not in s), CANONICAL_PYTHON_CHECK),
        (lambda s: "bash" in s or "shell-script" in s or "unbound" in s, CANONICAL_SHELL_CHECK),
        (lambda s: "lvm" in s, CANONICAL_LVM_CHECK),
        (lambda s: "initramfs" in s or "dracut" in s, CANONICAL_INITRAMFS_CHECK),
        (lambda s: "grub" in s or "mbr" in s or "kernel-panic" in s or "kernel" in s or "boot" in s, CANONICAL_GRUB_CHECK),
        (lambda s: "patch" in s, CANONICAL_PATCHING_CHECK),
        (lambda s: "ipmi" in s or "baremetal" in s or "vmware" in s, CANONICAL_BAREMETAL_CHECK),
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

    shell = RHELShell(state=state, scenario_slug=getattr(state, "scenario_slug", ""))
    failures: list[str] = []
    checks_run = 0

    for line in script.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("echo "):
            continue
        if stripped.startswith("if ") or stripped.startswith("fi") or stripped.startswith("then"):
            continue
        if stripped.startswith("exit "):
            code = stripped.split()[1]
            if code == "0":
                break
            return False, failures[-1] if failures else "Validation exit non-zero"

        if _run_line_check(stripped, state, shell, engine, failures):
            checks_run += 1
        elif "sim-valid" in stripped:
            continue

    if checks_run == 0:
        return False, "No validation checks matched this simulation script"
    if failures:
        return False, failures[0]
    return True, "Simulation validation passed"


def _run_line_check(
    stripped: str,
    state: RHELOSState,
    shell: RHELShell,
    engine: Any,
    failures: list[str],
) -> bool:
    """Return True if this line was recognized as a validation check."""
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

    if "getent passwd" in stripped and "appuser" in stripped:
        passwd = state.read_file("/etc/passwd") or ""
        if "appuser" not in passwd:
            failures.append("appuser not in /etc/passwd")
        return True

    if "pwck" in stripped:
        out = shell.run("pwck")
        if out and "no errors" not in out.lower():
            failures.append(out)
        return True

    if "nvidia-smi" in stripped:
        if not getattr(state, "gpu_healthy", True):
            failures.append("GPU still unhealthy")
        return True

    if "systemctl is-active mysqld" in stripped or "systemctl is-active mysql" in stripped:
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

    if "systemctl is-active docker" in stripped:
        svc = state.services.get("docker")
        if not svc or svc.active != "active":
            failures.append("docker service is not running")
        return True

    if "docker ps" in stripped:
        running = engine and getattr(engine, "_container_running", False)
        if not running:
            failures.append("no running docker containers")
        return True

    if "kubectl get pods" in stripped and "Running" in stripped:
        cluster = engine.cluster if engine else None
        if not cluster or not all(p.status == "Running" for p in cluster.pods):
            failures.append("not all pods are Running")
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
        if engine and not getattr(engine, "_ssh_key_fixed", False):
            failures.append("ansible hosts unreachable")
        return True

    if "firewall-cmd --list-ports" in stripped or ("80/tcp" in stripped and "firewall" in stripped):
        if not state.firewall.is_port_open(80):
            failures.append("port 80 not open in firewall")
        return True

    if "python3 -m py_compile" in stripped or "py_compile" in stripped:
        path = "/opt/app/main.py"
        if "main.py" in stripped:
            for part in stripped.split():
                if part.endswith(".py"):
                    path = part
                    break
        content = state.read_file(path) or ""
        if "SyntaxError" in content or "IndentationError" in content:
            failures.append(f"syntax error in {path}")
        return True

    if "bash -n" in stripped:
        path = "/opt/scripts/deploy.sh"
        for part in stripped.split():
            if part.endswith(".sh"):
                path = part
                break
        content = state.read_file(path) or ""
        if "$" in content and "set -u" in content and ":-}" not in content:
            failures.append(f"unbound variable risk in {path}")
        return True

    if "lvextend" in stripped or ("pvs" in stripped and "sdb" in stripped):
        pv = state.lvm.pvs.get("/dev/sdb")
        if pv and not pv.vg:
            failures.append("PV /dev/sdb not in volume group")
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
        if not fixed and boot and boot.phase not in ("shell", "login"):
            failures.append("boot issue not resolved")
        return True

    if "dnf check-update" in stripped or "yum check-update" in stripped:
        if not getattr(state, "patching_done", False):
            failures.append("system patching not completed")
        return True

    if "ipmitool power status" in stripped:
        power = getattr(engine, "_power_state", "on") if engine else "on"
        if str(power).lower() not in ("on", "up"):
            failures.append("host power is off")
        return True

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
