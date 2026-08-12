"""Acceptance-criteria live checklist (audit X7c).

Until §G per-objective assertions exist, the checklist is all-or-nothing on
overall validation pass, with a keyword heuristic that can tick individual
objectives when the validator output clearly mentions them.
"""

from __future__ import annotations

import re
from typing import Any


def build_acceptance_checklist(
    objectives: Any,
    *,
    passed: bool = False,
    output: str = "",
) -> list[dict]:
    """Return ``[{id, text, done}]`` for the learner-facing live checklist."""
    if objectives is None:
        items: list[Any] = []
    elif isinstance(objectives, str):
        items = [line.strip() for line in objectives.splitlines() if line.strip()]
    elif isinstance(objectives, list):
        items = objectives
    else:
        items = [objectives]

    out_l = (output or "").lower()
    checklist = []
    for i, obj in enumerate(items):
        if isinstance(obj, dict):
            text = str(obj.get("text") or obj.get("title") or obj.get("objective") or obj)
        else:
            text = str(obj)
        text = text.strip()
        if not text:
            continue
        done = bool(passed)
        if not done and out_l:
            # Heuristic: tick when ≥2 distinctive tokens from the objective appear.
            tokens = [
                t for t in re.findall(r"[a-z0-9]{4,}", text.lower())
                if t not in {"must", "should", "ensure", "verify", "check", "that", "with", "from", "this"}
            ]
            hits = sum(1 for t in tokens[:8] if t in out_l)
            if tokens and hits >= min(2, len(tokens)):
                done = True
        checklist.append({"id": f"obj-{i}", "text": text, "done": done})
    return checklist
