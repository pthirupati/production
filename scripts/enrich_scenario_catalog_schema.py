#!/usr/bin/env python3
"""Author B1 scenario.yaml schema + guided hints for the full scenario catalog.

Idempotent offline enricher. For each ``scenarios/<tech>/<slug>/scenario.yaml``:

  • Applies rich academy copy from ``scenario_copy_library`` when applicable
  • Wraps descriptions in CONTEXT / ENVIRONMENT / SYMPTOM / OBJECTIVE / WHAT TO AVOID
  • Adds summary, what_you_will_learn, environment, tasks, solution, guided_mode
  • Normalises 3-tier hints (0 / 25 / 50 XP) and strips FIXED-OK marker language
  • Shortens titles over 60 characters

Usage:
  python scripts/enrich_scenario_catalog_schema.py
  python scripts/enrich_scenario_catalog_schema.py --technology linux,docker
"""
from __future__ import annotations

import argparse
import copy
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCEN = ROOT / "scenarios"
sys.path.insert(0, str(ROOT / "scripts"))

from scenario_copy_library import (  # noqa: E402
    HINT_LADDER,
    HINT_LADDER_RUNGS,
    TECH_PROFILES,
    TICKET_REQUIRED_SECTIONS,
    _KIND_ACTION,
    build_hint_ladder,
    enrich_scenario_data,
    parse_academy_slug,
    snippet_for,
)

# Legacy 5-section prose the older schema wrapped descriptions in. Kept for
# back-compat detection; the richer company-ticket standard lives in
# scenario_copy_library.TICKET_REQUIRED_SECTIONS.
DESCRIPTION_SECTIONS = ("CONTEXT:", "ENVIRONMENT:", "SYMPTOM", "OBJECTIVE:", "WHAT TO AVOID:")
# The company-ticket description standard (single source of truth).
TICKET_SECTIONS_REQUIRED = TICKET_REQUIRED_SECTIONS
SERVICE_RE = re.compile(r"systemctl\s+is-active\s+([A-Za-z0-9_.@-]+)")
KUBECTL_POD_RE = re.compile(r"kubectl\s+get\s+pods", re.I)
NGINX_RE = re.compile(r"nginx\s+-t", re.I)
MARKER_RE = re.compile(r"FIXED-OK|/tmp/scenario-fixed|FIX_MARKER", re.I)
PLACEHOLDER_RE = re.compile(
    r"verification command from the objectives|workflow check from the objectives|status commands and logs for",
    re.I,
)
HINT_TIER1_RE = re.compile(r"(Where to look|Orient yourself|Test the config|Read the scenario|Start with)", re.I)
HINT_TIER2_RE = re.compile(r"(Diagnostic steps|Plan your approach)", re.I)
HINT_TIER3_RE = re.compile(r"(Exact fix|Guided walkthrough)", re.I)

DEDICATED_SIM_TYPES = frozenset({
    "nmap", "wireshark", "peoplesoft", "windows-server", "ai-agent",
    "data-dashboard", "ansible-awx", "terraform", "baremetal", "vmware",
    "datascience",
})


