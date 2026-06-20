"""Generator framework for FixitLab browser-IDE coding scenarios.

Integrity is the whole point. Every scenario carries TWO bodies of source:
  - ``broken``    : the starter file content shipped to the learner. For
                    fix-bug scenarios this is buggy; for implement-missing it is
                    an unimplemented stub. It MUST fail the hidden tests.
  - ``reference`` : a known-correct solution used ONLY at generation time to
                    prove the tests can pass. It is never written into YAML.

Before any YAML is emitted, ``verify_scenario`` runs the scenario's tests
(visible + hidden) through the REAL backend grader (apps.labs.code_exec) twice:
  1. against ``broken``    -> must NOT all_pass   (fail-before)
  2. against ``reference`` -> must all_pass        (pass-after)

A scenario that does not satisfy both is refused — it is never written. This is
the same fail-closed philosophy as code_exec.py itself.

Run via scripts/coding_gen/generate.py (which wires Django so code_exec imports).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Optional

import yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCEN_ROOT = os.path.join(REPO_ROOT, "scenarios")


@dataclass
class Test:
    name: str
    code: str


@dataclass
class Scenario:
    slug: str
    title: str
    language: str            # "python" | "javascript"
    kind: str                # fix | impl | logfix | review (informational)
    difficulty: str          # easy | medium | hard
    description: str
    objectives: list[str]
    instructions: str
    entrypoint: str
    broken: str              # starter file content (must FAIL)
    reference: str           # correct solution (must PASS) — never written
    visible_tests: list[Test]
    hidden_tests: list[Test]
    hints: list[str]                       # exactly 3
    initial_state: str = ""
    solution_explanation: str = ""
    scenario_type: str = "fix"             # fix | do (matches model choices)
    timeout: int = 8
    # Extra files (helpers) that are NOT the entrypoint. The grader concatenates
    # non-entry files first, so helpers they define are in scope. Each is
    # (path, content, readonly).
    extra_files: list[tuple[str, str, bool]] = field(default_factory=list)
    category: Optional[str] = None

    def all_tests_payload(self) -> list[dict]:
        """visible + hidden as the grader expects (entrypoint graded)."""
        return (
            [{"name": t.name, "code": t.code, "hidden": False} for t in self.visible_tests]
            + [{"name": t.name, "code": t.code, "hidden": True} for t in self.hidden_tests]
        )

    def _graded_source(self, body: str) -> str:
        """Mirror public_api grading: non-entry files first, entry last."""
        parts = [c for (_p, c, _ro) in self.extra_files]
        parts.append(body)
        return "\n".join(parts)


def verify_scenario(scn: Scenario, grade_submission) -> list[str]:
    """Return a list of integrity problems (empty == passes both gates)."""
    problems: list[str] = []
    if scn.language not in ("python", "javascript"):
        problems.append(f"{scn.slug}: language {scn.language} not auto-graded")
        return problems
    if len(scn.hints) != 3:
        problems.append(f"{scn.slug}: expected 3 hints, got {len(scn.hints)}")
    if not scn.visible_tests:
        problems.append(f"{scn.slug}: no visible tests")
    if not scn.hidden_tests:
        problems.append(f"{scn.slug}: no hidden tests")

    tests = scn.all_tests_payload()

    # 1) broken starter must FAIL
    broken_res = grade_submission(
        scn.language, scn._graded_source(scn.broken), tests, timeout=scn.timeout
    )
    if broken_res.all_passed:
        problems.append(f"{scn.slug}: BROKEN starter PASSES tests (no fail-before)")

    # 2) reference must PASS everything
    ref_res = grade_submission(
        scn.language, scn._graded_source(scn.reference), tests, timeout=scn.timeout
    )
    if not ref_res.all_passed:
        failing = [o.name for o in ref_res.outcomes if not o.passed]
        problems.append(
            f"{scn.slug}: REFERENCE does NOT pass "
            f"(ran={ref_res.ran}, err={ref_res.error[:160]!r}, failing={failing})"
        )
    return problems


# ── YAML emission ────────────────────────────────────────────────────────────

# Use literal block scalars for multi-line strings so the generated YAML is
# readable and round-trips cleanly.
class _LiteralStr(str):
    pass


def _literal_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="|")


yaml.add_representer(_LiteralStr, _literal_representer)


def _block(s: str) -> _LiteralStr:
    # Ensure trailing newline so block scalar uses clean clip semantics.
    if not s.endswith("\n"):
        s = s + "\n"
    return _LiteralStr(s)


def scenario_to_dict(scn: Scenario) -> dict:
    cat = scn.category or (
        "Python Development" if scn.language == "python" else "JavaScript Development"
    )
    files = [
        {"path": p, "content": _block(c), "readonly": ro}
        for (p, c, ro) in scn.extra_files
    ]
    files.append({"path": scn.entrypoint, "content": _block(scn.broken), "readonly": False})

    hints = [
        {"order": i + 1, "cost": 10 + i * 10, "content": h}
        for i, h in enumerate(scn.hints)
    ]

    return {
        "title": scn.title,
        "slug": scn.slug,
        "category": cat,
        "description": scn.description,
        "difficulty": scn.difficulty,
        "scenario_type": scn.scenario_type,
        "lab_mode": "simulation",
        "simulation_type": "python",   # IDE runtime flag; language lives in coding_spec
        "coding_mode": True,
        "jira_priority": "Medium",
        "time_limit": 1500,
        "max_score": 100,
        "is_free": True,
        "dual_terminal": False,
        "objectives": scn.objectives,
        "initial_state": scn.initial_state or scn.description,
        "solution_explanation": _block(scn.solution_explanation) if scn.solution_explanation else "",
        "coding_spec": {
            "language": scn.language,
            "entrypoint": scn.entrypoint,
            "kind": scn.kind,
            "instructions": _block(scn.instructions),
            "files": files,
            "visible_tests": [
                {"name": t.name, "code": _block(t.code)} for t in scn.visible_tests
            ],
            "hidden_tests": [
                {"name": t.name, "code": _block(t.code)} for t in scn.hidden_tests
            ],
            "timeout": scn.timeout,
        },
        "hints": hints,
    }


def write_scenario(scn: Scenario) -> str:
    lang_dir = "python" if scn.language == "python" else "javascript"
    out_dir = os.path.join(SCEN_ROOT, lang_dir, scn.slug)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "scenario.yaml")
    data = scenario_to_dict(scn)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, sort_keys=False, allow_unicode=True, width=100)
    return path
