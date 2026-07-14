"""Generate one distinct hero SVG per course from its real components.

Offline + deterministic: reads each course's topic profile (or the curated
per-course component registry) and renders labelled boxes + data-flow arrows
themed per category into::

    frontend/public/tutorials/illustrations/<course>.svg

Usage:
    python manage.py gen_tutorial_illustrations           # all courses w/ profile
    python manage.py gen_tutorial_illustrations --check    # report, write nothing
    python manage.py gen_tutorial_illustrations --course linux-sysadmin-zero-hero
"""
from __future__ import annotations

import re
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.tutorials.course_diagrams import resolve_components, slugify, stable_hash

# Repo layout: backend/apps/tutorials/management/commands/ -> parents[5] == repo root
ILLUSTRATIONS_DIR = (
    Path(__file__).resolve().parents[5]
    / "frontend" / "public" / "tutorials" / "illustrations"
)

# Category → (accent-start, accent-end) gradient. Chosen to echo the existing
# on-brand palette (dark slate bg + a vivid accent per domain).
_CATEGORY_THEME: dict[str, tuple[str, str]] = {
    "linux": ("#4ade80", "#22d3ee"),
    "os": ("#4ade80", "#22d3ee"),
    "container": ("#38bdf8", "#0ea5e9"),
    "cloud": ("#f59e0b", "#f97316"),
    "iac": ("#a78bfa", "#8b5cf6"),
    "database": ("#34d399", "#10b981"),
    "observability": ("#f472b6", "#ec4899"),
    "network": ("#60a5fa", "#3b82f6"),
    "security": ("#f87171", "#ef4444"),
    "cicd": ("#c084fc", "#a855f7"),
    "appdev": ("#facc15", "#eab308"),
    "data": ("#2dd4bf", "#14b8a6"),
    "ai": ("#818cf8", "#6366f1"),
    "infra": ("#fb923c", "#f97316"),
    "general": ("#94a3b8", "#64748b"),
}

# Topic slug → category, for theme selection.
_TOPIC_CATEGORY: dict[str, str] = {
    "linux": "linux", "rhel-linux": "linux", "bash": "os", "windows": "os",
    "docker": "container", "podman": "container", "containerd": "container",
    "kubernetes": "container", "openshift": "container", "helm": "container",
    "terraform": "iac", "pulumi": "iac", "cloudformation": "iac", "packer": "iac",
    "ansible": "iac",
    "aws": "cloud", "azure": "cloud", "gcp": "cloud",
    "database": "database", "postgresql": "database", "mysql": "database",
    "sqlite": "database", "mongodb": "database", "redis": "database",
    "prometheus": "observability", "grafana": "observability",
    "monitoring": "observability", "loki": "observability", "tempo": "observability",
    "jaeger": "observability", "elk": "observability",
    "networking": "network", "vyos": "network", "cisco": "network",
    "mikrotik": "network", "pfsense": "network", "nginx": "network",
    "security": "security", "cybersecurity": "security", "devsecops": "security",
    "iam": "security", "siem": "security", "soc": "security",
    "nmap": "security", "wireshark": "security",
    "git": "cicd", "github": "cicd", "gitlab": "cicd", "bitbucket": "cicd",
    "jenkins": "cicd", "argocd": "cicd", "devops": "cicd",
    "python": "appdev", "backend": "appdev", "django": "appdev", "fastapi": "appdev",
    "express-js": "appdev", "node-js": "appdev", "next-js": "appdev",
    "react": "appdev", "javascript": "appdev", "typescript": "appdev",
    "html": "appdev", "css": "appdev", "java": "appdev", "frontend": "appdev",
    "data-science": "data",
    "ai-engineering": "ai", "ai-infrastructure": "ai", "gpu": "ai",
    "prompt-engineering": "ai",
    "bare-metal": "infra", "maas": "infra", "vmware": "infra",
    "peoplesoft": "infra", "simulation": "general",
}


def _esc(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _wrap_label(text: str, width: int = 16) -> list[str]:
    """Wrap a component label to at most two short lines."""
    words = (text or "").split()
    lines: list[str] = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + (1 if cur else 0) <= width:
            cur = f"{cur} {w}".strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:2] or [text[:width]]


