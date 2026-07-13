"""Map tutorial topics and technology learning paths to scenario slugs.

Scans the scenarios/ tree so linking works before DB seed; sync_* helpers
update Technology.learning_path and Tutorial.scenario_slug after seed.
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import yaml

CATEGORY_ORDER = {
    "Core Skills": 0,
    "Build Lab": 1,
    "Operations": 2,
    "Troubleshooting": 3,
    "Production": 4,
    "Security": 5,
    "Automation": 6,
    "Observability": 7,
    "Backup & Recovery": 8,
    "Cross-Technology": 9,
}

MODULE_CATEGORY_HINTS: dict[int, list[str]] = {
    1: ["Core Skills"],
    2: ["Core Skills", "Build Lab"],
    3: ["Build Lab"],
    4: ["Build Lab", "Operations"],
    5: ["Operations"],
    6: ["Troubleshooting"],
    7: ["Troubleshooting", "Production"],
    8: ["Production", "Security"],
    9: ["Security", "Automation"],
    10: ["Cross-Technology", "Observability", "Backup & Recovery"],
}

TOPIC_TO_TECH_SLUG: dict[str, str] = {
    "Linux": "linux",
    "RHEL": "rhel-linux",
    "RHEL Linux": "rhel-linux",
    "Docker": "docker",
    "Kubernetes": "kubernetes",
    "Terraform": "terraform",
    "Ansible": "ansible",
    "Networking": "networking",
    "VMware": "vmware",
    "Windows": "windows",
    "Python": "python",
    "Java": "java",
    "JavaScript": "javascript",
    "React": "react",
    "Node.js": "nodejs",
    "HTML": "html",
    "DevOps": "devops",
    "Security": "security",
    "Cybersecurity": "security",
    "DevSecOps": "security",
    "Grafana": "grafana",
    "Prometheus": "prometheus",
    "Monitoring": "prometheus",
    "PostgreSQL": "postgresql",
    "MySQL": "mysql",
    "SQLite": "sqlite",
    "Database": "database",
    "GPU": "gpu",
    "Bare Metal": "baremetal",
    "AI": "ai-ml",
    "AI / ML": "ai-ml",
    "Data Science": "data-science",
    "Prompt Engineering": "prompt-engineering",
    "Bash": "shell-script",
    "Shell Scripting": "shell-script",
    "Shell Script": "shell-script",
    "Nmap": "nmap",
    "Wireshark": "wireshark",
    "PeopleSoft": "peoplesoft",
    "Simulation": "simulation",
    "Git": "devops",
    "GitHub": "devops",
    "GitLab": "devops",
    "Helm": "kubernetes",
    "Nginx": "html",
    "Redis": "database",
    "ELK": "grafana",
    "AWS": "devops",
    "Azure": "devops",
    "GCP": "devops",
}

TECH_TO_TUTORIAL_TOPICS: dict[str, list[str]] = {
    "linux": ["Linux"],
    "rhel-linux": ["RHEL", "RHEL Linux"],
    "shell-script": ["Bash", "Shell Scripting"],
    "docker": ["Docker"],
    "kubernetes": ["Kubernetes"],
    "terraform": ["Terraform"],
    "ansible": ["Ansible"],
    "networking": ["Networking"],
    "vmware": ["VMware"],
    "windows": ["Windows"],
    "python": ["Python"],
    "java": ["Java"],
    "javascript": ["JavaScript"],
    "react": ["React"],
    "nodejs": ["Node.js"],
    "html": ["HTML"],
    "devops": ["DevOps"],
    "security": ["Security", "Cybersecurity", "DevSecOps"],
    "grafana": ["Grafana"],
    "prometheus": ["Prometheus", "Monitoring"],
    "postgresql": ["PostgreSQL"],
    "mysql": ["MySQL"],
    "sqlite": ["SQLite"],
    "database": ["Database"],
    "gpu": ["GPU"],
    "baremetal": ["Bare Metal"],
    "ai-ml": ["AI", "AI / ML"],
    "data-science": ["Data Science"],
    "prompt-engineering": ["Prompt Engineering"],
    "nmap": ["Nmap"],
    "wireshark": ["Wireshark"],
    "peoplesoft": ["PeopleSoft"],
    "simulation": ["Simulation"],
}

LEARNING_PATH_LIMIT = 30
_ACADEMY_SEQ = re.compile(r"academy-[\w-]+-(\d+)-")

# Difficulty ordering for beginner learning paths: each tech's ordered lab list
# ramps easy -> medium -> hard. Unknown/missing difficulty defaults to medium.
DIFFICULTY_RANK = {"easy": 0, "medium": 1, "hard": 2}


def _difficulty_rank(meta_or_value) -> int:
    """Return the difficulty rank (0=easy,1=medium,2=hard).

    Accepts either a meta dict (with a ``difficulty`` key) or a raw string.
    Unknown/missing difficulty defaults to medium (1).
    """
    if isinstance(meta_or_value, dict):
        value = meta_or_value.get("difficulty")
    else:
        value = meta_or_value
    return DIFFICULTY_RANK.get((value or "").strip().lower(), 1)


def scenarios_root() -> Path:
    for candidate in (
        Path("/scenarios"),
        Path(__file__).resolve().parents[3] / "scenarios",
    ):
        if candidate.is_dir():
            return candidate
    return Path(__file__).resolve().parents[3] / "scenarios"


def topic_to_tech_slug(topic: str | None) -> str | None:
    if not topic:
        return None
    slug = TOPIC_TO_TECH_SLUG.get(topic.strip())
    if slug:
        return slug
    normalized = topic.strip().lower().replace(" ", "-").replace("/", "-")
    root = scenarios_root()
    if (root / normalized).is_dir():
        return normalized
    return None


def _slug_sort_key(slug: str) -> tuple:
    match = _ACADEMY_SEQ.match(slug)
    if match:
        return (0, int(match.group(1)), slug)
    return (1, 0, slug)


def _read_scenario_meta(scenario_dir: Path) -> dict | None:
    yaml_path = scenario_dir / "scenario.yaml"
    if not yaml_path.is_file():
        return None
    try:
        with open(yaml_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except (OSError, yaml.YAMLError):
        return None
    slug = data.get("slug") or scenario_dir.name
    category = data.get("category") or "General"
    difficulty = (data.get("difficulty") or "medium").strip().lower()
    return {
        "slug": slug,
        "category": category,
        "is_free": bool(data.get("is_free")),
        "title": data.get("title") or slug,
        "difficulty": difficulty,
    }


@lru_cache(maxsize=1)
def build_scenario_index() -> dict[str, dict]:
    """Return {tech_slug: {by_category, ordered, meta_by_slug}} from filesystem."""
    root = scenarios_root()
    index: dict[str, dict] = {}

    if not root.is_dir():
        return index

    for tech_dir in sorted(root.iterdir()):
        if not tech_dir.is_dir() or tech_dir.name in ("shared",):
            continue
        tech_slug = tech_dir.name
        by_category: dict[str, list[str]] = {}
        meta_by_slug: dict[str, dict] = {}
        entries: list[tuple] = []

        for scenario_dir in sorted(tech_dir.iterdir()):
            if not scenario_dir.is_dir():
                continue
            meta = _read_scenario_meta(scenario_dir)
            if not meta:
                continue
            slug = meta["slug"]
            cat = meta["category"]
            by_category.setdefault(cat, []).append(slug)
            meta_by_slug[slug] = meta
            cat_rank = CATEGORY_ORDER.get(cat, 50)
            # Difficulty is the PRIMARY ordering key (after is_free) so each tech's
            # path ramps easy -> medium -> hard before category/sequence tie-breaks.
            entries.append(
                (
                    0 if meta["is_free"] else 1,
                    _difficulty_rank(meta),
                    cat_rank,
                    *_slug_sort_key(slug),
                    slug,
                )
            )

        # Per-category lists also order difficulty-first (easy -> medium -> hard),
        # then academy-sequence/slug as a stable tie-break.
        for cat in by_category:
            by_category[cat] = sorted(
                by_category[cat],
                key=lambda s: (_difficulty_rank(meta_by_slug.get(s, {})), _slug_sort_key(s)),
            )

        ordered = [e[-1] for e in sorted(entries)]
        index[tech_slug] = {
            "by_category": by_category,
            "ordered": ordered,
            "meta_by_slug": meta_by_slug,
        }

    return index


def clear_scenario_index_cache() -> None:
    build_scenario_index.cache_clear()


def resolve_module_scenario_slug(topic: str | None, module_order: int) -> str:
    tech_slug = topic_to_tech_slug(topic)
    if not tech_slug:
        return ""
    index = build_scenario_index().get(tech_slug)
    if not index:
        return ""

    hints = MODULE_CATEGORY_HINTS.get(module_order, ["Core Skills"])
    for cat in hints:
        slugs = index["by_category"].get(cat, [])
        if slugs:
            offset = max(0, module_order - 1) % len(slugs)
            return slugs[offset]

    ordered = index.get("ordered") or []
    if not ordered:
        return ""
    offset = max(0, module_order - 1) % len(ordered)
    return ordered[offset]


def build_learning_path_steps(tech_slug: str, limit: int = LEARNING_PATH_LIMIT) -> list[dict]:
    index = build_scenario_index().get(tech_slug)
    if not index:
        return []

    steps: list[dict] = []
    seen: set[str] = set()
    for slug in index["ordered"]:
        if slug in seen:
            continue
        seen.add(slug)
        meta = index["meta_by_slug"].get(slug, {})
        category = meta.get("category") or "Lab"
        title = meta.get("title") or category
        steps.append(
            {
                "title": title,
                "scenario_slug": slug,
                "description": f"{category} — hands-on lab",
            }
        )
        if len(steps) >= limit:
            break
    return steps


def enrich_catalog_specs(specs: list[dict]) -> list[dict]:
    for spec in specs:
        if spec.get("scenario_slug"):
            continue
        spec["scenario_slug"] = resolve_module_scenario_slug(
            spec.get("topic"),
            int(spec.get("module_order") or 1),
        )
    return specs


def sync_tutorial_scenario_links(stdout=None, style=None) -> dict:
    from apps.tutorials.models import Tutorial

    clear_scenario_index_cache()
    updated = 0
    linked = 0

    for tutorial in Tutorial.objects.all().only("id", "topic", "module_order", "scenario_slug"):
        slug = resolve_module_scenario_slug(tutorial.topic, tutorial.module_order or 1)
        if not slug:
            continue
        if tutorial.scenario_slug != slug:
            Tutorial.objects.filter(pk=tutorial.pk).update(scenario_slug=slug)
            updated += 1
        linked += 1

    msg = f"Tutorial scenario links: {linked} resolved, {updated} updated."
    if stdout and style:
        stdout.write(style.SUCCESS(msg))
    elif stdout:
        stdout.write(msg)
    return {"linked": linked, "updated": updated}


def sync_technology_learning_paths(stdout=None, style=None) -> dict:
    from apps.question_bank.models import Scenario, Technology

    clear_scenario_index_cache()
    updated = 0
    skipped = 0

    for tech in Technology.objects.filter(is_active=True):
        candidate_steps = build_learning_path_steps(tech.slug)
        if not candidate_steps:
            skipped += 1
            continue

        slugs = [s["scenario_slug"] for s in candidate_steps]
        existing = set(
            Scenario.objects.filter(
                technology=tech,
                slug__in=slugs,
                is_active=True,
            ).values_list("slug", flat=True)
        )
        steps = [s for s in candidate_steps if s["scenario_slug"] in existing][:LEARNING_PATH_LIMIT]
        if not steps:
            skipped += 1
            continue

        if tech.learning_path != steps:
            tech.learning_path = steps
            tech.save(update_fields=["learning_path"])
            updated += 1

    msg = f"Technology learning paths: {updated} updated, {skipped} skipped (no scenarios)."
    if stdout and style:
        stdout.write(style.SUCCESS(msg))
    elif stdout:
        stdout.write(msg)
    return {"updated": updated, "skipped": skipped}


def sync_catalog(stdout=None, style=None) -> dict:
    """Run full technology ↔ tutorial catalog sync."""
    tutorials = sync_tutorial_scenario_links(stdout, style)
    paths = sync_technology_learning_paths(stdout, style)
    return {"tutorials": tutorials, "learning_paths": paths}
