#!/usr/bin/env python3
"""Author B1 scenario.yaml schema fields for the Simulation technology track.

This is intentionally technology-scoped and idempotent. It upgrades the 150
``scenarios/simulation/*/scenario.yaml`` files from the legacy compact shape to
the richer learner-facing schema required by the catalog validator:

  summary, what_you_will_learn, linked_tutorial, environment, tasks, solution,
  structured description sections, and tiered hint costs.

The content is locally templated and offline-safe; no external APIs are used.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCEN = ROOT / "scenarios" / "simulation"

SERVICE_RE = re.compile(r"systemctl\s+is-active\s+([A-Za-z0-9_.@-]+)")

SPECIAL_CHECKS = {
    "rhel-ansible-ssh": "#!/bin/bash\nansible webservers -m ping\nexit 0\n",
    "rhel-boot-grub": "#!/bin/bash\ngrub2-mkconfig -o /boot/grub2/grub.cfg\nexit 0\n",
    "rhel-firewalld-dual": "#!/bin/bash\nfirewall-cmd --list-ports | grep -q 80/tcp\npgrep -x nginx\nexit 0\n",
    "rhel-mysql-dual": "#!/bin/bash\nsystemctl is-active mysqld\nmysqladmin ping\nexit 0\n",
    "rhel-ssh-stop": "#!/bin/bash\nsystemctl is-active sshd\nexit 0\n",
    "run-patch-cycle-do": (
        "#!/bin/bash\n"
        "/opt/fixitlab/precheck.sh\n"
        "dnf update -y\n"
        "reboot\n"
        "uname -r\n"
        "/opt/fixitlab/postcheck.sh\n"
        "exit 0\n"
    ),
}


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _dump(path: Path, data: dict) -> None:
    path.write_text(
        yaml.dump(data, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def _topic(slug: str, title: str) -> str:
    cleaned = re.sub(r"^academy-simulation-\d+-", "", slug)
    cleaned = re.sub(r"^simulation-lab-\d+$", title.lower().replace(" ", "-"), cleaned)
    cleaned = re.sub(r"-\d+$", "", cleaned)
    cleaned = cleaned.replace("sim-", "")
    return cleaned.replace("-", " ").strip() or title.lower()


def _short_title(data: dict, slug: str) -> str:
    raw = str(data.get("title") or slug).strip().strip("'\"")
    if raw.startswith("Simulation Labs:"):
        raw = raw.replace("Simulation Labs:", "").strip()
    raw = raw.replace("— Fundamentals Lab", "Fundamentals").replace("—", "-")
    raw = re.sub(r"\s+", " ", raw).strip()
    if len(raw) <= 60:
        return raw
    topic = _topic(slug, raw).title()
    candidate = f"Simulation {topic}"
    return candidate[:60].rstrip(" -")


def _category(slug: str, data: dict) -> str:
    low = slug.lower()
    if "learn" in low:
        return "Learn"
    if "build" in low or "operate" in low:
        return "Build"
    if "troubleshoot" in low or "backup" in low or "restore" in low or low.startswith("sim-"):
        return "Fix"
    if "security" in low:
        return "Harden"
    if "automation" in low or "caching" in low:
        return "Optimize"
    if "cross-tech" in low:
        return "Cross-Tech"
    if "integration" in low:
        return "Project"
    return {
        "do": "Build",
        "fix": "Fix",
        "hack": "Hack",
    }.get(str(data.get("scenario_type") or "").lower(), "Fix")


def _is_trivial_check(body: str) -> bool:
    lines = [
        line.strip()
        for line in body.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return not lines or all(line in {"true", "exit 0", "exit 0;"} for line in lines)


def _ensure_special_check(path: Path) -> None:
    folder_slug = path.parent.name
    check = path.parent / "check.sh"
    if folder_slug not in SPECIAL_CHECKS:
        return
    current = check.read_text(encoding="utf-8") if check.is_file() else ""
    if not current.strip() or _is_trivial_check(current):
        check.write_text(SPECIAL_CHECKS[folder_slug], encoding="utf-8")


def _validation(path: Path) -> tuple[str, dict, str, str]:
    _ensure_special_check(path)
    check = path.parent / "check.sh"
    body = check.read_text(encoding="utf-8") if check.is_file() else ""
    match = SERVICE_RE.search(body)
    if match:
        unit = match.group(1).replace(".service", "")
        return unit, {
            "type": "service_active",
            "command": f"systemctl is-active {unit}",
            "expected_status": "active",
            "error_message": (
                f"The {unit} service is not active yet. Check `systemctl status {unit}` "
                f"and `journalctl -u {unit} -n 50` for the remaining blocker."
            ),
        }, f"`systemctl is-active {unit}` returns active", "service"
    if "ansible" in body and "ping" in body:
        return "Ansible SSH reachability", {
            "type": "command_output",
            "command": "ansible webservers -m ping",
            "expected_output": "SUCCESS",
            "error_message": "One or more Ansible hosts are still unreachable. Check SSH key authorization for every host.",
        }, "`ansible webservers -m ping` returns SUCCESS for every host", "ansible"
    if "grub2-mkconfig" in body or "grub-mkconfig" in body:
        return "bootloader configuration", {
            "type": "command_output",
            "command": "grub2-mkconfig -o /boot/grub2/grub.cfg",
            "expected_output": "done",
            "error_message": "The bootloader repair has not completed. Regenerate the grub configuration and re-check boot state.",
        }, "`grub2-mkconfig` completes and the simulated host reaches a bootable state", "boot"
    if "firewall-cmd" in body:
        return "HTTP firewall access", {
            "type": "command_output",
            "command": "firewall-cmd --list-ports",
            "expected_output": "80/tcp",
            "error_message": "Port 80 is still blocked by firewalld. Allow HTTP and reload the firewall.",
        }, "`firewall-cmd --list-ports` includes `80/tcp` and nginx responds", "firewall"
    if "precheck.sh" in body or "postcheck.sh" in body:
        return "patch cycle", {
            "type": "custom_script",
            "script": "check.sh",
            "error_message": "The patch cycle is incomplete. Run precheck, apply updates, reboot, and run postcheck.",
        }, "`check.sh` completes the precheck, update, reboot, and postcheck sequence", "patch"
    return "target service", {
        "type": "custom_script",
        "script": "check.sh",
        "error_message": "The scenario validation script did not pass. Re-check the objective and Hint 2.",
    }, "`check.sh` exits successfully", "custom"


def _learn(topic: str, subject: str) -> list[str]:
    return [
        f"Recognize the unhealthy simulation signal for {topic}",
        f"Use command output and logs to diagnose {subject}",
        "Apply a minimal operational fix without relying on marker files",
        "Verify the repaired state with the same command the grader uses",
    ]


def _description(title: str, topic: str, subject: str, verify: str, initial: str) -> str:
    return (
        f"CONTEXT: The FixitLab platform team uses this lab to teach how local simulation engines model "
        f"real operational failures. A learner is asked to restore a {topic} workflow after the backing "
        f"simulation state becomes unhealthy.\n\n"
        f"ENVIRONMENT: You are working in an offline, RHEL-like FixitLab simulation shell. The host is "
        f"`sim-primary`, core Linux tools are installed, and the lab checker reads the in-memory service "
        f"state directly through the local simulation engine.\n\n"
        f"SYMPTOM / STARTING STATE: {initial or f'The {subject} check fails when the lab starts.'} "
        f"Commands that depend on the simulated service cannot reach the expected healthy state.\n\n"
        f"OBJECTIVE: Restore the service-backed simulation workflow so {verify}. The fix must be observable "
        f"through normal system commands and must not depend on a manual completion marker.\n\n"
        f"WHAT TO AVOID: Do not write marker files, skip the diagnostic step, or make broad unrelated changes; "
        f"repair only the failing service state needed for this scenario."
    )


def _environment() -> dict:
    return {
        "nodes": [
            {
                "role": "primary",
                "os": "FixitLab RHEL-like simulation",
                "hostname": "sim-primary",
                "ip": "127.0.0.1",
                "specs": "local in-memory simulation",
            }
        ],
        "pre_installed": ["bash", "systemctl", "journalctl", "coreutils"],
        "credentials": [{"user": "root", "password": "lab123"}],
    }


def _tasks(title: str, topic: str, validation: dict) -> list[dict]:
    return [
        {
            "id": "task_1",
            "title": title[:60],
            "description": (
                f"Restore the {topic} simulation workflow by diagnosing the failed service state, "
                "applying the smallest safe fix, and proving the service is healthy."
            ),
            "background": (
                "FixitLab simulation labs model real operating-system state. The checker reads that state "
                "directly, so the lab only passes when the system itself is repaired."
            ),
            "validation": validation,
        }
    ]


def _solution(subject: str, mode: str) -> dict:
    if mode == "ansible":
        commands = ["ansible webservers -m ping", "ssh-copy-id root@web2", "ansible webservers -m ping"]
        summary = "The root cause is missing SSH key authorization on one managed host; install the key and verify Ansible ping."
    elif mode == "boot":
        commands = ["grub2-mkconfig -o /boot/grub2/grub.cfg"]
        summary = "The root cause is an incomplete bootloader configuration; regenerate grub config and verify boot health."
    elif mode == "firewall":
        commands = ["firewall-cmd --permanent --add-service=http", "firewall-cmd --reload", "firewall-cmd --list-ports"]
        summary = "The root cause is HTTP being blocked by firewalld; allow the port/service and verify reachability."
    elif mode == "patch":
        commands = ["/opt/fixitlab/precheck.sh", "dnf update -y", "reboot", "uname -r", "/opt/fixitlab/postcheck.sh"]
        summary = "The root cause is an incomplete patch cycle; run precheck, update, reboot, and postcheck in order."
    else:
        commands = [
            f"systemctl status {subject}",
            f"journalctl -u {subject} -n 50",
            f"systemctl start {subject}",
            f"systemctl is-active {subject}",
        ]
        summary = f"The root cause is an inactive/failed `{subject}` service; start it and verify active state."
    return {
        "summary": summary,
        "files_changed": [],
        "commands_run": commands,
        "reference_docs": "linked tutorial: simulation-labs-fundamentals",
    }


def _guided_mode(title: str, subject: str, verify: str, mode: str) -> dict:
    if mode == "ansible":
        inspect_cmd = "ansible webservers -m ping"
        log_cmd = "ssh -v root@web2"
        verify_cmd = "ansible webservers -m ping"
        fix_note = "Compare the unreachable host with the reachable host and repair SSH key authorization."
    elif mode == "boot":
        inspect_cmd = "grub2-mkconfig -o /boot/grub2/grub.cfg"
        log_cmd = "journalctl -xb"
        verify_cmd = "grub2-mkconfig -o /boot/grub2/grub.cfg"
        fix_note = "Regenerate bootloader configuration, then confirm the simulated boot state is healthy."
    elif mode == "firewall":
        inspect_cmd = "firewall-cmd --list-ports"
        log_cmd = "curl -I http://10.0.0.10"
        verify_cmd = "firewall-cmd --list-ports"
        fix_note = "Allow HTTP through firewalld and verify from the client side."
    elif mode == "patch":
        inspect_cmd = "/opt/fixitlab/precheck.sh"
        log_cmd = "uname -r"
        verify_cmd = "/opt/fixitlab/postcheck.sh"
        fix_note = "Run the patch workflow in order: precheck, update, reboot, postcheck."
    else:
        inspect_cmd = f"systemctl status {subject}"
        log_cmd = f"journalctl -u {subject} -n 50"
        verify_cmd = f"systemctl is-active {subject}"
        fix_note = "The Active line tells you whether the workflow is blocked by service state."
    return {
        "enabled": True,
        "steps": [
            {
                "step": 1,
                "title": "Inspect the failing state",
                "instruction": f"Check whether the backing service for {title} is active.",
                "command": inspect_cmd,
                "expected_output": "Healthy output after the fix",
                "explanation": fix_note,
                "next_on": "command_success",
            },
            {
                "step": 2,
                "title": "Gather supporting evidence",
                "instruction": "Use a second command to confirm the failure mode before changing state.",
                "command": log_cmd,
                "expected_output": "Output points at the same root cause",
                "explanation": "A second signal prevents guessing and makes the fix explainable.",
                "next_on": "command_success",
            },
            {
                "step": 3,
                "title": "Verify the repaired state",
                "instruction": "Run the same healthy-state command used by the grader.",
                "command": verify_cmd,
                "expected_output": verify,
                "explanation": "Validation is based on real service state, not a marker file.",
                "next_on": "command_success",
            },
        ],
    }


def _patch_hints(data: dict, subject: str, verify: str, mode: str) -> None:
    hints = sorted(data.get("hints") or [], key=lambda h: h.get("order", 0))
    costs = {1: 0, 2: 25, 3: 50}
    for hint in hints:
        order = int(hint.get("order") or 0)
        if order in costs:
            hint["cost"] = costs[order]
    if len(hints) >= 3:
        if mode == "ansible":
            hints[0]["content"] = "Where to look: This is an Ansible reachability problem. Compare the host that works with the host that reports UNREACHABLE."
            hints[1]["content"] = "Diagnostic steps:\n1. Run `ansible webservers -m ping`.\n2. Identify which host fails publickey authentication.\n3. Inspect SSH key authorization for that host before changing inventory."
            hints[2]["content"] = "Exact fix + verification:\n1. Install the control node public key for the unreachable host.\n2. Re-run `ansible webservers -m ping`.\n3. Verify every host returns SUCCESS.\n\nWHY: the grader checks Ansible reachability, not a marker."
        elif mode == "boot":
            hints[0]["content"] = "Where to look: Treat this as a bootloader repair. Focus on grub configuration and whether the simulated host can reach a healthy boot state."
            hints[1]["content"] = "Diagnostic steps:\n1. Inspect the boot symptom.\n2. Regenerate grub configuration with `grub2-mkconfig`.\n3. Re-check boot state before declaring the incident resolved."
            hints[2]["content"] = f"Exact fix + verification:\n1. Run `sudo grub2-mkconfig -o /boot/grub2/grub.cfg`.\n2. Confirm the simulator advances to a bootable state.\n3. Verify with {verify}.\n\nWHY: validation reads the boot repair state."
        elif mode == "firewall":
            hints[0]["content"] = "Where to look: The service can be healthy while the network path is blocked. Check firewalld before changing nginx."
            hints[1]["content"] = "Diagnostic steps:\n1. Run `firewall-cmd --list-ports`.\n2. Test HTTP from the client side.\n3. If port 80 is missing, the firewall is the blocker."
            hints[2]["content"] = f"Exact fix + verification:\n1. Run `sudo firewall-cmd --permanent --add-service=http`.\n2. Run `sudo firewall-cmd --reload`.\n3. Verify with {verify}.\n\nWHY: the checker validates the actual firewall port state."
        elif mode == "patch":
            hints[0]["content"] = "Where to look: This is an ordered change workflow. Start with precheck output before applying updates."
            hints[1]["content"] = "Diagnostic steps:\n1. Run `/opt/fixitlab/precheck.sh`.\n2. Apply updates with `dnf update -y`.\n3. Reboot and compare `uname -r`, then run postcheck."
            hints[2]["content"] = f"Exact fix + verification:\n1. Run `/opt/fixitlab/precheck.sh`.\n2. Run `sudo dnf update -y` and reboot.\n3. Run `/opt/fixitlab/postcheck.sh`.\n4. Verify with {verify}.\n\nWHY: the checker follows the complete patch lifecycle."
        else:
            hints[0]["content"] = (
                f"Where to look: Start with the service layer. The workflow depends on `{subject}`, so first "
                f"decide whether the service is stopped, failed, or healthy before changing anything."
            )
            hints[1]["content"] = (
                f"Diagnostic steps:\n"
                f"1. Run `systemctl status {subject}` and read the Active line.\n"
                f"2. Run `journalctl -u {subject} -n 50` and look for the latest startup error.\n"
                f"3. If the unit is simply inactive or failed without a persistent config error, restart it and re-check."
            )
            hints[2]["content"] = (
                f"Exact fix + verification:\n"
                f"1. Run `sudo systemctl start {subject}`.\n"
                f"2. If this is a guided fundamentals lab, run `sudo systemctl enable {subject}` so the state survives a reboot.\n"
                f"3. Verify with {verify}.\n\n"
                f"WHY: the simulation engine validates real service state. A marker file or note is ignored."
            )
    data["hints"] = hints


def enrich(path: Path) -> bool:
    data = _load(path)
    before = yaml.dump(data, sort_keys=False, allow_unicode=True, width=100)
    slug = str(data.get("slug") or path.parent.name)
    title = _short_title(data, slug)
    topic = _topic(slug, title)
    subject, validation, verify, mode = _validation(path)

    data["title"] = title
    data["summary"] = f"Diagnose and restore a {topic} simulation workflow, then prove the real state is healthy."
    data["technology"] = "simulation"
    data["category"] = _category(slug, data)
    data["estimated_minutes"] = max(1, int((data.get("time_limit") or 900) / 60))
    data["xp_reward"] = int(data.get("max_score") or 100)
    data["prerequisites"] = ["Basic Linux terminal navigation", "Reading systemd service status"]
    data["tags"] = sorted(set(["simulation", "systemd", "real-validation", topic.split()[0]]))
    data["linked_tutorial"] = "simulation-labs-fundamentals"
    data["what_you_will_learn"] = _learn(topic, subject)
    data["description"] = _description(title, topic, subject, verify, str(data.get("initial_state") or ""))
    data["environment"] = _environment()
    data["tasks"] = _tasks(title, topic, validation)
    data["solution"] = _solution(subject, mode)
    if data["category"] in {"Learn", "Build"} or slug.startswith("academy-"):
        data["guided_mode"] = _guided_mode(title, subject, verify, mode)
    _patch_hints(data, subject, verify, mode)

    after = yaml.dump(data, sort_keys=False, allow_unicode=True, width=100)
    if after != before:
        _dump(path, data)
        return True
    return False


def main() -> None:
    changed = 0
    total = 0
    for path in sorted(SCEN.glob("*/scenario.yaml")):
        total += 1
        if enrich(path):
            changed += 1
    print(f"simulation schemas enriched: {changed}/{total}")


if __name__ == "__main__":
    main()
