"""Tutorial richness checks and deterministic enrichment helpers.

The public tutorial model intentionally stores lesson content as Markdown-ish
text. These helpers define the required authoring surface without adding a risky
schema migration: diagrams, callouts, tables, shell/code examples, quizzes, and
linked labs are all discoverable from the current Tutorial/TutorialSection
fields and from the deterministic quiz generator.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .quiz_bank import build_module_quiz
from .tutorial_enrichment import (
    ENRICHMENT_HEADER,
    architecture_diagram,
    fix_broken_prose,
    practical_summary,
    reference_table,
    shell_practice_block,
    strip_auto_enrichment,
    topic_illustration,
)

MERMAID_RE = re.compile(r"```mermaid\b", re.I)
CODE_RE = re.compile(r"```(?!mermaid\b)[a-zA-Z0-9_+-]*\n", re.I)
TABLE_RE = re.compile(r"^\s*\|.+\|\s*$\n^\s*\|?[\s:|-]+\|", re.M)
CALLOUT_RE = re.compile(r"^\s*>\s*\[!(NOTE|TIP|WARNING|DANGER|GOTCHA)\]", re.I | re.M)
SHELL_RE = re.compile(r"```(bash|shell|sh)\b", re.I)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")

REQUIRED_SECTION_HINTS = {
    "overview": ("overview", "why it matters", "theory"),
    "prerequisites": ("prerequisite", "before you start"),
    "core_concept": ("core concept", "concept"),
    "architecture": ("architecture", "flow diagram", "diagram"),
    "step_by_step": ("step-by-step", "hands-on", "labs"),
    "worked_example": ("worked example", "example", "simulation"),
    "errors": ("common error", "troubleshoot", "incident"),
    "best_practices": ("best practice", "security", "production"),
    "cheat_sheet": ("cheat", "reference", "notes"),
    "summary": ("summary", "takeaways", "notes"),
    "quiz": ("quiz", "assessment"),
    "linked_lab": ("linked lab", "hands-on lab", "scenario"),
}

ROOT = Path(__file__).resolve().parents[3]
SCENARIOS_ROOT = ROOT / "scenarios"


@dataclass(frozen=True)
class TutorialCompleteness:
    slug: str
    gaps: list[str]


def _section_blob(sections: Iterable) -> str:
    chunks: list[str] = []
    for section in sections:
        chunks.extend([
            getattr(section, "heading", "") or "",
            getattr(section, "body", "") or "",
            getattr(section, "code", "") or "",
        ])
    return "\n\n".join(chunks)


def has_quiz(tutorial) -> bool:
    for section in tutorial.sections.all():
        heading = (section.heading or "").lower()
        if section.quiz_json or any(k in heading for k in ("assessment", "quiz", "checkpoint")):
            quiz = section.quiz_json or build_module_quiz(tutorial.topic, tutorial.title)
            if len(quiz.get("questions") or []) >= 5:
                return True
    return False


def validate_tutorial(tutorial) -> TutorialCompleteness:
    sections = list(tutorial.sections.all())
    blob = _section_blob(sections)
    lower = blob.lower()
    headings = " ".join((s.heading or "").lower() for s in sections)
    gaps: list[str] = []

    if not MERMAID_RE.search(blob):
        gaps.append("missing Mermaid/diagram block")
    if not CODE_RE.search(blob) and not any((s.code or "").strip() for s in sections):
        gaps.append("missing fenced code or section code block")
    if not SHELL_RE.search(blob) and not any((s.code_language or "").lower() in {"bash", "shell", "sh"} and (s.code or "").strip() for s in sections):
        gaps.append("missing shell command block")
    if not TABLE_RE.search(blob):
        gaps.append("missing comparison/cheat-sheet table")
    if len(CALLOUT_RE.findall(blob)) < 2:
        gaps.append("fewer than 2 callouts")
    if not has_quiz(tutorial):
        gaps.append("missing 5-question quiz")
    if not tutorial.scenario_slug:
        gaps.append("missing linked lab/scenario_slug")

    for key, aliases in REQUIRED_SECTION_HINTS.items():
        haystack = headings if key == "quiz" else lower + "\n" + headings
        if not any(alias in haystack for alias in aliases):
            gaps.append(f"missing required lesson section: {key}")

    return TutorialCompleteness(slug=tutorial.slug, gaps=gaps)


def _slugish(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")


def default_linked_lab_slug(topic: str) -> str:
    """Best-effort lab link used by the seeder when a tutorial lacks one."""
    tech = _slugish(topic)
    aliases = {
        "ai": "ai-ml",
        "ai-agents": "ai-ml",
        "ai-engineering": "ai-ml",
        "ai-infrastructure": "gpu",
        "argocd": "devops",
        "argocd-gitops": "devops",
        "aws": "terraform",
        "azure": "terraform",
        "backend": "nodejs",
        "backend-api": "nodejs",
        "bash": "shell-script",
        "bitbucket": "devops",
        "cloudformation": "terraform",
        "containerd": "docker",
        "css": "html",
        "cybersecurity": "security",
        "devsecops": "security",
        "express": "nodejs",
        "express-js": "nodejs",
        "fastapi": "python",
        "frontend": "react",
        "gcp": "terraform",
        "git": "devops",
        "github": "devops",
        "gitlab": "devops",
        "helm": "kubernetes",
        "iam": "security",
        "loki": "grafana",
        "maas": "baremetal",
        "mikrotik": "networking",
        "monitoring": "prometheus",
        "next-js": "react",
        "nextjs": "react",
        "nginx": "linux",
        "openshift": "kubernetes",
        "packer": "terraform",
        "podman": "docker",
        "pulumi": "terraform",
        "siem": "security",
        "soc": "security",
        "tempo": "grafana",
        "typescript": "javascript",
        "vyos": "networking",
        "html-css": "html",
        "rhel": "rhel-linux",
    }
    tech = aliases.get(tech, tech)
    candidate = f"academy-{tech}-001-learn-{_topic_first_concept(tech)}"
    if (SCENARIOS_ROOT / tech / candidate / "scenario.yaml").is_file():
        return candidate
    matches = sorted((SCENARIOS_ROOT / tech).glob(f"academy-{tech}-001-*/scenario.yaml")) if (SCENARIOS_ROOT / tech).is_dir() else []
    if matches:
        return matches[0].parent.name
    # Final fallback keeps completion possible for broad catalogue topics that
    # do not yet have a same-name scenario folder (for example ArgoCD/Azure).
    return "academy-linux-001-learn-users-groups"


def _topic_first_concept(tech: str) -> str:
    return {
        "linux": "users-groups",
        "rhel-linux": "subscription-repos",
        "docker": "images-layers",
        "kubernetes": "pods",
        "terraform": "providers",
        "ansible": "inventory",
        "devops": "git-flow",
        "python": "venv",
        "nodejs": "express",
        "react": "components",
        "html": "semantic-html",
        "java": "maven",
        "shell-script": "variables",
        "database": "backup",
        "mysql": "indexes",
        "postgresql": "roles",
        "sqlite": "schema",
        "grafana": "datasources",
        "prometheus": "scrape-config",
        "security": "ssh-hardening",
        "nmap": "tcp-scan",
        "wireshark": "filters",
        "vmware": "vm-lifecycle",
        "windows": "active-directory",
    }.get(tech, "fundamentals")


def enrich_body(topic: str, title: str, body: str) -> str:
    """Append missing rich blocks to authored Markdown, idempotently.

    Strips any prior auto-enrichment (including the legacy generic mermaid) so
    re-seeding refreshes lessons with topic-specific diagrams and commands.
    """
    body = fix_broken_prose(strip_auto_enrichment(body or ""))
    additions: list[str] = []
    if not IMAGE_RE.search(body):
        additions.append(topic_illustration(topic, title))
    if not CALLOUT_RE.search(body):
        additions.append(
            f"> [!NOTE] **{title or topic}** — study the architecture diagram, run the "
            "commands below in order, then practice the linked lab."
        )
        additions.append(
            "> [!TIP] Copy commands into the integrated terminal. Compare output before "
            "and after each change — that diff is your evidence."
        )
    if not MERMAID_RE.search(body):
        additions.append(architecture_diagram(topic, title=title))
    if not TABLE_RE.search(body):
        additions.append(reference_table(topic, title))
    if not CODE_RE.search(body):
        additions.append(shell_practice_block(topic, title))
    if "hands-on playbook" not in body.lower():
        additions.append(practical_summary(topic, title))
    if additions:
        return body.rstrip() + f"\n\n{ENRICHMENT_HEADER}\n\n" + "\n\n".join(additions)
    return body
