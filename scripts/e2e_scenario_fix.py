"""Load and apply per-scenario fix.sh for E2E validation."""
from __future__ import annotations

import os

from apps.labs.provisioner import get_provisioner


def fix_script_path(scenario) -> str | None:
    tech = scenario.technology.slug if scenario.technology_id else ""
    if not tech or not scenario.slug:
        return None
    path = f"/scenarios/{tech}/{scenario.slug}/fix.sh"
    return path if os.path.isfile(path) else None


def apply_scenario_fix(session) -> tuple[bool, str]:
    """Run fix.sh inside the lab container. Returns (ok, output)."""
    path = fix_script_path(session.scenario)
    if not path:
        return False, "no fix.sh"

    resource_id = session.container_id or session.instance_id
    if not resource_id:
        return False, "no container"

    try:
        with open(path, encoding="utf-8") as fh:
            script = fh.read()
    except OSError as exc:
        return False, str(exc)[:200]

    if not script.strip():
        return False, "empty fix.sh"

    provisioner = get_provisioner(session.provider or "docker")
    try:
        if hasattr(provisioner, "execute_script"):
            exit_code, output = provisioner.execute_script(resource_id, script)
        else:
            exit_code, output = provisioner.execute_command(resource_id, script)
        return exit_code == 0, (output or "")[:500]
    except Exception as exc:
        return False, str(exc)[:200]
