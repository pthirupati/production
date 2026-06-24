"""Resume / profile personalization for generated questions — free, no API."""

from __future__ import annotations

import random


def profile_hooks(snapshot: dict) -> dict[str, str]:
    snap = snapshot or {}
    return {
        "company": (snap.get("current_company") or "").strip(),
        "role": (snap.get("target_role") or snap.get("experience_level") or "this role").strip(),
        "tech": (snap.get("primary_technology_name") or "").strip(),
        "level": (snap.get("experience_level") or "mid").strip(),
    }


def personalize_question(text: str, snapshot: dict, rng: random.Random | None = None) -> str:
    """Light personalization — anchor questions to the candidate's profile."""
    if not text:
        return text
    rng = rng or random.Random()
    hooks = profile_hooks(snapshot)
    company = hooks["company"]
    role = hooks["role"]
    tech = hooks["tech"]

    if company and company.lower() not in ("your current company", "your org", "") and rng.random() < 0.22:
        if "?" in text:
            return text.replace("?", f" — at {company}?", 1)
        return f"{text} (thinking about your work at {company})"

    if tech and tech.lower() not in text.lower() and rng.random() < 0.18:
        return f"In your {tech} context: {text}"

    if role and role.lower() not in ("this role", "mid role", "") and rng.random() < 0.12:
        if text.startswith("Tell me") or text.startswith("Walk me"):
            return f"For a {role} track — {text[0].lower()}{text[1:]}"

    return text


def personalized_study_links(snapshot: dict, weak_topics: list[str]) -> list[dict]:
    """Study plan rows tailored to resume tech + weak round topics."""
    snap = snapshot or {}
    slug = (snap.get("primary_technology_slug") or snap.get("primary_technology") or "linux")
    if hasattr(slug, "slug"):
        slug = slug.slug
    slug = str(slug).lower().replace(" ", "-") if slug else "linux"

    plan: list[dict] = [
        {"title": "Practice scenarios", "url": f"/technologies/{slug}"},
        {"title": "Simulation labs", "url": "/scenarios?mode=simulation"},
        {"title": "Review round transcript", "url": ""},
    ]
    topic_labels = {
        "kubernetes": "Kubernetes drills",
        "docker": "Container labs",
        "nginx": "nginx troubleshooting",
        "linux": "Linux fundamentals",
        "aws": "AWS scenarios",
        "terraform": "Terraform labs",
        "monitoring": "Observability practice",
        "security": "Security scenarios",
        "database": "Database ops labs",
        "system_design": "Architecture practice",
    }
    for topic in weak_topics[:3]:
        label = topic_labels.get(topic, topic.replace("_", " ").title())
        plan.insert(1, {
            "title": f"Strengthen: {label}",
            "url": f"/technologies/{slug}?topic={topic}",
        })
    plan[2]["url"] = plan[2]["url"] or "/interviews"
    return plan[:6]
