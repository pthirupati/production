"""
Lean tutorial section content — the six-section lesson per course module.

Delegates to the curriculum section writers, then folds in any hand-authored
deep content. The deep-content registry (deep_modules / keyword_deep) is keyed by
the OLD 20-section keys, so we MAP those into the new six sections instead of
dropping the high-signal prose:

    theory + concepts            -> Key concepts
    architecture                 -> Overview
    labs                         -> Hands-on walkthrough
    troubleshooting              -> Common pitfalls & fixes
    notes/security/monitoring/…  -> Key takeaways
"""

from __future__ import annotations

from .curriculum.deep_modules import get_deep_body
from .curriculum.keyword_deep import keyword_deep_body
from .curriculum.section_writers import SECTION_HEADINGS, build_rich_module_sections

# New section key -> ordered list of legacy deep-content keys to fold in.
# Only the highest-signal legacy prose is surfaced; the rest is intentionally
# dropped to keep lessons concise and non-repetitive.
_DEEP_KEY_MAP: dict[str, tuple[str, ...]] = {
    "overview": ("architecture",),
    "concepts": ("theory", "concepts"),
    # "walkthrough" is NOT deep-folded: the writer's shell block + sequence diagram
    # is cleaner than the raw command dumps in the legacy "labs" deep entries.
    "pitfalls": ("troubleshooting",),
    "takeaways": ("notes",),
    # "assess" intentionally has no deep merge — it is the lab CTA + quiz.
}

# Strip a redundant leading legacy "## Heading" so folded prose does not print a
# second section title above the writer's own heading.
_LEGACY_HEADINGS = (
    "## Theory", "## Architecture", "## Core concepts", "## Concepts",
    "## Hands-on labs", "## Labs", "## Troubleshooting",
    "## Notes and key takeaways", "## Notes", "## Monitoring", "## Security practices",
)


def _clean_deep(text: str) -> str:
    text = (text or "").strip()
    for h in _LEGACY_HEADINGS:
        if text.startswith(h):
            text = text[len(h):].lstrip("\n").lstrip()
            break
    return text


def _collect_deep(course_slug: str, module_order: int, module_title: str, new_key: str) -> str:
    """Return folded deep prose for a new section key, or '' if none.

    Prefers hand-authored (course_slug, module) deep content; falls back to
    keyword-triggered deep content matched on the module title.
    """
    parts: list[str] = []
    for legacy_key in _DEEP_KEY_MAP.get(new_key, ()):
        deep = get_deep_body(course_slug, module_order, legacy_key)
        if not deep:
            deep = keyword_deep_body(module_title, legacy_key)
        deep = _clean_deep(deep)
        if deep and deep not in parts:
            parts.append(deep)
    return "\n\n".join(parts)


def build_module_sections(course: dict, module_title: str, level: str) -> list[tuple[str, str, str, str, str]]:
    """Return the six-section lesson for one course module (deep-content folded)."""
    course_slug = course.get("course_slug", "")
    module_order = course.get("_module_order", 0)

    course_with_mod = {**course, "_module_order": module_order}
    sections = build_rich_module_sections(course_with_mod, module_title, level)

    if not course_slug or not module_order:
        return sections

    key_by_heading = {h: k for h, k in SECTION_HEADINGS}
    merged: list[tuple[str, str, str, str, str]] = []
    for heading, body, code, lang, caption in sections:
        new_key = key_by_heading.get(heading, "")
        deep = _collect_deep(course_slug, module_order, module_title, new_key)
        if deep:
            # Fold authored prose UNDER the writer's heading + diagram so the
            # single diagram stays in place and no heading is duplicated.
            body = f"{body}\n\n{deep}"
        merged.append((heading, body, code, lang, caption))
    return merged
