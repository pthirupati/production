"""Evaluate check.sh-style validation against simulated RHEL state."""

from __future__ import annotations

from .rhel_os import RHELOSState
from .rhel_shell import RHELShell

# Canonical checks used when DB/scenario check.sh is a stub (true/exit 0 only)
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
    if "nginx" in slug and ("root" in slug or "html" in slug):
        return CANONICAL_NGINX_ROOT_CHECK
    if "nginx" in slug:
        return CANONICAL_NGINX_CHECK
    return script


def validate_simulation_state(state: RHELOSState, script: str) -> tuple[bool, str]:
    """Run simplified validation checks against in-memory OS state."""
    script = (script or "").strip()
    if not script or is_trivial_validation_script(script):
        return False, "Validation not configured — fix the scenario before checking"

    shell = RHELShell(state=state)
    lines = script.splitlines()
    failures: list[str] = []
    checks_run = 0

    for line in lines:
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
        if stripped.startswith("HTTP_CODE=") or stripped.startswith("HTTP_CODE=$(curl"):
            checks_run += 1
            code = _curl_http_code(state)
            if code != "200":
                failures.append(f"nginx not responding on port 80 (got HTTP {code})")
            continue
        if "grep" in stripped and "root /var/www/html" in stripped:
            checks_run += 1
            sites = state.read_file("/etc/nginx/sites-enabled/default") or ""
            if "root /var/www/html" not in sites:
                failures.append("nginx document root must be /var/www/html")
            continue
        if "nginx -t" in stripped:
            checks_run += 1
            out = shell.run("nginx -t")
            if "test is successful" not in out:
                failures.append("nginx configuration is invalid")
            continue
        if "pgrep -x nginx" in stripped or "pgrep nginx" in stripped:
            checks_run += 1
            nginx = state.services.get("nginx")
            if not nginx or nginx.active != "active":
                failures.append("nginx is not running")
            continue
        if "systemctl is-active nginx" in stripped:
            checks_run += 1
            nginx = state.services.get("nginx")
            if not nginx or nginx.active != "active":
                failures.append("nginx service inactive")
            continue
        if "getent passwd" in stripped and "appuser" in stripped:
            checks_run += 1
            passwd = state.read_file("/etc/passwd") or ""
            if "appuser" not in passwd:
                failures.append("appuser not in /etc/passwd")
            continue
        if "pwck" in stripped:
            checks_run += 1
            out = shell.run("pwck")
            if out and "no errors" not in out:
                failures.append(out)
            continue
        if "nvidia-smi" in stripped:
            checks_run += 1
            if not getattr(state, "gpu_healthy", True):
                failures.append("GPU still unhealthy")
            continue
        if "kubectl get pods" in stripped and "Running" in stripped:
            checks_run += 1
            continue
        if "firewall-cmd --list-ports" in stripped or "80/tcp" in stripped:
            checks_run += 1
            if not state.firewall.is_port_open(80):
                failures.append("port 80 not open in firewall")
            continue
        if "lvextend" in stripped or "pvs" in stripped and "sdb" in stripped:
            checks_run += 1
            pv = state.lvm.pvs.get("/dev/sdb")
            if pv and not pv.vg:
                failures.append("PV /dev/sdb not in volume group")
            continue
        if "sim-valid" in stripped:
            continue

    if checks_run == 0:
        return False, "No validation checks matched this simulation script"
    if failures:
        return False, failures[0]
    return True, "Simulation validation passed"


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