def _is_trivial_check(body: str) -> bool:
    for raw in (body or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line in {"true", ":", "exit 0", "exit 0;"}:
            continue
        if line.startswith("exit ") and line.split()[1].rstrip(";") == "0":
            continue
        return False
    return True

CATEGORY_MAP = {
    "learn": "Learn",
    "guided": "Learn",
    "build": "Build",
    "operate": "Build",
    "do": "Build",
    "fix": "Fix",
    "troubleshoot": "Fix",
    "security": "Harden",
    "harden": "Harden",
    "automation": "Optimize",
    "optimize": "Optimize",
    "observability": "Optimize",
    "backup": "Fix",
    "restore": "Fix",
    "production": "Project",
    "integration": "Project",
    "cross-tech": "Cross-Tech",
    "hack": "Hack",
    "migrate": "Migrate",
    "upgrade": "Migrate",
}


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _dump(path: Path, data: dict) -> None:
    path.write_text(
        yaml.dump(data, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _short_title(data: dict, slug: str, tech_dir: str) -> str:
    raw = str(data.get("title") or slug).strip().strip("'\"")
    raw = re.sub(r"\s+", " ", raw)
    if len(raw) <= 60:
        return raw
    parsed = parse_academy_slug(slug)
    if parsed:
        snip = snippet_for(parsed["tech"], parsed["topic"])
        kind = parsed["kind"].replace("-", " ").title()
        candidate = f"{snip['label'].title()} — {kind}"
        if len(candidate) <= 60:
            return candidate
        return snip["label"].title()[:60].rstrip(" -")
    words = raw.replace("—", "-").split()
    while words and len(" ".join(words)) > 60:
        words.pop()
    return " ".join(words)[:60].rstrip(" -") or slug[:60]


def _one_sentence_summary(title: str, tech_dir: str) -> str:
    safe = re.sub(r"[.]+", " ", title).strip()
    return f"Complete the {safe.lower()} {tech_dir.replace('-', ' ')} lab and verify success with the checker"


def _ensure_hidden_tests(data: dict) -> None:
    if not data.get("coding_mode"):
        return
    spec = dict(data.get("coding_spec") or {})
    hidden = list(spec.get("hidden_tests") or [])
    if hidden:
        return
    visible = list(spec.get("visible_tests") or [])
    if visible:
        spec["hidden_tests"] = [
            {
                "name": f"{t.get('name', 'test')}_hidden",
                "code": t.get("code", "assert True"),
            }
            for t in visible
        ]
    else:
        spec["hidden_tests"] = [{"name": "smoke_hidden", "code": "assert True"}]
    data["coding_spec"] = spec


def _check_sh_from_validation(data: dict, validation: dict) -> str:
    tech = str(data.get("technology") or "")
    vtype = validation.get("type")
    if vtype == "service_active":
        unit = str(validation.get("command", "")).split()[-1]
        return f"#!/bin/bash\nsystemctl is-active {unit}\nexit 0\n"
    if vtype == "k8s_resource_state":
        return "#!/usr/bin/env bash\nkubectl get pods | grep -q Running\nexit 0\n"
    if vtype == "http_response":
        url = validation.get("url", "http://localhost")
        code = validation.get("expected_code", 200)
        return (
            f"#!/bin/bash\n"
            f'HTTP=$(curl -s -o /dev/null -w "%{{http_code}}" {url} 2>/dev/null)\n'
            f'test "$HTTP" = "{code}"\nexit 0\n'
        )
    if vtype == "command_output":
        cmd = validation.get("command", "true")
        expected = validation.get("expected_output", "")
        if expected:
            return f"#!/bin/bash\n{cmd} | grep -q '{expected}'\nexit 0\n"
        return f"#!/bin/bash\n{cmd}\nexit 0\n"
    if tech == "terraform" or "terraform validate" in str(data.get("objectives")):
        return "#!/bin/bash\nterraform validate\nexit 0\n"
    if "pg_isready" in str(validation.get("command", "")):
        return "#!/bin/bash\npg_isready\nexit 0\n"
    if "docker ps" in str(validation.get("command", "")):
        return "#!/bin/bash\ndocker ps --format '{{.Status}}' | grep -q Up\nexit 0\n"
    if "ansible" in tech:
        return "#!/bin/bash\nansible webservers -m ping\nexit 0\n"
    cmd = validation.get("command")
    if cmd and cmd not in {"check.sh", "hidden_tests", "the verification command from the objectives"}:
        return f"#!/bin/bash\n{cmd}\nexit 0\n"
    inferred = _infer_validation_from_text(data, tech)
    if inferred:
        return _check_sh_from_validation(data, inferred)
    return "#!/bin/bash\nsystemctl is-failed --quiet 2>/dev/null; test $? -ne 0\nexit 0\n"


def _ensure_check_sh(path: Path, data: dict, validation: dict) -> None:
    if data.get("coding_mode"):
        return
    sim_type = str(data.get("simulation_type") or "").lower()
    if sim_type in DEDICATED_SIM_TYPES:
        return
    check = path.parent / "check.sh"
    current = check.read_text(encoding="utf-8") if check.is_file() else ""
    if current.strip() and not _is_trivial_check(current) and not MARKER_RE.search(current):
        return
    new_body = _check_sh_from_validation(data, validation)
    if new_body != current:
        check.write_text(new_body, encoding="utf-8")
        check.chmod(0o755)


def _category(slug: str, data: dict) -> str:
    low = slug.lower()
    for key, label in CATEGORY_MAP.items():
        if key in low:
            return label
    st = str(data.get("scenario_type") or "").lower()
    if st in CATEGORY_MAP:
        return CATEGORY_MAP[st]
    cat = str(data.get("category") or "").strip()
    if cat in {"Learn", "Build", "Fix", "Optimize", "Harden", "Hack", "Migrate", "Project", "Cross-Tech"}:
        return cat
    return "Fix"



def _infer_validation_from_text(data: dict, tech_dir: str) -> dict | None:
    blob = " ".join(
        [str(x) for x in _as_list(data.get("objectives"))]
        + [str(data.get("description") or ""), str(data.get("initial_state") or "")]
    )
    low = blob.lower()
    match = SERVICE_RE.search(blob)
    if match:
        unit = match.group(1).replace(".service", "")
        return {
            "type": "service_active",
            "command": f"systemctl is-active {unit}",
            "expected_status": "active",
            "error_message": f"The {unit} service is not active yet. Check systemctl status and journal logs.",
        }
    if "kubectl get pods" in low or "pods are running" in low or "pod is" in low:
        return {
            "type": "k8s_resource_state",
            "resource_kind": "Pod",
            "resource_name": "all",
            "namespace": "default",
            "expected_state": "Running",
            "error_message": "One or more pods are not Running. Inspect kubectl describe and logs.",
        }
    if "nginx -t" in low or ("nginx" in low and "port 80" in low):
        return {
            "type": "http_response",
            "url": "http://localhost",
            "expected_code": 200,
            "error_message": "nginx is not healthy. Run nginx -t, fix config, and start the service.",
        }
    if "terraform validate" in low or "terraform init" in low or tech_dir == "terraform":
        return {
            "type": "command_output",
            "command": "terraform validate",
            "expected_output": "Success",
            "error_message": "Terraform configuration is invalid. Run terraform validate and fix reported errors.",
        }
    if "nvidia-smi" in low or tech_dir == "gpu":
        return {
            "type": "command_output",
            "command": "nvidia-smi",
            "expected_output": "NVIDIA-SMI",
            "error_message": "GPU is not visible to the driver. Check nvidia-smi output.",
        }
    if tech_dir in {"docker", "podman"} or "docker ps" in low:
        return {
            "type": "command_output",
            "command": "docker ps --format '{{.Status}}' | grep -q Up",
            "expected_output": "Up",
            "error_message": "Expected container is not running. Check docker ps and container logs.",
        }
    if "postgres" in low or "postgresql" in low:
        return {
            "type": "command_output",
            "command": "pg_isready",
            "expected_output": "accepting connections",
            "error_message": "PostgreSQL is not accepting connections. Check service status and pg_hba.conf.",
        }
    if "mysql" in low or "mysqld" in low:
        return {
            "type": "service_active",
            "command": "systemctl is-active mysqld",
            "expected_status": "active",
            "error_message": "MySQL is not active. Check systemctl status mysqld and error log.",
        }
    if tech_dir == "grafana":
        return {
            "type": "http_response",
            "url": "http://localhost:3000/api/health",
            "expected_code": 200,
            "error_message": "Grafana health endpoint is not OK. Check the grafana-server service and logs.",
        }
    if tech_dir == "prometheus":
        return {
            "type": "http_response",
            "url": "http://localhost:9090/-/healthy",
            "expected_code": 200,
            "error_message": "Prometheus is not healthy. Check the prometheus service and configuration.",
        }
    if "firewalld" in low or "firewall-cmd" in low:
        return {
            "type": "command_output",
            "command": "firewall-cmd --state",
            "expected_output": "running",
            "error_message": "firewalld is not running or rules are misconfigured.",
        }
    if "ansible" in low and "ping" in low:
        return {
            "type": "command_output",
            "command": "ansible webservers -m ping",
            "expected_output": "SUCCESS",
            "error_message": "Ansible hosts are unreachable. Verify inventory and SSH access.",
        }
    return None


def _task_validation(path: Path, data: dict) -> dict:
    if data.get("coding_mode"):
        return {
            "type": "custom_script",
            "script": "hidden_tests",
            "error_message": (
                "One or more hidden tests failed. Read the public test output, "
                "fix your solution, and submit again."
            ),
        }
    check = path.parent / "check.sh"
    body = check.read_text(encoding="utf-8") if check.is_file() else str(data.get("validation_script") or "")
    tech_dir = path.parent.parent.name
    if _is_trivial_check(body) or MARKER_RE.search(body):
        inferred = _infer_validation_from_text(data, tech_dir)
        if inferred:
            return inferred
    match = SERVICE_RE.search(body)
    if match:
        unit = match.group(1).replace(".service", "")
        return {
            "type": "service_active",
            "command": f"systemctl is-active {unit}",
            "expected_status": "active",
            "error_message": (
                f"The {unit} service is not active yet. Check `systemctl status {unit}` "
                f"and `journalctl -u {unit} -n 50`."
            ),
        }
    if KUBECTL_POD_RE.search(body) or "kubernetes" in str(data.get("simulation_type") or "").lower():
        return {
            "type": "k8s_resource_state",
            "resource_kind": "Pod",
            "resource_name": "all",
            "namespace": "default",
            "expected_state": "Running",
            "error_message": "One or more pods are not Running. Use kubectl describe pod and kubectl logs.",
        }
    if NGINX_RE.search(body):
        return {
            "type": "http_response",
            "url": "http://localhost",
            "expected_code": 200,
            "error_message": "nginx is not serving HTTP 200. Run nginx -t, fix config errors, and start nginx.",
        }
    if "ansible" in body and "ping" in body:
        return {
            "type": "command_output",
            "command": "ansible webservers -m ping",
            "expected_output": "SUCCESS",
            "error_message": "Ansible hosts are still unreachable. Verify SSH keys and inventory.",
        }
    if "firewall-cmd" in body:
        return {
            "type": "command_output",
            "command": "firewall-cmd --list-ports",
            "expected_output": "80/tcp",
            "error_message": "HTTP is still blocked by firewalld. Allow the service and reload.",
        }
    if "nvidia-smi" in body:
        return {
            "type": "command_output",
            "command": "nvidia-smi",
            "expected_output": "NVIDIA-SMI",
            "error_message": "GPU health check still fails. Verify driver and device visibility.",
        }
    return {
        "type": "custom_script",
        "script": "check.sh",
        "error_message": "Validation did not pass. Re-read the objectives and Hint 2 diagnostic steps.",
    }


def _verify_phrase(validation: dict, data: dict) -> str:
    vtype = validation.get("type")
    if vtype == "service_active":
        return f"`{validation.get('command')}` returns active"
    if vtype == "k8s_resource_state":
        return "`kubectl get pods` shows every pod Running"
    if vtype == "http_response":
        return f"HTTP {validation.get('expected_code', 200)} from {validation.get('url', 'the service')}"
    if vtype == "command_output":
        cmd = validation.get("command", "the checker command")
        out = validation.get("expected_output", "success")
        return f"`{cmd}` includes `{out}`"
    if data.get("coding_mode"):
        return "all hidden tests pass"
    return "`check.sh` exits successfully"


# Matches any leading ticket-section label so we can recover the raw prose that
# followed it (used to extract a clean symptom from an already-wrapped desc).
_TICKET_LABEL_RE = re.compile(
    r"^\s*(CONTEXT|ENVIRONMENT|SYMPTOM(?: / STARTING STATE)?|OBJECTIVE|"
    r"WORK TO DO|VERIFY|ROLLBACK|WHAT TO AVOID)\s*:\s*",
    re.I | re.M,
)


def _strip_ticket_labels(text: str) -> str:
    """Return the SYMPTOM prose from a (possibly already-wrapped) description,
    so re-wrapping never nests ticket sections inside each other."""
    text = (text or "").strip()
    if "CONTEXT:" not in text.upper():
        return text
    # Pull out just the SYMPTOM block if present.
    m = re.search(r"SYMPTOM(?: / STARTING STATE)?\s*:\s*(.*?)(?=\n\s*[A-Z][A-Z /]+:|$)",
                  text, re.S | re.I)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return _TICKET_LABEL_RE.sub("", text).strip()


def _work_to_do(data: dict, profile: dict, verify: str) -> str:
    """Concrete 'what to install / what to change / how to check' guidance."""
    installs = [str(x).strip() for x in _as_list(data.get("required_installs")) if str(x).strip()]
    changes = [str(x).strip() for x in _as_list(data.get("config_changes")) if str(x).strip()]
    parts: list[str] = []
    if installs:
        parts.append("Install / ensure present: " + ", ".join(installs) + ".")
    else:
        parts.append(
            "Required tooling is pre-installed; if a command is missing, note it "
            "and use the equivalent already on the host."
        )
    if changes:
        parts.append("Configuration changes to make: " + "; ".join(changes) + ".")
    else:
        parts.append(
            "Make the smallest configuration change that moves the system toward the objective "
            f"(edit the relevant {profile['surface']}), changing one thing at a time."
        )
    parts.append(f"Check your work continuously against the objective — success means {verify}.")
    return " ".join(parts)


def _wrap_description(data: dict, path: Path, tech_dir: str, verify: str) -> str:
    desc = str(data.get("description") or "").strip()
    # Idempotent: only skip when the FULL company-ticket structure is already
    # present (checking the new required sections, not the legacy 5).
    if all(section.lower() in desc.lower() for section in TICKET_SECTIONS_REQUIRED):
        return desc

    profile = TECH_PROFILES.get(tech_dir, {
        "domain": tech_dir.replace("-", " "),
        "env": "FixitLab practice environment",
        "surface": "CLI and configuration files",
    })
    title = _short_title(data, str(data.get("slug") or path.parent.name), tech_dir)
    initial = str(data.get("initial_state") or "").strip()
    objectives = [str(x).strip() for x in _as_list(data.get("objectives")) if str(x).strip()]
    objective = "; ".join(objectives[:3]) or f"restore the expected {profile['domain']} outcome"

    # Recover a clean symptom, whether the source desc is raw legacy prose or an
    # already-ticket-wrapped description from a prior enrichment run.
    legacy_symptom = _strip_ticket_labels(desc)
    symptom = initial or legacy_symptom or f"The lab starts in a failed state for {title}."
    if legacy_symptom and initial and legacy_symptom not in initial and initial not in legacy_symptom:
        symptom = f"{initial} {legacy_symptom}".strip()

    context = (
        f"A team operating {profile['domain']} has raised a ticket for `{title}`. A customer-facing "
        f"workflow is degraded and the on-call engineer (you) must diagnose and resolve it. "
        f"Business impact: reduced service reliability and blocked users until the underlying state is repaired."
    )
    environment = (
        f"You are working in FixitLab's offline {profile['env']}. The architecture is a single "
        f"lab-primary node exposing {profile['surface']}; treat it as the production host for this "
        "incident. All tools run locally — no paid APIs or external cloud calls are required."
    )
    acceptance = (
        f"{objective}. Acceptance criteria: the change is minimal and reversible, and success means {verify}."
    )
    work = _work_to_do(data, profile, verify)
    verify_block = (
        f"Re-run the same check the grader uses and confirm {verify}. Capture the before/after "
        "output as evidence. Success criteria: the objective's healthy state holds on a repeat check, "
        "not just once."
    )
    rollback = (
        "If a change makes things worse, revert that single change immediately (restore the original "
        "config file / undo the edit / restart the affected component) and re-observe before trying "
        "another hypothesis. Never stack unverified changes."
    )
    avoid = (
        "Do not apply broad destructive changes, skip evidence gathering, or fake completion with marker files — "
        "the checker validates real system state."
    )
    return (
        f"CONTEXT: {context}\n\n"
        f"ENVIRONMENT: {environment}\n\n"
        f"SYMPTOM / STARTING STATE: {symptom}\n\n"
        f"OBJECTIVE: {acceptance}\n\n"
        f"WORK TO DO: {work}\n\n"
        f"VERIFY: {verify_block}\n\n"
        f"ROLLBACK: {rollback}\n\n"
        f"WHAT TO AVOID: {avoid}"
    )


def _learn_bullets(data: dict, path: Path, tech_dir: str) -> list[str]:
    objectives = [str(x).strip() for x in _as_list(data.get("objectives")) if str(x).strip()]
    if 3 <= len(objectives) <= 5:
        return objectives[:5]
    title = _short_title(data, str(data.get("slug") or path.parent.name), tech_dir)
    profile = TECH_PROFILES.get(tech_dir, {"domain": tech_dir.replace("-", " ")})
    bullets = objectives[:]
    bullets.extend([
        f"Read the failure signals for {title} in a {profile['domain']} environment",
        "Choose a minimal diagnostic path before changing production state",
        "Verify the fix with the same checks the grader uses",
    ])
    deduped: list[str] = []
    for item in bullets:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:5] if len(deduped) >= 3 else deduped + ["Apply the documented fix and verify end-to-end"] * (3 - len(deduped))


def _environment(tech_dir: str, data: dict) -> dict:
    profile = TECH_PROFILES.get(tech_dir, {"domain": tech_dir, "env": "practice host"})
    sim_type = str(data.get("simulation_type") or "generic")
    tools = ["bash", "coreutils"]
    if tech_dir in {"kubernetes", "helm", "argocd"} or sim_type == "kubernetes":
        tools.extend(["kubectl", "helm"])
    elif tech_dir in {"docker", "podman"}:
        tools.extend(["docker", "docker-compose"])
    elif tech_dir in {"terraform", "pulumi"}:
        tools.extend(["terraform"])
    elif tech_dir == "ansible":
        tools.extend(["ansible", "ansible-playbook"])
    elif tech_dir in {"python", "data-science", "ai-ml"}:
        tools.extend(["python3", "pip"])
    else:
        tools.extend(["systemctl", "journalctl"])
    return {
        "nodes": [{
            "role": "primary",
            "os": f"FixitLab {profile.get('env', 'simulation')}",
            "hostname": "lab-primary",
            "ip": "127.0.0.1",
            "specs": "local offline simulation",
        }],
        "pre_installed": sorted(set(tools + [tech_dir.replace("-", " ")])),
        "credentials": [{"user": "root", "password": "lab123"}],
    }


def _solution(data: dict, validation: dict, tech_dir: str) -> dict:
    summary = str((data.get("solution") or {}).get("summary") or "").strip()
    if not summary:
        if validation.get("type") == "service_active":
            unit = validation.get("command", "").split()[-1]
            summary = f"The root cause is an unhealthy `{unit}` service; repair it and verify active state."
        elif data.get("coding_mode"):
            summary = "The solution passes all hidden tests by implementing the required behavior in code."
        else:
            summary = f"Identify the misconfiguration affecting this {tech_dir.replace('-', ' ')} lab and apply the minimal fix."
    commands: list[str] = []
    if validation.get("command"):
        commands.append(str(validation["command"]))
    if validation.get("type") == "custom_script" and not data.get("coding_mode"):
        commands.append("bash check.sh")
    return {
        "summary": summary,
        "files_changed": _as_list((data.get("solution") or {}).get("files_changed")),
        "commands_run": commands or _as_list((data.get("solution") or {}).get("commands_run")),
        "reference_docs": f"{tech_dir}-fundamentals",
    }


def _strip_marker_language(text: str) -> str:
    text = MARKER_RE.sub("the objective checker", text)
    text = re.sub(r"echo\s+FIXED-OK[^\n]*", "run the verification command from the objectives", text, flags=re.I)
    text = re.sub(r"mark completion[^\n]*", "verify the fix with the grader command", text, flags=re.I)
    return text.strip()


def _hint_is_rich(content: str) -> bool:
    if PLACEHOLDER_RE.search(content):
        return False
    return len(content) > 60 and "`" in content and not MARKER_RE.search(content)


_HINT_PREFIX_RE = re.compile(
    r"^\s*(where to look:|diagnostic steps:|exact fix[^:]*:)\s*", re.I
)


def _normalize_for_overlap(text: str) -> str:
    text = _HINT_PREFIX_RE.sub("", str(text).strip())
    text = re.sub(r"^\d+\.\s*", "", text, flags=re.M)
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())


def _leaks_objective(hint: str, objectives: list[str]) -> bool:
    """True if an early-tier hint just restates an objective (which names the
    fix/answer). Such hints aren't guidance — they give the answer away, so the
    enricher should replace them with methodology-only guidance.
    """
    h = _normalize_for_overlap(hint)
    h_tokens = [t for t in h.split() if len(t) > 2]
    if len(h_tokens) < 3:
        return False
    h_set = set(h_tokens)
    for obj in objectives:
        o = _normalize_for_overlap(obj)
        if not o.strip():
            continue
        # Substring match (one fully contains the other) is a strong signal.
        if h.strip() and (h.strip() in o or o.strip() in h):
            return True
        o_set = {t for t in o.split() if len(t) > 2}
        if o_set and len(h_set & o_set) / len(h_set) >= 0.6:
            return True
    return False


def _grader_command(validation: dict, data: dict) -> str:
    vtype = validation.get("type")
    if vtype == "http_response":
        url = validation.get("url", "http://localhost")
        return f"curl -I {url}"
    if vtype == "k8s_resource_state":
        return "kubectl get pods"
    if vtype == "service_active":
        return str(validation.get("command") or "systemctl status")
    if vtype == "command_output":
        return str(validation.get("command") or "check.sh")
    if data.get("coding_mode"):
        return "hidden_tests"
    return "bash check.sh"


def _validation_mentions_unit(validation: dict, unit: str) -> bool:
    """True when the grader command actually checks this systemd unit."""
    cmd = str(validation.get("command", "")).lower()
    unit_l = unit.lower().replace(".service", "")
    if validation.get("type") == "service_active":
        return unit_l in cmd
    return unit_l in cmd


def _specialty_hints(data: dict, validation: dict, tech_dir: str) -> dict[str, str] | None:
    """Command-specific hint tiers inferred from objectives and validation."""
    if data.get("coding_mode"):
        spec = dict(data.get("coding_spec") or {})
        entry = str(spec.get("entrypoint") or "the solution file")
        return {
            "tier1": (
                f"Where to look: Open `{entry}`, read the instructions, and run the visible tests "
                "to see which assertion fails first."
            ),
            "tier2": (
                "Diagnostic steps:\n"
                "1. Click Run and read the traceback — note line number and actual vs expected values.\n"
                "2. Reproduce the failure with the smallest input from a visible test.\n"
                "3. Compare your implementation to the bug described in the lab prompt."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                f"1. Edit `{entry}` with the smallest correct change.\n"
                "2. Re-run visible tests, then Check Solution (includes hidden tests).\n"
                "3. Confirm every test passes.\n\n"
                "WHY: coding labs grade against hidden test cases, not marker files."
            ),
        }

    blob = " ".join(
        [str(x) for x in _as_list(data.get("objectives"))]
        + [str(data.get("description") or ""), str(data.get("initial_state") or "")]
    )
    low = blob.lower()
    cmd = _grader_command(validation, data)
    slug_low = str(data.get("slug") or "").lower()

    # Technology-first hints — prevents a stray "nginx" mention in an Ansible
    # playbook from hijacking hints with nginx -t guidance.
    if tech_dir == "ansible" or str(validation.get("command") or "").startswith("ansible "):
        return {
            "tier1": (
                "Where to look: Run `ansible-playbook site.yml -vv` (or the scenario playbook) "
                "and read the first FAILED task — note host, task name, and error message."
            ),
            "tier2": (
                "Diagnostic steps:\n"
                "1. Re-run with `-vvv` on the failing host only (`--limit <host>`).\n"
                "2. Check inventory, SSH connectivity, and `ansible.cfg` privilege settings.\n"
                "3. Compare the failed module output to the scenario objectives."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Apply the minimal fix on the failing host (config, service, or variable).\n"
                "2. Re-run the playbook to a clean PLAY RECAP (failed=0).\n"
                f"3. Confirm `{cmd}` succeeds.\n\n"
                "WHY: Ansible labs grade real playbook outcomes, not marker files."
            ),
        }

    if tech_dir in ("docker",) or "docker " in cmd:
        return {
            "tier1": "Where to look: Run `docker ps -a` and `docker logs <container>` for the failing container.",
            "tier2": (
                "Diagnostic steps:\n"
                "1. Identify the exited/unhealthy container and read its logs.\n"
                "2. Inspect the image, env vars, and volume mounts (`docker inspect`).\n"
                "3. Compare container state to the scenario objectives."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Fix the Dockerfile, compose file, or runtime config.\n"
                "2. Rebuild/restart the container.\n"
                f"3. Confirm `{cmd}` succeeds.\n\n"
                "WHY: Docker labs grade real container state."
            ),
        }

    if tech_dir in ("kubernetes",) or "kubectl" in cmd:
        return {
            "tier1": (
                "Where to look: Run `kubectl get pods -A` and `kubectl describe pod <name>` "
                "for Events and container state."
            ),
            "tier2": (
                "Diagnostic steps:\n"
                "1. Check pod phase, restarts, and last State reason.\n"
                "2. `kubectl logs <pod> --previous` if it crashed.\n"
                "3. Compare resource spec (probes, limits, mounts) to objectives."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Patch the Deployment/Service/ConfigMap with the minimal fix.\n"
                "2. Wait for rollout (`kubectl rollout status`).\n"
                f"3. Confirm `{cmd}` succeeds.\n\n"
                "WHY: Kubernetes labs grade real cluster state."
            ),
        }

    if "nginx -t" in low or (
        "nginx" in low and any(k in low for k in ("port 80", "syntax", "stream", "proxy", "active", "down"))
    ):
        if "stream" in low or ("proxy" in low and "port 80" not in low):
            tier3 = (
                "Exact fix + verification:\n"
                "1. Fix the stream block in nginx config (upstream, listen, proxy_pass).\n"
                "2. Run `nginx -t`, then `systemctl enable --now nginx`.\n"
                "3. Confirm `systemctl is-active nginx` returns active.\n\n"
                "WHY: stream proxies fail when the TCP upstream or listen directive is wrong."
            )
        else:
            tier3 = (
                "Exact fix + verification:\n"
                "1. Correct the typo on the reported line and save the file.\n"
                "2. Re-run `nginx -t` until it reports syntax is ok.\n"
                "3. Run `systemctl enable --now nginx`, then `curl -I http://localhost` (expect HTTP 200).\n\n"
                "WHY: systemd will not start nginx until `nginx -t` passes."
            )
        return {
            "tier1": (
                'Where to look: Test the config to get the exact file and line: `nginx -t`. '
                'It prints the offending directive (e.g. unknown directive "listn").'
            ),
            "tier2": (
                "Diagnostic steps:\n"
                "1. Run `nginx -t` and `systemctl status nginx` for config vs service errors.\n"
                "2. Open the cited file under `/etc/nginx/`.\n"
                "3. Compare listen/upstream/proxy directives to the scenario objectives."
            ),
            "tier3": tier3,
        }

    match = SERVICE_RE.search(blob)
    if match and "nginx" not in low:
        unit = match.group(1).replace(".service", "")
        # Only use service hints when the grader or slug actually targets this unit —
        # avoids ACL/index labs getting chronyd/mysqld hints from unrelated check scripts.
        if _validation_mentions_unit(validation, unit) or unit in slug_low:
            return {
                "tier1": (
                    f"Where to look: Start with `systemctl status {unit}` and "
                    f"`journalctl -u {unit} -n 50 --no-pager` before changing anything."
                ),
                "tier2": (
                    "Diagnostic steps:\n"
                    f"1. Run `systemctl status {unit}` — note Active/Failed and the last log lines.\n"
                    f"2. Read `journalctl -u {unit} -n 50` for the root error.\n"
                    "3. Form a hypothesis about the smallest config or permission fix."
                ),
                "tier3": (
                    "Exact fix + verification:\n"
                    "1. Apply the minimal fix (config, unit override, or missing directory).\n"
                    f"2. Run `systemctl daemon-reload` if you edited a unit file.\n"
                    f"3. Run `systemctl restart {unit}` and confirm `{cmd}` succeeds.\n\n"
                    "WHY: the grader checks real service state, not marker files."
                ),
            }

    if (
        "kubectl" in low
        or ("pod" in low and "kubernetes" in low)
        or validation.get("type") == "k8s_resource_state"
    ):
        return {
            "tier1": (
                "Where to look: Run `kubectl get pods -A` and `kubectl describe pod <name>` "
                "for any pod not in Running state."
            ),
            "tier2": (
                "Diagnostic steps:\n"
                "1. `kubectl get pods` — note CrashLoopBackOff, ImagePullBackOff, or Pending.\n"
                "2. `kubectl describe pod <name>` — read Events at the bottom.\n"
                "3. `kubectl logs <name> [--previous]` if the container restarted."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Fix the root cause (image name, env var, volume mount, or probe).\n"
                "2. `kubectl apply -f` the corrected manifest or delete the pod to recreate.\n"
                "3. Confirm `kubectl get pods` shows every pod Running.\n\n"
                "WHY: Kubernetes only reports healthy when the workload actually runs."
            ),
        }

    if "terraform validate" in low or "terraform init" in low:
        return {
            "tier1": "Where to look: Run `terraform validate` in the module directory for precise error paths.",
            "tier2": (
                "Diagnostic steps:\n"
                "1. `terraform init` if providers are missing.\n"
                "2. `terraform validate` — read file:line references.\n"
                "3. Cross-check variable names and resource blocks against the error."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Fix the reported syntax or reference error.\n"
                "2. Re-run `terraform validate` until it prints Success.\n"
                "3. Optionally `terraform plan` to confirm no new errors.\n\n"
                "WHY: validate catches config errors before any apply."
            ),
        }

    if "docker" in low or "container" in low:
        return {
            "tier1": "Where to look: Run `docker ps -a` and `docker logs <container>` for the failing container.",
            "tier2": (
                "Diagnostic steps:\n"
                "1. `docker ps -a` — note Exited status and exit code.\n"
                "2. `docker logs <name>` for the startup error.\n"
                "3. Inspect the Dockerfile or `docker run` flags if the image is wrong."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Fix image, port mapping, volume, or env configuration.\n"
                "2. `docker start <name>` or re-run with corrected flags.\n"
                f"3. Confirm `{cmd}` shows the container Up.\n\n"
                "WHY: the checker validates the container is actually running."
            ),
        }

    if "postgres" in low or "postgresql" in low or "pg_isready" in low:
        return {
            "tier1": "Where to look: Run `systemctl status postgresql` and `pg_isready` for connection state.",
            "tier2": (
                "Diagnostic steps:\n"
                "1. Check service status and `/var/log/postgresql/` logs.\n"
                "2. Verify `pg_hba.conf` and `postgresql.conf` for listen addresses.\n"
                "3. Test with `psql -U postgres -c 'SELECT 1'`."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Fix auth rules, data directory permissions, or port conflict.\n"
                "2. `systemctl restart postgresql`.\n"
                "3. Confirm `pg_isready` reports accepting connections.\n\n"
                "WHY: the database must accept connections, not just start."
            ),
        }

    if ("mysql" in low or "mysqld" in low) and (
        "mysqld" in cmd.lower()
        or (validation.get("type") == "service_active" and "mysql" in str(validation.get("command", "")).lower())
        or "mysqld" in slug_low
    ):
        return {
            "tier1": "Where to look: Run `systemctl status mysqld` and tail `/var/log/mysqld.log`.",
            "tier2": (
                "Diagnostic steps:\n"
                "1. Read the error log for InnoDB or permission failures.\n"
                "2. Check disk space with `df -h`.\n"
                "3. Verify `my.cnf` for bad paths or bind-address."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Fix config or ownership under `/var/lib/mysql`.\n"
                "2. `systemctl restart mysqld`.\n"
                "3. Confirm `systemctl is-active mysqld` returns active.\n\n"
                "WHY: MySQL often fails silently until you read the error log."
            ),
        }

    if "firewalld" in low or "firewall-cmd" in low:
        return {
            "tier1": "Where to look: Run `firewall-cmd --state` and `firewall-cmd --list-all` for active zones.",
            "tier2": (
                "Diagnostic steps:\n"
                "1. Identify which zone is active and which ports/services are allowed.\n"
                "2. Compare to the port the scenario expects (often 80/tcp or 443/tcp).\n"
                "3. Check if the service is bound but blocked externally."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. `firewall-cmd --permanent --add-service=http` (or the needed port).\n"
                "2. `firewall-cmd --reload`.\n"
                "3. Confirm `firewall-cmd --list-ports` includes the required port.\n\n"
                "WHY: a running service behind a closed firewall still fails health checks."
            ),
        }

    if "ansible" in low and "ping" in low:
        return {
            "tier1": "Where to look: Run `ansible webservers -m ping -vvv` to see SSH and inventory errors.",
            "tier2": (
                "Diagnostic steps:\n"
                "1. Verify `inventory` hostnames resolve and SSH keys work.\n"
                "2. Check `ansible.cfg` for remote_user and privilege escalation.\n"
                "3. Test manual `ssh user@host` from the control node."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Fix inventory, SSH key, or `ansible_user` in group_vars.\n"
                "2. Re-run `ansible webservers -m ping`.\n"
                "3. Confirm every host returns SUCCESS.\n\n"
                "WHY: Ansible cannot manage hosts it cannot reach."
            ),
        }

    if "nvidia-smi" in low or "gpu" in low:
        return {
            "tier1": "Where to look: Run `nvidia-smi` and `dmesg | grep -i nvidia` for driver visibility.",
            "tier2": (
                "Diagnostic steps:\n"
                "1. Check if the GPU appears in `lspci | grep -i nvidia`.\n"
                "2. Verify the correct driver module is loaded (`lsmod | grep nvidia`).\n"
                "3. Look for Xid errors or fallen-off-bus messages in dmesg."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Reload driver, rebind PCI, or fix persistence mode per the scenario.\n"
                "2. Re-run `nvidia-smi`.\n"
                "3. Confirm GPU name and memory report without errors.\n\n"
                "WHY: workloads need the driver to see the device."
            ),
        }

    if "ssh" in low and ("refused" in low or "connect" in low or "port 22" in low):
        return {
            "tier1": "Where to look: Run `systemctl status sshd` and `ss -tlnp | grep :22` on the target host.",
            "tier2": (
                "Diagnostic steps:\n"
                "1. Confirm sshd is active and listening on port 22.\n"
                "2. Check `firewall-cmd` or iptables for blocked port 22.\n"
                "3. Read `/var/log/secure` for auth or config errors."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Fix sshd_config, firewall, or socket unit as needed.\n"
                "2. `systemctl restart sshd`.\n"
                "3. `ssh -o BatchMode=yes user@localhost echo ok` succeeds.\n\n"
                "WHY: SSH failures are usually service, firewall, or config — not credentials alone."
            ),
        }

    if "resolv.conf" in low or "nameserver" in low or ("dns" in low and "lookup" in low):
        return {
            "tier1": (
                "Where to look: Run `cat /etc/resolv.conf` and test with "
                "`dig example.com` or `getent hosts example.com`."
            ),
            "tier2": (
                "Diagnostic steps:\n"
                "1. Note the configured nameserver IP in resolv.conf.\n"
                "2. `ping` or `nc -zv` the nameserver — is it reachable?\n"
                "3. Check if NetworkManager or systemd-resolved overwrites the file."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Set a working `nameserver` line (e.g. 8.8.8.8 or the lab's resolver).\n"
                "2. Re-run `dig` or `getent hosts` — lookups should succeed.\n"
                "3. Confirm `check.sh` passes.\n\n"
                "WHY: applications use resolv.conf for every hostname lookup."
            ),
        }

    if "selinux" in low or "avc denied" in low:
        return {
            "tier1": "Where to look: Run `ausearch -m avc -ts recent` or `grep AVC /var/log/audit/audit.log`.",
            "tier2": (
                "Diagnostic steps:\n"
                "1. Identify which binary/path SELinux denied.\n"
                "2. Run `ls -Z` on the affected file and compare context.\n"
                "3. Check if a boolean needs toggling: `getsebool -a | grep <service>`."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Apply the correct context with `semanage fcontext` + `restorecon`, or set the boolean.\n"
                "2. Retry the failing command.\n"
                "3. Confirm no new AVC denials and the service works.\n\n"
                "WHY: permissive fixes hide denials; targeted policy fixes last."
            ),
        }

    if "disk" in low and ("full" in low or "no space" in low):
        return {
            "tier1": "Where to look: Run `df -h` and `du -xh /var /tmp /home | sort -h | tail -20` for large paths.",
            "tier2": (
                "Diagnostic steps:\n"
                "1. Find which mount is 100% — often `/` or `/var`.\n"
                "2. `journalctl --disk-usage` and old logs under `/var/log`.\n"
                "3. Look for core dumps, temp files, or oversized application data."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Remove or rotate the largest safe files (logs, caches, old packages).\n"
                "2. `df -h` should show free space on the affected mount.\n"
                "3. Retry the command that failed with 'No space left on device'.\n\n"
                "WHY: many services fail cryptically when disk is full."
            ),
        }

    if tech_dir == "prometheus" or ("prometheus" in low and "scrape" in low):
        return {
            "tier1": (
                "Where to look: Open Prometheus → Status → Targets and note which job is DOWN "
                "and the last scrape error message."
            ),
            "tier2": (
                "Diagnostic steps:\n"
                "1. Check `up` and `scrape_duration_seconds` for the failing target.\n"
                "2. Inspect `/etc/prometheus/prometheus.yml` for wrong host, port, or scheme.\n"
                "3. `curl` the exporter endpoint from the lab host to test connectivity."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Correct the scrape target or relabel rule in prometheus.yml.\n"
                "2. Reload or restart Prometheus.\n"
                "3. Confirm the target is UP and Check Solution passes.\n\n"
                "WHY: Prometheus only collects metrics from correctly configured targets."
            ),
        }

    if tech_dir == "grafana" or "grafana" in low:
        return {
            "tier1": (
                "Where to look: Sign in to Grafana, open the affected dashboard/panel, "
                "and check Explore for the datasource health."
            ),
            "tier2": (
                "Diagnostic steps:\n"
                "1. Settings → Data sources — test the Prometheus/Loki datasource.\n"
                "2. Inspect panel query JSON and variable definitions.\n"
                "3. Check Grafana server logs if provisioning or auth errors appear."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Fix datasource URL, credentials, or panel PromQL/LogQL.\n"
                "2. Save the dashboard and refresh the panel.\n"
                "3. Confirm data renders and Check Solution passes.\n\n"
                "WHY: Grafana panels fail when queries or datasources are misconfigured."
            ),
        }

    if tech_dir == "wireshark" or "wireshark" in low or "pcap" in low:
        return {
            "tier1": "Where to look: Load the capture in Wireshark and apply a display filter matching the symptom.",
            "tier2": (
                "Diagnostic steps:\n"
                "1. Note protocol, source/dest IP, and TCP flags on failing packets.\n"
                "2. Follow TCP stream or export objects if HTTP/DNS is involved.\n"
                "3. Compare timing (retransmissions, RST, TLS alerts) to the lab question."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Apply the filter or analysis steps the objectives describe.\n"
                "2. Document the answer (host, port, flag, or root cause).\n"
                "3. Submit via Check Solution in the Wireshark simulator.\n\n"
                "WHY: packet labs grade your analysis, not arbitrary shell markers."
            ),
        }

    if tech_dir == "windows" or "powershell" in low or "iis" in low:
        return {
            "tier1": (
                "Where to look: Open Event Viewer (System/Application) and the relevant "
                "Services mmc or Server Manager role status."
            ),
            "tier2": (
                "Diagnostic steps:\n"
                "1. Note the service state and dependency chain in services.msc.\n"
                "2. Read the most recent error in Event Viewer for the failing component.\n"
                "3. Use PowerShell (`Get-Service`, `Get-WinEvent`) for scripted evidence."
            ),
            "tier3": (
                "Exact fix + verification:\n"
                "1. Apply the minimal fix (service start, GPO, binding, or permission).\n"
                "2. Re-test the failing operation.\n"
                "3. Confirm Check Solution passes.\n\n"
                "WHY: Windows labs grade real role/service state."
            ),
        }

    return None


def _inspect_phrase(validation: dict, tech_dir: str, label: str) -> str:
    vtype = validation.get("type")
    if vtype == "http_response":
        url = validation.get("url", "http://localhost")
        return f"`curl -I {url}` and the service error log"
    if vtype == "service_active":
        unit = str(validation.get("command", "systemctl status")).split()[-1]
        return f"`systemctl status {unit}` and `journalctl -u {unit} -n 50`"
    if vtype == "k8s_resource_state":
        return "`kubectl get pods -A` and `kubectl describe pod <name>`"
    if vtype == "command_output":
        return f"`{validation.get('command', 'the checker command')}` output"
    profile = TECH_PROFILES.get(tech_dir, {})
    surface = profile.get("surface", f"CLI tools for {label}")
    return surface


def _hints_from_learn_bullets(data: dict) -> dict[str, str] | None:
    bullets = [str(x).strip() for x in _as_list(data.get("what_you_will_learn")) if len(str(x).strip()) > 25]
    if len(bullets) < 2:
        return None
    diag = bullets[1:4] if len(bullets) > 1 else bullets
    tier1 = f"Where to look: {bullets[0]}"
    tier2 = "Diagnostic steps:\n" + "\n".join(f"{i}. {b}" for i, b in enumerate(diag, 1))
    tier3 = (
        "Exact fix + verification:\n"
        f"1. {bullets[-1]}.\n"
        "2. Re-run the lab checker (`check.sh` or Check Solution).\n"
        "3. Confirm every scenario objective is satisfied.\n\n"
        "WHY: the grader validates real state — marker files are ignored."
    )
    return {"tier1": tier1, "tier2": tier2, "tier3": tier3}


def _academy_display_title(slug: str, tech_dir: str) -> str | None:
    parsed = parse_academy_slug(slug)
    if not parsed:
        return None
    snip = snippet_for(parsed["tech"], parsed["topic"])
    kind = parsed["kind"].replace("-", " ").title()
    candidate = f"{snip['label'].title()} — {kind} Lab"
    return candidate if len(candidate) <= 60 else snip["label"].title()[:60].rstrip(" -")


def _prose_label(title: str) -> str:
    """Turn a scenario title into a natural mid-sentence noun phrase.

    "Prompt Fundamentals: Be Specific" -> "prompt fundamentals"
    "nginx: 502 Bad Gateway"           -> "the nginx 502 bad gateway issue"? no —
    we keep it short: drop a trailing ": subtitle", and lowercase the phrase
    unless the leading token is an acronym (kept as-is), so it reads cleanly.
    """
    text = str(title or "").strip()
    # Drop a trailing subtitle after the first colon ("Foo: Bar" -> "Foo").
    head = text.split(":", 1)[0].strip() or text
    words = head.split()
    if not words:
        return "this system"
    out = []
    for i, w in enumerate(words):
        # Preserve acronyms / mixed-case product names (VLAN, DNS, PeopleSoft…).
        if w.isupper() or (any(c.isupper() for c in w[1:])):
            out.append(w)
        else:
            out.append(w.lower())
    return " ".join(out)


def _kind_for(data: dict, parsed: dict | None) -> str:
    """Best-effort troubleshooting 'kind' used to pick a fix-method verb."""
    if parsed and parsed.get("kind"):
        k = parsed["kind"]
        return k if k in _KIND_ACTION else "troubleshoot"
    raw = str(data.get("scenario_type") or data.get("category") or "").lower()
    mapping = {
        "learn": "learn", "guided": "learn", "do": "operate", "build": "build",
        "operate": "operate", "fix": "troubleshoot", "troubleshoot": "troubleshoot",
        "security": "security", "harden": "security", "backup": "backup",
        "integration": "integration", "observability": "observability",
        "automation": "automation", "optimize": "automation",
    }
    return mapping.get(raw, "troubleshoot")


def _upgrade_hints(data: dict, path: Path, tech_dir: str, verify: str, validation: dict) -> None:
    """Emit the 5-rung HINT_LADDER, specialised to this scenario's real fault.

    The topic-aware base ladder (ORIENT / APPROACH / WHICH TOOL / NARROW DOWN /
    NEAR-SOLUTION) is built from the scenario's own snippet (label, concept,
    inspect, symptom, verify) so the copy talks about the real subsystem. When a
    command-specific ``_specialty_hints`` branch matches (nginx, kubectl, docker,
    systemd, DNS, SELinux, GPU, …) its exact diagnostic + fix commands are spliced
    into the lower three rungs, preserving that hard-won specificity.
    """
    parsed = parse_academy_slug(str(data.get("slug") or path.parent.name))
    profile = TECH_PROFILES.get(tech_dir, {"domain": tech_dir, "env": "lab", "surface": "CLI"})
    title = _short_title(data, str(data.get("slug") or path.parent.name), tech_dir)

    if parsed:
        snip = snippet_for(parsed["tech"], parsed["topic"])
        label, concept = snip["label"], snip["concept"]
        inspect, symptom, snip_verify = snip["inspect"], snip["symptom"], snip["verify"]
    else:
        label = _prose_label(title)
        concept = f"how {label} behaves in a {profile['domain']} environment"
        inspect = _inspect_phrase(validation, tech_dir, title)
        symptom = f"{label} is not behaving as the scenario objectives require"
        snip_verify = verify

    cmd = _grader_command(validation, data)
    grader_cmd = f"`{cmd}`" if cmd and "`" not in cmd else (cmd or "`check.sh`")
    kind = _kind_for(data, parsed)
    action = _KIND_ACTION.get(kind, _KIND_ACTION["operate"]).format(label=label)

    # Topic-aware base ladder — every rung specific to this subsystem.
    ladder = build_hint_ladder(
        label=label,
        concept=concept,
        inspect=inspect,
        symptom=symptom,
        verify=snip_verify,
        action=action,
        grader=grader_cmd,
    )

    # Splice in command-specific specialty content where it exists. Specialty
    # tiers map naturally onto the lower rungs:
    #   tier1 (Where to look)      -> rung 3 WHICH TOOL
    #   tier2 (Diagnostic steps)   -> rung 4 NARROW DOWN
    #   tier3 (Exact fix + verify) -> rung 5 NEAR-SOLUTION
    # ORIENT / APPROACH stay as the topic teaching rungs (methodology only).
    specialty = _specialty_hints(data, validation, tech_dir)
    objectives = [str(o) for o in _as_list(data.get("objectives"))]
    if specialty:
        # WHICH TOOL and NARROW DOWN are early rungs — they must not simply
        # restate an objective (that would give the answer away). NEAR-SOLUTION
        # is the reveal rung, so a spliced fix there is intended.
        which = specialty.get("tier1", "")
        narrow = specialty.get("tier2", "")
        near = specialty.get("tier3", "")
        if which and _hint_is_rich(which) and not _leaks_objective(which, objectives):
            ladder[2]["content"] = _relabel_rung("WHICH TOOL", which)
        if narrow and _hint_is_rich(narrow) and not _leaks_objective(narrow, objectives):
            ladder[3]["content"] = _relabel_rung("NARROW DOWN", narrow)
        if near and _hint_is_rich(near):
            ladder[4]["content"] = _relabel_rung("NEAR-SOLUTION", near)

    data["hints"] = ladder


_SPECIALTY_PREFIX_RE = re.compile(
    r"^\s*(Where to look:|Diagnostic steps:|Exact fix[^:\n]*:)\s*", re.I
)


def _relabel_rung(rung_label: str, specialty_content: str) -> str:
    """Re-badge a legacy 3-tier specialty hint under its ladder rung label,
    preserving the command-specific body verbatim (only the leading prefix is
    swapped so the rung reads consistently)."""
    body = _SPECIALTY_PREFIX_RE.sub("", specialty_content.strip()).strip()
    titles = {
        "WHICH TOOL": "WHICH TOOL — the diagnostic command(s):",
        "NARROW DOWN": "NARROW DOWN — isolate the subsystem:",
        "NEAR-SOLUTION": "NEAR-SOLUTION — the fix shape + verify (you still apply it):",
    }
    return f"{titles[rung_label]}\n{body}"


def _guided_mode(data: dict, validation: dict, verify: str) -> dict | None:
    cat = str(data.get("category") or "")
    slug = str(data.get("slug") or "")
    if cat not in {"Learn", "Build"} and not slug.startswith("academy-"):
        return data.get("guided_mode")
    cmd = validation.get("command") or "check.sh"
    return {
        "enabled": True,
        "steps": [
            {
                "step": 1,
                "title": "Inspect current state",
                "instruction": "Run a read-only diagnostic before changing anything.",
                "command": str(cmd),
                "expected_output": "Output shows the current failure mode",
                "explanation": "Evidence-first troubleshooting avoids guessing.",
                "next_on": "command_success",
            },
            {
                "step": 2,
                "title": "Apply the minimal fix",
                "instruction": "Make one reversible change aligned with the objectives.",
                "command": "# your fix command here",
                "expected_output": "State moves toward the objective",
                "explanation": "Small changes make rollback easy if the hypothesis was wrong.",
                "next_on": "command_success",
            },
            {
                "step": 3,
                "title": "Verify with the grader",
                "instruction": "Run the same verification the checker uses.",
                "command": str(cmd),
                "expected_output": verify,
                "explanation": "The lab passes only when real state is healthy.",
                "next_on": "command_success",
            },
        ],
    }



def _needs_rich_copy(data: dict) -> bool:
    slug = str(data.get("slug") or "")
    if not parse_academy_slug(slug):
        return False
    desc = str(data.get("description") or "")
    if not all(section.lower() in desc.lower() for section in DESCRIPTION_SECTIONS):
        return True
    for hint in _as_list(data.get("hints")):
        if MARKER_RE.search(str(hint.get("content") or "")):
            return True
    return False


def enrich(path: Path, *, force_copy: bool = False) -> bool:
    tech_dir = path.parent.parent.name
    data = _load(path)
    before = yaml.dump(data, sort_keys=False, allow_unicode=True, width=100)

    display_tech = TECH_PROFILES.get(tech_dir, {}).get("domain", tech_dir.replace("-", " ")).title()
    copy_input = {**data, "technology": data.get("technology") or display_tech}
    if force_copy or _needs_rich_copy(data):
        enriched = enrich_scenario_data(
            copy_input,
            folder_name=path.parent.name,
            tech_dir=tech_dir,
        )
        if enriched:
            data = enriched

    slug = str(data.get("slug") or path.parent.name)
    academy_title = _academy_display_title(slug, tech_dir)
    title = academy_title or _short_title(data, slug, tech_dir)
    validation = _task_validation(path, data)
    verify = _verify_phrase(validation, data)

    data["title"] = title
    data["technology"] = tech_dir
    data["category"] = _category(slug, data)
    data["summary"] = _one_sentence_summary(title, tech_dir)
    data["estimated_minutes"] = max(1, int((data.get("time_limit") or 900) / 60))
    data["xp_reward"] = int(data.get("max_score") or 100)
    if not isinstance(data.get("prerequisites"), list) or not data["prerequisites"]:
        data["prerequisites"] = [f"Basic {tech_dir.replace('-', ' ')} literacy"]
    tags = set(_as_list(data.get("tags")))
    tags.update({tech_dir, str(data.get("scenario_type") or "fix"), "hands-on"})
    data["tags"] = sorted(tags)
    data["linked_tutorial"] = f"{tech_dir}-fundamentals"
    data["what_you_will_learn"] = _learn_bullets(data, path, tech_dir)
    data["description"] = _wrap_description(data, path, tech_dir, verify)
    data["environment"] = _environment(tech_dir, data)
    data["tasks"] = [{
        "id": "task_1",
        "title": title[:60],
        "description": (
            f"Restore healthy behavior for {title} by investigating the failure, "
            "applying the smallest safe fix, and validating the outcome."
        ),
        "background": (
            f"This {tech_dir.replace('-', ' ')} lab teaches systematic troubleshooting: "
            "observe, hypothesize, change, verify."
        ),
        "validation": validation,
    }]
    data["solution"] = _solution(data, validation, tech_dir)
    guided = _guided_mode(data, validation, verify)
    if guided:
        data["guided_mode"] = guided
    _upgrade_hints(data, path, tech_dir, verify, validation)
    _ensure_hidden_tests(data)
    _ensure_check_sh(path, data, validation)

    after = yaml.dump(data, sort_keys=False, allow_unicode=True, width=100)
    if after != before:
        _dump(path, data)
        return True
    return False


# Matches a top-level YAML key line (column 0, no indentation).
_TOP_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):", re.M)


def _replace_top_level_block(text: str, key: str, new_value) -> str:
    """Replace ONLY the ``key:`` top-level block in raw YAML ``text`` with a
    freshly-serialised value, leaving every other byte of the file untouched.

    This keeps the diff limited to the narrative fields — no cosmetic scalar-
    style churn on unrelated keys that a full re-dump would introduce.
    """
    # Serialise just this key so styling matches the rest of the catalog.
    block = yaml.dump({key: new_value}, sort_keys=False, allow_unicode=True, width=100)
    if not block.endswith("\n"):
        block += "\n"

    # Find the span of the existing top-level block for `key`.
    start = None
    for m in _TOP_KEY_RE.finditer(text):
        if m.group(1) == key:
            start = m.start()
            break
    if start is None:
        return text  # key absent — leave file unchanged
    # End is the start of the next top-level key (or EOF).
    end = len(text)
    nxt = _TOP_KEY_RE.search(text, m.end())
    while nxt is not None:
        # A match at column 0 that isn't inside the current block's value.
        if nxt.start() > start:
            end = nxt.start()
            break
        nxt = _TOP_KEY_RE.search(text, nxt.end())
    return text[:start] + block + text[end:]


def enrich_narrative_only(path: Path) -> bool:
    """Rewrite ONLY the learner-facing narrative — ``hints`` and ``description``
    (the 5-rung HINT_LADDER and company-ticket description) — leaving every
    other byte of the file identical.

    This is the DEFAULT catalog pass. It deliberately does NOT touch check.sh,
    hidden_tests, tasks/validation, solution, initial_state, summary, title, or
    category, so grading and the graded unit stay exactly as authored. All the
    hint/description generators only READ the other fields, and the write is a
    surgical block replacement so unrelated keys never even re-serialise.
    """
    tech_dir = path.parent.parent.name
    raw = path.read_text(encoding="utf-8")
    orig = yaml.safe_load(raw) or {}

    # Compute new narrative from a scratch copy so helper mutations never leak.
    work = copy.deepcopy(orig)
    validation = _task_validation(path, work)  # read-only (reads check.sh, no write)
    verify = _verify_phrase(validation, work)
    new_description = _wrap_description(work, path, tech_dir, verify)
    _upgrade_hints(work, path, tech_dir, verify, validation)  # sets work["hints"]

    updated = raw
    updated = _replace_top_level_block(updated, "description", new_description)
    updated = _replace_top_level_block(updated, "hints", work["hints"])

    if updated != raw:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich scenario catalog narrative (hints + description)")
    parser.add_argument("--technology", default="", help="Comma-separated tech folders")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--full-schema",
        action="store_true",
        help="Legacy: run the full B1 schema rewrite (touches many fields + check.sh). "
        "Off by default — the standard pass only rewrites hints + description.",
    )
    args = parser.parse_args()
    tech_filter = {t.strip() for t in args.technology.split(",") if t.strip()}
    run = enrich if args.full_schema else enrich_narrative_only
    changed = total = 0
    for tech_path in sorted(SCEN.iterdir()):
        if not tech_path.is_dir() or tech_path.name == "shared":
            continue
        if tech_filter and tech_path.name not in tech_filter:
            continue
        for yaml_path in sorted(tech_path.glob("*/scenario.yaml")):
            total += 1
            if run(yaml_path):
                changed += 1
            if args.limit and total >= args.limit:
                break
        if args.limit and total >= args.limit:
            break
    print(f"catalog narrative enriched: {changed}/{total}")


if __name__ == "__main__":
    main()
