"""Evaluate check.sh-style validation against simulated RHEL state."""

from __future__ import annotations

from .rhel_os import RHELOSState
from .rhel_shell import RHELShell


def validate_simulation_state(state: RHELOSState, script: str) -> tuple[bool, str]:
    """Run simplified validation checks against in-memory OS state."""
    script = (script or "").strip()
    if not script:
        return False, "NO_VALIDATION_SCRIPT"

    shell = RHELShell(state=state)
    lines = script.splitlines()
    failures: list[str] = []

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
            code = _curl_http_code(state)
            if code != "200":
                failures.append(f"nginx not responding on port 80 (got HTTP {code})")
            continue
        if "nginx -t" in stripped:
            out = shell.run("nginx -t")
            if "test is successful" not in out:
                failures.append("nginx configuration is invalid")
            continue
        if "pgrep -x nginx" in stripped or "pgrep nginx" in stripped:
            nginx = state.services.get("nginx")
            if not nginx or nginx.active != "active":
                failures.append("nginx is not running")
            continue
        if "systemctl is-active nginx" in stripped:
            nginx = state.services.get("nginx")
            if not nginx or nginx.active != "active":
                failures.append("nginx service inactive")
            continue
        if "getent passwd" in stripped and "appuser" in stripped:
            passwd = state.read_file("/etc/passwd") or ""
            if "appuser" not in passwd:
                failures.append("appuser not in /etc/passwd")
            continue
        if "pwck" in stripped:
            out = shell.run("pwck")
            if out and "no errors" not in out:
                failures.append(out)
            continue
        if "nvidia-smi" in stripped:
            if not getattr(state, "gpu_healthy", True):
                failures.append("GPU still unhealthy")
            continue
        if "sim-valid" in stripped or stripped == "true":
            continue

    if failures:
        return False, failures[0]
    return True, "Simulation validation passed"


def _curl_http_code(state: RHELOSState) -> str:
    nginx = state.services.get("nginx")
    if nginx and nginx.active == "active":
        sites = state.read_file("/etc/nginx/sites-enabled/default") or ""
        if "listn" in sites:
            return "502"
        return "200"
    return "000"
