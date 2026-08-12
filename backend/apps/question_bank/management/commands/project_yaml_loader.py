"""Thin YAML loader for guided-project fixtures (Z6-14 decomposition half)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parent / "data" / "projects"


def load_project_yamls(directory: Path | str | None = None) -> list[dict]:
    """Load every ``*.yaml`` / ``*.yml`` under data/projects/ (sorted by name)."""
    root = Path(directory) if directory else DATA_DIR
    if not root.is_dir():
        return []
    projects: list[dict] = []
    for path in sorted(root.iterdir()):
        if path.suffix.lower() not in (".yaml", ".yml"):
            continue
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if isinstance(data, list):
            projects.extend(p for p in data if isinstance(p, dict) and p.get("slug"))
        elif isinstance(data, dict) and data.get("slug"):
            projects.append(data)
    return projects


def merge_extra_projects(python_projects: list[dict]) -> list[dict]:
    """YAML fixtures override same-slug entries from the Python list."""
    yamls = load_project_yamls()
    if not yamls:
        return list(python_projects or [])
    slugs = {p["slug"] for p in yamls}
    kept = [p for p in (python_projects or []) if p.get("slug") not in slugs]
    return kept + yamls
