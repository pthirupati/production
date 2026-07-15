"""Validate every scenario.yaml for catalog completeness (B6).

Checks description, guided hints, validation script quality, objectives, and
academy marker-only labs. Idempotent read-only unless --fix-hints is passed
(re-invokes enrich_scenario_copy for thin entries).

Usage:
  python manage.py validate_scenario_catalog
  python manage.py validate_scenario_catalog --technology linux
  python manage.py validate_scenario_catalog --fail-on-gaps
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand

ROOT = Path(__file__).resolve().parents[5]
SCEN = ROOT / "scenarios"

# Reuse the single source of truth for the catalog standards defined alongside
# the generator, so the validator enforces exactly what the enricher emits.
_SCRIPTS = ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
try:
    from scenario_copy_library import (  # noqa: E402
        HINT_LADDER_RUNGS,
        TICKET_REQUIRED_SECTIONS,
    )
except Exception:  # pragma: no cover - defensive; keep validator importable
    HINT_LADDER_RUNGS = 5
    TICKET_REQUIRED_SECTIONS = (
        "CONTEXT:", "ENVIRONMENT:", "SYMPTOM", "OBJECTIVE:",
        "WORK TO DO:", "VERIFY:", "WHAT TO AVOID:",
    )

MARKER_ONLY_RE = re.compile(r"grep\s+-q\s+FIXED-OK|FIXED-OK.*grep", re.I)
# Truly fake completion marker: a sentinel file the learner writes by hand
# (echo FIXED-OK > /tmp/scenario-fixed). This proves nothing about lab state.
TMP_MARKER_RE = re.compile(r"/tmp/scenario-fixed|FIX_MARKER", re.I)
GUIDED_HINT_RE = re.compile(
    # New 5-rung HINT_LADDER labels, plus the legacy guided prefixes and any
    # numbered step, so both new and older rich hints pass.
    r"(ORIENT|APPROACH|WHICH TOOL|NARROW DOWN|NEAR-SOLUTION|"
    r"Orient yourself|Plan your approach|Guided walkthrough|Where to look|"
    r"Diagnostic steps|Exact fix|\n\s*1\.\s)",
    re.I,
)
ACADEMY_SLUG_RE = re.compile(r"^academy-")

# Simulation types that are graded by a dedicated engine (apps.vmware_sim.*),
# NOT by check.sh — see SimulationProvisioner.run_validation routing. For these
# the on-disk check.sh is vestigial, so a leftover marker there is not a grading
# gap (the dedicated engine performs the real state check).
DEDICATED_SIM_TYPES = frozenset({
    "nmap", "wireshark", "peoplesoft", "windows-server", "ai-agent",
    "data-dashboard", "ansible-awx", "terraform", "baremetal", "vmware",
    "datascience",
})

# Company-ticket description standard (single source of truth in the copy
# library). Enforces the richer sections — including the load-bearing WORK TO DO
# (what to install / change) and VERIFY (how to check) — not just the legacy 5.
DESCRIPTION_SECTIONS = TICKET_REQUIRED_SECTIONS
REAL_VALIDATION_TYPES = frozenset({
    "command_output",
    "file_contains",
    "service_active",
    "port_listening",
    "http_response",
    "k8s_resource_state",
    "terraform_plan_clean",
    "custom_script",
})
SCENARIO_CATEGORIES = {
    "learn": "Learn",
    "guided": "Learn",
    "build": "Build",
    "do": "Build",
    "fix": "Fix",
    "troubleshoot": "Fix",
    "optimize": "Optimize",
    "harden": "Harden",
    "hack": "Hack",
    "migrate": "Migrate",
    "upgrade": "Migrate",
    "project": "Project",
    "cross-tech": "Cross-Tech",
    "cross_technology": "Cross-Tech",
}


def _is_trivial_script(body: str) -> bool:
    """True when a check.sh has no substantive validation line (always passes)."""
    for raw in (body or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line in ("true", ":", "exit 0", "exit 0;"):
            continue
        if line.startswith("exit ") and line.split()[1].rstrip(";") == "0":
            continue
        return False
    return True


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _tech_from_path(path: Path) -> str:
    try:
        return path.relative_to(SCEN).parts[0]
    except Exception:
        return path.parent.parent.name


def _title(data: dict, path: Path) -> str:
    return str(data.get("title") or data.get("slug") or path.parent.name).strip()


def _summary_for(data: dict, path: Path) -> str:
    title = _title(data, path)
    tech = str(data.get("technology") or _tech_from_path(path)).replace("-", " ")
    return f"TODO: Practice {tech} by completing {title.lower()} and validating the healthy end state."


def _category_for(data: dict) -> str:
    raw = str(data.get("category") or data.get("scenario_type") or "fix").strip().lower()
    return SCENARIO_CATEGORIES.get(raw, data.get("category") or "Fix")


def _description_for(data: dict, path: Path) -> str:
    existing = str(data.get("description") or "").strip()
    initial = str(data.get("initial_state") or "").strip()
    title = _title(data, path)
    tech = str(data.get("technology") or _tech_from_path(path)).replace("-", " ")
    objective = "; ".join(str(x) for x in _as_list(data.get("objectives"))[:3]) or f"restore the expected {tech} outcome"
    return (
        f"CONTEXT: TODO: A realistic operations team is handling a {tech} incident for `{title}`. "
        f"The learner must reason from symptoms to a minimal, verifiable fix.\n\n"
        f"ENVIRONMENT: TODO: The lab runs in FixitLab's local simulation environment with the tools required for {tech}. "
        "No external services or paid APIs are required.\n\n"
        f"SYMPTOM / STARTING STATE: {initial or existing or 'TODO: describe the starting failure the learner observes.'}\n\n"
        f"OBJECTIVE: {objective}. The solution must be validated by the scenario checker, not by a manual marker.\n\n"
        "WORK TO DO: TODO: List what to install, what to configure, and what to change to satisfy the objective.\n\n"
        "VERIFY: TODO: Re-run the scenario checker and confirm the healthy end state holds on a repeat check.\n\n"
        "ROLLBACK: TODO: If a change makes things worse, revert that single change and re-observe before trying another.\n\n"
        "WHAT TO AVOID: TODO: Do not apply broad, destructive changes; make the smallest fix that satisfies the objective."
    )


def _learn_for(data: dict, path: Path) -> list[str]:
    objectives = [str(x).strip() for x in _as_list(data.get("objectives")) if str(x).strip()]
    if len(objectives) >= 3:
        return objectives[:5]
    title = _title(data, path)
    tech = str(data.get("technology") or _tech_from_path(path)).replace("-", " ")
    base = objectives[:]
    base.extend([
        f"Identify the unhealthy {tech} signal for {title}",
        "Choose the smallest diagnostic path before changing state",
        "Validate the restored state with the provided checker",
    ])
    deduped = []
    for item in base:
        if item not in deduped:
            deduped.append(item)
    return deduped[:5]


def _environment_for(data: dict, path: Path) -> dict:
    tech = str(data.get("technology") or _tech_from_path(path))
    return {
        "nodes": [
            {
                "role": "primary",
                "os": "FixitLab local simulation",
                "hostname": "lab",
                "ip": "127.0.0.1",
                "specs": "local/offline",
            }
        ],
        "pre_installed": [tech, "bash", "coreutils"],
        "credentials": [{"user": "root", "password": "lab123"}],
    }


def _task_validation_for(data: dict, path: Path) -> dict:
    validation = (data.get("validation_script") or "").strip()
    check_sh = path.parent / "check.sh"
    if check_sh.is_file():
        validation = check_sh.read_text(encoding="utf-8")
    if "systemctl is-active" in validation:
        unit = validation.split("systemctl is-active", 1)[1].split()[0].replace(".service", "")
        return {
            "type": "service_active",
            "expected_status": "active",
            "command": f"systemctl is-active {unit}",
            "error_message": f"The {unit} service is not active yet. Check systemctl status {unit} and recent journal logs.",
        }
    if "kubectl get pods" in validation:
        return {
            "type": "k8s_resource_state",
            "resource_kind": "Pod",
            "resource_name": "all",
            "namespace": "default",
            "expected_state": "Running",
            "error_message": "One or more pods are not Running. Inspect kubectl describe pod and logs.",
        }
    if "ansible" in validation and "ping" in validation:
        return {
            "type": "command_output",
            "command": "ansible webservers -m ping",
            "expected_output": "SUCCESS",
            "error_message": "Ansible hosts are not reachable yet. Verify inventory and SSH access.",
        }
    if "nvidia-smi" in validation:
        return {
            "type": "command_output",
            "command": "nvidia-smi",
            "expected_output": "NVIDIA-SMI",
            "error_message": "GPU health check still fails. Verify driver/runtime state.",
        }
    return {
        "type": "custom_script",
        "script": "check.sh",
        "error_message": "The scenario validation script did not pass. Review the failing objective and hint tier 2.",
    }


def _tasks_for(data: dict, path: Path) -> list[dict]:
    title = _title(data, path)
    return [
        {
            "id": "task_1",
            "title": title[:60],
            "description": (
                "TODO: Complete the scenario objective with the smallest change that restores the expected state. "
                "Use the validation feedback to confirm each objective."
            ),
            "background": "TODO: Explain the concept this scenario teaches in 1-2 learner-friendly sentences.",
            "validation": _task_validation_for(data, path),
        }
    ]


def _solution_for(data: dict, path: Path) -> dict:
    return {
        "summary": data.get("solution_explanation") or "TODO: Summarize the root cause and the minimal fix.",
        "files_changed": [],
        "commands_run": [],
        "reference_docs": "TODO: Link to the relevant official documentation or internal tutorial slug.",
    }


def _ensure_schema_stubs(path: Path, data: dict) -> bool:
    """Patch missing B1 schema fields in-memory. Return True if changed."""
    changed = False

    def set_missing(key: str, value):
        nonlocal changed
        if key not in data or data.get(key) in (None, "", []):
            data[key] = value
            changed = True

    set_missing("summary", _summary_for(data, path))
    set_missing("technology", _tech_from_path(path))
    set_missing("category", _category_for(data))
    if "estimated_minutes" not in data:
        data["estimated_minutes"] = max(1, int((data.get("time_limit") or 900) / 60))
        changed = True
    if "xp_reward" not in data:
        data["xp_reward"] = int(data.get("max_score") or 100)
        changed = True
    set_missing("prerequisites", [])
    set_missing("tags", [str(data.get("technology") or _tech_from_path(path)), str(data.get("scenario_type") or "fix")])
    set_missing("linked_tutorial", f"TODO: link-tutorial-for-{_tech_from_path(path)}")
    if len(_as_list(data.get("what_you_will_learn"))) < 3:
        data["what_you_will_learn"] = _learn_for(data, path)
        changed = True
    desc = str(data.get("description") or "")
    if not all(section.lower() in desc.lower() for section in DESCRIPTION_SECTIONS):
        data["description"] = _description_for(data, path)
        changed = True
    set_missing("environment", _environment_for(data, path))
    if not data.get("tasks"):
        data["tasks"] = _tasks_for(data, path)
        changed = True
    set_missing("solution", _solution_for(data, path))
    if str(data.get("scenario_type") or "").lower() in {"learn", "guided", "build", "do"} and "guided_mode" not in data:
        data["guided_mode"] = {"enabled": True, "steps": []}
        changed = True
    return changed


def validate_schema_fields(data: dict, path: Path) -> list[str]:
    gaps: list[str] = []
    title = _title(data, path)
    if not title:
        gaps.append("missing title")
    elif len(title) > 60:
        gaps.append("title longer than 60 chars")
    summary = str(data.get("summary") or "").strip()
    if not summary:
        gaps.append("missing summary")
    elif summary.count(".") > 1:
        gaps.append("summary should be one sentence")
    if not data.get("technology"):
        gaps.append("missing technology")
    if not data.get("category"):
        gaps.append("missing category")
    if not data.get("estimated_minutes"):
        gaps.append("missing estimated_minutes")
    if not data.get("xp_reward"):
        gaps.append("missing xp_reward")
    if "prerequisites" not in data or not isinstance(data.get("prerequisites"), list):
        gaps.append("missing prerequisites list")
    if "tags" not in data or not isinstance(data.get("tags"), list) or len(data.get("tags") or []) == 0:
        gaps.append("missing tags list")
    if not data.get("linked_tutorial"):
        gaps.append("missing linked_tutorial")
    learn = _as_list(data.get("what_you_will_learn"))
    if not (3 <= len([x for x in learn if str(x).strip()]) <= 5):
        gaps.append("what_you_will_learn must have 3-5 bullets")
    desc = str(data.get("description") or "")
    for section in DESCRIPTION_SECTIONS:
        if section.lower() not in desc.lower():
            gaps.append(f"description missing {section.rstrip(':')} section")
    env = data.get("environment")
    if not isinstance(env, dict) or not env.get("nodes"):
        gaps.append("missing environment.nodes")
    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        gaps.append("missing tasks")
    else:
        for task in tasks:
            validation = task.get("validation") if isinstance(task, dict) else None
            vtype = validation.get("type") if isinstance(validation, dict) else None
            if vtype not in REAL_VALIDATION_TYPES:
                gaps.append("task validation missing real validator type")
                break
            if not validation.get("error_message"):
                gaps.append("task validation missing error_message")
                break
    solution = data.get("solution")
    if not isinstance(solution, dict) or not solution.get("summary"):
        gaps.append("missing solution.summary")
    return gaps


def validate_scenario_file(path: Path, *, fix_stubs: bool = False) -> list[str]:
    """Return list of gap messages for one scenario.yaml."""
    gaps: list[str] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [f"YAML parse error: {exc}"]

    if fix_stubs and _ensure_schema_stubs(path, data):
        path.write_text(
            yaml.dump(data, sort_keys=False, allow_unicode=True, width=100),
            encoding="utf-8",
        )

    gaps.extend(validate_schema_fields(data, path))

    slug = data.get("slug") or path.parent.name
    desc = (data.get("description") or "").strip()
    if len(desc) < 80:
        gaps.append("description too short (<80 chars)")

    objectives = data.get("objectives") or []
    if len(objectives) < 2:
        gaps.append("fewer than 2 objectives")

    hints = data.get("hints") or []
    if len(hints) < HINT_LADDER_RUNGS:
        gaps.append(f"fewer than {HINT_LADDER_RUNGS} hints (graduated ladder required)")
    else:
        for i, h in enumerate(sorted(hints, key=lambda x: x.get("order", 0)), 1):
            content = (h.get("content") or "").strip()
            if len(content) < 40:
                gaps.append(f"hint {i} too short")
            elif not GUIDED_HINT_RE.search(content):
                gaps.append(f"hint {i} not step-by-step guided format")

    # Determine the real grading channel before judging check.sh, so we report
    # honest, actionable gaps instead of false "marker" positives:
    #   • coding_mode labs are graded by HIDDEN TESTS (check.sh is vestigial),
    #   • dedicated-sim labs are graded by their engine (check.sh is vestigial),
    #   • everything else is graded by check.sh via the simulation engine.
    coding_mode = bool(data.get("coding_mode"))
    sim_type = (data.get("simulation_type") or "").strip().lower()

    check_sh = path.parent / "check.sh"
    validation = (data.get("validation_script") or "").strip()
    script_body = validation
    if check_sh.is_file():
        script_body = check_sh.read_text(encoding="utf-8")

    if coding_mode:
        spec = data.get("coding_spec") or {}
        hidden = spec.get("hidden_tests") or []
        if not hidden:
            gaps.append("coding lab has no hidden tests (grading is trivial)")
    elif sim_type in DEDICATED_SIM_TYPES:
        # Graded by a dedicated engine; the on-disk check.sh is not used.
        pass
    elif not script_body.strip():
        gaps.append("no validation script / check.sh")
    elif _is_trivial_script(script_body):
        gaps.append("trivial validation (check.sh always passes)")
    elif TMP_MARKER_RE.search(script_body):
        # The fake /tmp/scenario-fixed completion sentinel — proves nothing.
        if ACADEMY_SLUG_RE.match(slug):
            gaps.append("academy lab still uses FIXED-OK marker check")
        else:
            gaps.append("marker-only validation (/tmp completion sentinel)")

    return gaps


class Command(BaseCommand):
    help = "Validate scenario catalog completeness (descriptions, guided hints, real validation)."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Validate all scenarios (default; CI-friendly alias)")
        parser.add_argument("--technology", default="", help="Comma-separated tech folder slugs")
        parser.add_argument(
            "--fix-stubs",
            action="store_true",
            help="Patch missing schema fields with TODO-marked placeholders in scenario.yaml",
        )
        parser.add_argument(
            "--flagship-only",
            action="store_true",
            help="Only validate labs in flagship_presets.FLAGSHIP_SLUG_KIND (real-sim upgraded set)",
        )
        parser.add_argument("--fail-on-gaps", action="store_true", help="Exit 1 if any gaps found")
        parser.add_argument("--limit", type=int, default=0, help="Stop after N scenarios (smoke)")

    def handle(self, *args, **options):
        tech_filter = {t.strip() for t in options["technology"].split(",") if t.strip()}
        flagship_only = bool(options["flagship_only"])
        fix_stubs = bool(options["fix_stubs"])
        flagship_slugs: set[str] = set()
        if flagship_only:
            from apps.labs.provisioner.simulation.flagship_presets import FLAGSHIP_SLUG_KIND

            flagship_slugs = set(FLAGSHIP_SLUG_KIND)
        limit = int(options["limit"] or 0)
        total = 0
        gap_count = 0
        gap_rows: list[tuple[str, list[str]]] = []
        slug_to_files: dict[str, list[str]] = {}

        for tech_path in sorted(SCEN.iterdir()):
            if not tech_path.is_dir() or tech_path.name == "shared":
                continue
            if tech_filter and tech_path.name not in tech_filter:
                continue
            for yaml_path in sorted(tech_path.glob("*/scenario.yaml")):
                if flagship_only:
                    slug = yaml_path.parent.name
                    if slug not in flagship_slugs:
                        continue
                total += 1
                gaps = validate_scenario_file(yaml_path, fix_stubs=fix_stubs)
                if gaps:
                    gap_count += 1
                    rel = yaml_path.relative_to(ROOT)
                    gap_rows.append((str(rel), gaps))
                # Track slug -> files for the global duplicate-slug check below.
                try:
                    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
                except yaml.YAMLError:
                    data = {}
                slug = str(data.get("slug") or yaml_path.parent.name)
                slug_to_files.setdefault(slug, []).append(str(yaml_path.relative_to(ROOT)))
                if limit and total >= limit:
                    break
            if limit and total >= limit:
                break

        # Duplicate-slug detection (mirrors seed_scenarios' collision guard).
        # Scenario.slug is globally unique, so any slug mapping to >1 file means
        # seeding will silently overwrite scenarios — catch it in CI pre-deploy.
        duplicate_slugs = {s: fs for s, fs in slug_to_files.items() if len(fs) > 1}

        self.stdout.write(f"Scanned {total} scenarios — {gap_count} with gaps, {total - gap_count} clean")
        for rel, gaps in gap_rows[:50]:
            self.stdout.write(f"  {rel}:")
            for g in gaps:
                self.stdout.write(f"    - {g}")
        if len(gap_rows) > 50:
            self.stdout.write(f"  ... and {len(gap_rows) - 50} more")

        if duplicate_slugs:
            self.stdout.write(
                self.style.ERROR(
                    f"\nDuplicate scenario slugs detected ({len(duplicate_slugs)}) — "
                    "these would silently overwrite each other at seed time:"
                )
            )
            for slug in sorted(duplicate_slugs):
                self.stdout.write(f"  slug '{slug}':")
                for path in sorted(duplicate_slugs[slug]):
                    self.stdout.write(f"      - {path}")

        if (options["fail_on_gaps"] and gap_count) or duplicate_slugs:
            sys.exit(1)
