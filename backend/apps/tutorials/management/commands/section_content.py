"""
Rich tutorial section content — every module ships the full enterprise learning structure.

Delegates to curriculum engine with optional hand-authored deep overrides.
"""

from __future__ import annotations

from .curriculum.deep_modules import get_deep_body
from .curriculum.keyword_deep import keyword_deep_body
from .curriculum.section_writers import SECTION_HEADINGS, build_rich_module_sections

DEEP_MERGE_KEYS = frozenset({
    "theory", "architecture", "concepts", "use_cases", "labs", "troubleshooting",
    "interview", "notes", "monitoring", "security", "enterprise",
})


def build_module_sections(course: dict, module_title: str, level: str) -> list[tuple[str, str, str, str, str]]:
    """Return full 19-section tuples for one course module."""
    course_slug = course.get("course_slug", "")
    module_order = course.get("_module_order", 0)

    # Pass module order through course dict for deep lookup
    course_with_mod = {**course, "_module_order": module_order}
    sections = build_rich_module_sections(course_with_mod, module_title, level)

    if not course_slug or not module_order:
        return sections

    merged: list[tuple[str, str, str, str, str]] = []
    for heading, body, code, lang, caption in sections:
        key = next((k for h, k in SECTION_HEADINGS if h == heading), "")
        deep = get_deep_body(course_slug, module_order, key)
        kw = keyword_deep_body(module_title, key) if not deep else None
        footer = (
            f"\n\n**Course:** {course.get('course_title', '')} · "
            f"Module {module_order} · {level} track"
        )
        if deep and key in DEEP_MERGE_KEYS:
            body = deep + "\n\n---\n\n" + body + footer
        elif deep:
            body = deep + footer
        elif kw:
            body = kw + "\n\n---\n\n" + body
        merged.append((heading, body, code, lang, caption))
    return merged
