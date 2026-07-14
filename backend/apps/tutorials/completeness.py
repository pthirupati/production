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
FLOWCHART_RE = re.compile(r"```mermaid\s*\n\s*flowchart\b", re.I)
SEQUENCE_RE = re.compile(r"```mermaid\s*\n\s*sequenceDiagram\b", re.I)
# A ``$``-prefixed command line inside a bash block, with at least one following
# non-command line == a shell block that carries expected output.
SHELL_WITH_OUTPUT_RE = re.compile(
    r"```(?:bash|shell|sh)\s*\n(?:.*\n)*?\s*\$ .+\n(?!\s*\$)(?!```).+", re.I
)

# The lean six-section lesson. Every course module must expose all six.
REQUIRED_SECTION_HINTS = {
    "overview": ("overview",),
    "concepts": ("key concepts", "concept"),
    "walkthrough": ("hands-on walkthrough", "walkthrough", "hands-on"),
    "pitfalls": ("common pitfalls", "pitfall"),
    "assess": ("practice & assess", "practice", "assess", "quiz"),
    "takeaways": ("key takeaways", "takeaway"),
}

# Legacy 20-section headings — if two or more of these still appear, the lesson
# is the old bloated structure and must fail the gate.
LEGACY_SECTION_HEADINGS = (
    "interactive simulations", "projects", "scenario questions",
    "certification exam prep", "enterprise production examples",
    "performance tuning", "real incidents", "root cause analysis",
    "interview questions", "use cases",
)

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


QUIZ_HEADING_HINTS = ("assess", "assessment", "quiz", "checkpoint", "practice & assess")


def has_quiz(tutorial) -> bool:
    for section in tutorial.sections.all():
        heading = (section.heading or "").lower()
        if section.quiz_json or any(k in heading for k in QUIZ_HEADING_HINTS):
            quiz = section.quiz_json or build_module_quiz(tutorial.topic, tutorial.title)
            if len(quiz.get("questions") or []) >= 5:
                return True
    return False


def validate_tutorial(tutorial) -> TutorialCompleteness:
    """Validate a tutorial against the lean six-section structure.

    Course modules (``course_slug`` set) are held to the full new contract:
    exactly six sections, exactly one architecture (flowchart) diagram + one
    sequenceDiagram, a shell block with expected output, a 5-question quiz, a
    linked lab, and >=2 callouts — and they FAIL if the old 20-section bloat or
    duplicate diagrams are present.

    Flat/standalone tutorials (no ``course_slug``) keep the looser contract: the
    required rich blocks must appear somewhere in the lesson.
    """
    sections = list(tutorial.sections.all())
    blob = _section_blob(sections)
    lower = blob.lower()
    headings = " ".join((s.heading or "").lower() for s in sections)
    is_course_module = bool(tutorial.course_slug)
    gaps: list[str] = []

    mermaid_count = len(MERMAID_RE.findall(blob))
    flowcharts = len(FLOWCHART_RE.findall(blob))
    sequences = len(SEQUENCE_RE.findall(blob))

    # ── Diagrams ──────────────────────────────────────────────────────────
    if mermaid_count == 0:
        gaps.append("missing Mermaid/diagram block")
    if is_course_module:
        if flowcharts != 1:
            gaps.append(f"expected exactly 1 architecture (flowchart) diagram, found {flowcharts}")
        if sequences != 1:
            gaps.append(f"expected exactly 1 sequenceDiagram, found {sequences}")
        if mermaid_count > 2:
            gaps.append(f"duplicate/extra diagrams: {mermaid_count} Mermaid blocks (max 2: 1 arch + 1 sequence)")

    # ── Shell walkthrough with expected output ────────────────────────────
    has_shell = SHELL_RE.search(blob) or any(
        (s.code_language or "").lower() in {"bash", "shell", "sh"} and (s.code or "").strip()
        for s in sections
    )
    if not has_shell:
        gaps.append("missing shell command block")
    elif is_course_module and not SHELL_WITH_OUTPUT_RE.search(blob):
        gaps.append("shell block has no expected output ($-prefixed command + output)")

    if len(CALLOUT_RE.findall(blob)) < 2:
        gaps.append("fewer than 2 callouts")
    if not has_quiz(tutorial):
        gaps.append("missing 5-question quiz")
    if not tutorial.scenario_slug:
        gaps.append("missing linked lab/scenario_slug")

    # ── Section structure ─────────────────────────────────────────────────
    if is_course_module:
        # Reject the old 20-section bloat.
        legacy_hits = [h for h in LEGACY_SECTION_HEADINGS if h in headings]
        if len(legacy_hits) >= 2:
            gaps.append(f"legacy 20-section bloat detected (headings: {', '.join(legacy_hits[:4])}…)")
        if len(sections) > 8:
            gaps.append(f"too many sections ({len(sections)}); lean lesson is 6 (+ optional quiz)")
        # Require all six lean sections by heading.
        for key, aliases in REQUIRED_SECTION_HINTS.items():
            if not any(alias in headings for alias in aliases):
                gaps.append(f"missing required lesson section: {key}")
        # A comparison table belongs in Key concepts.
        if not TABLE_RE.search(blob):
            gaps.append("missing comparison table (Key concepts)")
    else:
        # Flat tutorials: the blocks must appear somewhere.
        if not TABLE_RE.search(blob):
            gaps.append("missing comparison/cheat-sheet table")

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