def _theme_for(topic: str, course_slug: str) -> tuple[str, str]:
    for key in (slugify(course_slug), slugify(topic)):
        cat = _TOPIC_CATEGORY.get(key)
        if cat:
            return _CATEGORY_THEME[cat]
    # Trimmed course slug fallback.
    cs = re.sub(r"-(zero-hero|zero-to-hero).*$", "", slugify(course_slug))
    cat = _TOPIC_CATEGORY.get(cs)
    if cat:
        return _CATEGORY_THEME[cat]
    return _CATEGORY_THEME["general"]


def render_course_svg(
    course_slug: str,
    topic: str,
    title: str,
    components: list[tuple[str, str]],
) -> str:
    """Render a lightweight, on-brand SVG showing the course's real components
    as labelled boxes wired with data-flow arrows.
    """
    a0, a1 = _theme_for(topic, course_slug)
    heading = _esc(title or topic or course_slug)
    W, H = 800, 420

    # Lay components across up to two rows depending on count.
    comps = components[:6] or [("stack", topic or "Stack")]
    n = len(comps)
    # Box geometry.
    box_w, box_h = 150, 74
    gap = 26
    top_y = 150

    def _row(items: list[tuple[str, str]], y: int) -> list[str]:
        out: list[str] = []
        count = len(items)
        total_w = count * box_w + (count - 1) * gap
        x0 = (W - total_w) // 2
        centers: list[int] = []
        for i, (_, label) in enumerate(items):
            x = x0 + i * (box_w + gap)
            cx = x + box_w // 2
            centers.append(cx)
            out.append(
                f'  <rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="10" '
                f'fill="#1e293b" stroke="url(#accent)" stroke-width="2"/>'
            )
            lines = _wrap_label(label)
            if len(lines) == 1:
                out.append(
                    f'  <text x="{cx}" y="{y + box_h // 2 + 4}" text-anchor="middle" '
                    f'fill="#e2e8f0" font-family="system-ui,sans-serif" font-size="13" '
                    f'font-weight="600">{_esc(lines[0])}</text>'
                )
            else:
                out.append(
                    f'  <text x="{cx}" y="{y + box_h // 2 - 4}" text-anchor="middle" '
                    f'fill="#e2e8f0" font-family="system-ui,sans-serif" font-size="12.5" '
                    f'font-weight="600">{_esc(lines[0])}</text>'
                )
                out.append(
                    f'  <text x="{cx}" y="{y + box_h // 2 + 14}" text-anchor="middle" '
                    f'fill="#cbd5e1" font-family="system-ui,sans-serif" font-size="12.5" '
                    f'font-weight="600">{_esc(lines[1])}</text>'
                )
        # Horizontal arrows between adjacent boxes on this row.
        for i in range(count - 1):
            x_from = centers[i] + box_w // 2
            x_to = centers[i + 1] - box_w // 2
            ay = y + box_h // 2
            out.append(
                f'  <path d="M{x_from} {ay} H{x_to - 6}" stroke="url(#accent)" '
                f'stroke-width="2" marker-end="url(#arrow)"/>'
            )
        return out, centers

    body: list[str] = []
    if n <= 3:
        rows = [comps]
    else:
        # Split roughly in half across two rows for readability.
        half = (n + 1) // 2
        rows = [comps[:half], comps[half:]]

    row_centers: list[list[int]] = []
    row_ys: list[int] = []
    y = top_y
    for r in rows:
        parts, centers = _row(r, y)
        body.extend(parts)
        row_centers.append(centers)
        row_ys.append(y)
        y += box_h + 60

    # Vertical arrow connecting the last box of row 1 down to first of row 2.
    if len(rows) == 2 and row_centers[0] and row_centers[1]:
        x1 = row_centers[0][-1]
        y1 = row_ys[0] + box_h
        x2 = row_centers[1][0]
        y2 = row_ys[1]
        midy = (y1 + y2) // 2
        body.append(
            f'  <path d="M{x1} {y1} V{midy} H{x2} V{y2 - 6}" stroke="url(#accent)" '
            f'stroke-width="2" fill="none" marker-end="url(#arrow)"/>'
        )

    # Operator entry + observability exit annotations (subtle, on-brand).
    first_cx = row_centers[0][0] if row_centers and row_centers[0] else W // 2
    body.insert(
        0,
        f'  <text x="{first_cx}" y="{top_y - 16}" text-anchor="middle" fill="#64748b" '
        f'font-family="system-ui,sans-serif" font-size="11">operator / user →</text>',
    )
    last_cx = row_centers[-1][-1] if row_centers and row_centers[-1] else W // 2
    last_y = row_ys[-1] + box_h + 22
    body.append(
        f'  <text x="{last_cx}" y="{last_y}" text-anchor="middle" fill="#64748b" '
        f'font-family="system-ui,sans-serif" font-size="11">→ logs &amp; metrics</text>'
    )

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="{heading} architecture">',
        "  <defs>",
        '    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">',
        '      <stop offset="0%" stop-color="#0f172a"/>',
        '      <stop offset="100%" stop-color="#1e293b"/>',
        "    </linearGradient>",
        '    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">',
        f'      <stop offset="0%" stop-color="{a0}"/>',
        f'      <stop offset="100%" stop-color="{a1}"/>',
        "    </linearGradient>",
        '    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" '
        'markerHeight="6" orient="auto-start-reverse">',
        f'      <path d="M0 0 L10 5 L0 10 z" fill="{a1}"/>',
        "    </marker>",
        "  </defs>",
        f'  <rect width="{W}" height="{H}" rx="16" fill="url(#bg)"/>',
        f'  <text x="{W // 2}" y="52" text-anchor="middle" fill="#e2e8f0" '
        f'font-family="system-ui,sans-serif" font-size="26" font-weight="700">{heading}</text>',
        f'  <text x="{W // 2}" y="82" text-anchor="middle" fill="#94a3b8" '
        f'font-family="system-ui,sans-serif" font-size="13">Architecture overview — the real '
        f'components you will operate</text>',
        f'  <rect x="40" y="104" width="{W - 80}" height="{H - 130}" rx="14" fill="#0f172a" '
        f'fill-opacity="0.35" stroke="#334155" stroke-width="1"/>',
        *body,
        "</svg>",
        "",
    ]
    return "\n".join(svg)