# Headings that own a specific rich block. Enrichment is TARGETED: a diagram,
# hero image, table, or shell block is only ever injected into the single section
# that is supposed to carry it — so the same diagram/image never repeats across a
# lesson (that per-section injection was the old duplication source).
_OVERVIEW_HINTS = ("overview", "theory")
_WALKTHROUGH_HINTS = ("hands-on", "walkthrough", "worked example")
_CONCEPTS_HINTS = ("concept", "key concepts")


_STRUCTURED_HINTS = _OVERVIEW_HINTS + _WALKTHROUGH_HINTS + _CONCEPTS_HINTS + (
    "pitfall", "common pitfalls", "takeaway", "key takeaways", "assess",
    "prerequisite", "use case", "summary",
)


def enrich_body(topic: str, title: str, body: str, heading: str = "", is_first: bool = False) -> str:
    """Fill in any missing rich block for THIS section, idempotently and targeted.

    Unlike the old behaviour (which appended a diagram/image/table/shell to *every*
    section — the source of duplicate diagrams), enrichment now only adds the block
    a given section is meant to carry, based on its heading:

    * Overview            → hero image + exactly one architecture diagram
    * Hands-on walkthrough→ one shell block (with expected output)
    * Key concepts        → one comparison/cheat-sheet table

    For flat/standalone tutorials whose headings are free-text (not one of the
    structured phase headings), the block top-up is applied ONCE, on the first
    section (``is_first``), so those pages still clear the completeness gate without
    repeating diagrams/images across every section.

    A section that already contains a block is left untouched (idempotent). Strips
    any prior auto-enrichment (including the legacy generic mermaid) so re-seeding
    refreshes lessons cleanly.
    """
    body = fix_broken_prose(strip_auto_enrichment(body or ""))
    h = (heading or "").lower()
    additions: list[str] = []

    structured = bool(h) and any(k in h for k in _STRUCTURED_HINTS)
    # The "Practice & assess" section is the quiz/lab-CTA carrier — never inject a
    # diagram/image/shell/table there (its "practice" text must not trip walkthrough).
    is_assess = "assess" in h
    is_overview = (not is_assess) and any(k in h for k in _OVERVIEW_HINTS)
    is_walkthrough = (not is_assess) and any(k in h for k in _WALKTHROUGH_HINTS)
    is_concepts = (not is_assess) and any(k in h for k in _CONCEPTS_HINTS)
    # A free-text heading that is not part of the structured lesson: this is a flat
    # tutorial. Carry the full top-up on the first section only.
    flat_carrier = (not structured) and (is_first or not h)

    # Hero image: exactly once per lesson — Overview section (or a flat carrier).
    if (is_overview or flat_carrier) and not IMAGE_RE.search(body):
        additions.append(topic_illustration(topic, title))

    # Architecture diagram: Overview only (or a flat carrier missing any diagram).
    if (is_overview or flat_carrier) and not MERMAID_RE.search(body):
        additions.append(architecture_diagram(topic, title=title))

    # Shell block with expected output: walkthrough only (or a flat carrier).
    if (is_walkthrough or flat_carrier) and not CODE_RE.search(body):
        additions.append(shell_practice_block(topic, title))

    # One comparison table: concepts section only (or a flat carrier).
    if (is_concepts or flat_carrier) and not TABLE_RE.search(body):
        additions.append(reference_table(topic, title))

    # Ensure at least one callout on any section that has none, so the lesson as
    # a whole always clears the ≥2-callout gate without stacking duplicates.
    if not CALLOUT_RE.search(body):
        additions.append(
            f"> [!NOTE] **{title or topic}** — keep the Overview diagram in mind, run each "
            "command, and compare the output before and after every change."
        )

    if additions:
        return body.rstrip() + f"\n\n{ENRICHMENT_HEADER}\n\n" + "\n\n".join(additions)
    return body