class Command(BaseCommand):
    help = "Generate one distinct hero SVG per course from its real components."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true", help="Report only; write nothing")
        parser.add_argument("--course", default="", help="Only (re)generate this course_slug")

    def handle(self, *args, **options):
        from apps.tutorials.management.commands.course_catalog import all_course_definitions
        from apps.tutorials.management.commands.curriculum.topic_profiles import get_profile

        check = options.get("check")
        only = (options.get("course") or "").strip()

        ILLUSTRATIONS_DIR.mkdir(parents=True, exist_ok=True)
        courses = all_course_definitions()
        seen: set[str] = set()
        written = 0
        skipped_no_components: list[str] = []

        for course in courses:
            course_slug = course.get("course_slug", "")
            topic = course.get("topic", "")
            title = course.get("course_title", "") or topic
            if not course_slug or course_slug in seen:
                continue
            seen.add(course_slug)
            if only and course_slug != only:
                continue
            profile = get_profile(topic) or {}
            components = resolve_components(topic, profile, course_slug)
            if not components:
                # No real components — leave to the general.svg fallback.
                skipped_no_components.append(course_slug)
                continue
            svg = render_course_svg(course_slug, topic, title, components)
            target = ILLUSTRATIONS_DIR / f"{course_slug}.svg"
            if check:
                self.stdout.write(f"  would write {target.name} ({len(components)} components)")
            else:
                target.write_text(svg, encoding="utf-8")
                written += 1

        verb = "Would generate" if check else "Generated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {written if not check else len(seen)} course SVGs into "
                f"{ILLUSTRATIONS_DIR}"
            )
        )
        if skipped_no_components:
            self.stdout.write(
                f"  {len(skipped_no_components)} courses had no components "
                f"(use general.svg fallback): {', '.join(sorted(skipped_no_components)[:10])}"
                + (" ..." if len(skipped_no_components) > 10 else "")
            )
