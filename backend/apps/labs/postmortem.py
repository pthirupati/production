"""Auto-generated blameless postmortem + public replay artifact.

FOUNDATION feature (pairs with ``incident_director.py``). Assembles a blameless
postmortem from an :class:`~apps.labs.models.IncidentRun` (+ its
:class:`~apps.labs.models.LabSession` and command history / SessionRecording)
entirely deterministically — NO LLM, NO paid API, no ``random``/``time`` import
nondeterminism. Given the same inputs it always produces the same artifact,
which is what makes the public replay link a stable portfolio piece.

The artifact contains:
  * a timeline of key actions with timestamps (from CommandHistory),
  * the *known* root cause (owned by the Director, not inferred),
  * detection -> mitigation -> resolution durations (MTTR),
  * what worked, and
  * follow-up action items.

Output is a structured ``dict`` (JSON-safe) plus a Markdown rendering. Both are
persisted on the :class:`~apps.labs.models.Postmortem` model, which gates public
read via an unguessable ``public_token``.
"""

from __future__ import annotations

from typing import Any

# Commands that materially change system state — highlighted as timeline pivots.
_MITIGATION_HINTS = (
    "systemctl", "restart", "start ", "reload", "rollback", "revert",
    "kubectl", "helm", "dnf", "yum", "mount", "truncate", "kill",
    "firewall-cmd", "chcon", "setenforce", "lvextend", "vgextend",
)


def _fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "n/a"
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _classify(command: str) -> str:
    low = (command or "").lower()
    if any(h in low for h in _MITIGATION_HINTS):
        return "action"
    if low.startswith(("ls", "cat", "journalctl", "systemctl status", "df", "top",
                        "ps", "dig", "nslookup", "grep", "tail", "less", "kubectl get",
                        "kubectl describe", "kubectl logs")):
        return "investigation"
    return "other"


def _build_timeline(session, limit: int = 200) -> list[dict]:
    """Timeline entries from CommandHistory (key actions, timestamped)."""
    if session is None:
        return []
    from .models import CommandHistory

    events = (
        CommandHistory.objects.filter(session=session)
        .order_by("timestamp")[:limit]
    )
    start = getattr(session, "started_at", None)
    timeline: list[dict] = []
    for ev in events:
        offset = None
        if start and ev.timestamp:
            offset = (ev.timestamp - start).total_seconds()
        timeline.append({
            "at": _iso(ev.timestamp),
            "offset_seconds": None if offset is None else int(offset),
            "command": ev.command,
            "exit_code": ev.exit_code,
            "kind": _classify(ev.command),
        })
    return timeline


def _replay_reference(session) -> dict | None:
    """Reuse the existing SessionRecording (asciinema-style) as a replay ref."""
    if session is None:
        return None
    rec = getattr(session, "recording", None)
    if rec is None:
        # OneToOne may raise on access; guard via the related manager instead.
        from .models import SessionRecording

        rec = SessionRecording.objects.filter(session=session).first()
    if rec is None:
        return None
    return {
        "available": True,
        "total_duration": rec.total_duration,
        "event_count": len(rec.events or []),
        "created_at": _iso(rec.created_at),
    }


def _mttr(run) -> dict:
    """Detection -> mitigation -> resolution durations."""
    started = getattr(run, "started_at", None)
    detected = getattr(run, "detected_at", None) or started
    mitigated = getattr(run, "mitigated_at", None)
    resolved = getattr(run, "resolved_at", None)

    def _delta(a, b):
        if a and b:
            return (b - a).total_seconds()
        return None

    time_to_detect = _delta(started, detected)
    time_to_mitigate = _delta(detected, mitigated)
    time_to_resolve = _delta(detected, resolved)
    return {
        "started_at": _iso(started),
        "detected_at": _iso(detected),
        "mitigated_at": _iso(mitigated),
        "resolved_at": _iso(resolved),
        "time_to_detect_seconds": None if time_to_detect is None else int(time_to_detect),
        "time_to_mitigate_seconds": None if time_to_mitigate is None else int(time_to_mitigate),
        "mttr_seconds": None if time_to_resolve is None else int(time_to_resolve),
        "mttr_human": _fmt_duration(time_to_resolve),
    }


def build_postmortem_data(run, session=None) -> dict[str, Any]:
    """Assemble the structured (JSON-safe) postmortem dict.

    ``run`` is an IncidentRun; ``session`` defaults to ``run.lab_session``.
    Deterministic given the same DB rows.
    """
    if session is None:
        session = getattr(run, "lab_session", None)

    plan = getattr(run, "director_plan", None) or {}
    title = plan.get("title") or getattr(run, "template_key", "") or "Incident"
    timeline = _build_timeline(session)
    actions = [e for e in timeline if e["kind"] == "action"]

    data = {
        "schema": "fixitlab.postmortem.v1",
        "title": f"Blameless postmortem: {title}",
        "blameless_statement": (
            "This postmortem is blameless. It focuses on systems and process, not "
            "individuals — the goal is to learn and prevent recurrence."
        ),
        "incident": {
            "template_key": getattr(run, "template_key", ""),
            "difficulty": getattr(run, "difficulty", "") or plan.get("difficulty", ""),
            "summary": plan.get("summary", ""),
            "detection_signal": getattr(run, "detection_signal", "") or plan.get("detection_signal", ""),
        },
        "root_cause": getattr(run, "root_cause", "") or plan.get("root_cause", ""),
        "escalations": getattr(run, "escalations", None) or plan.get("escalations", []) or [],
        "timeline": timeline,
        "key_actions": actions,
        "mttr": _mttr(run),
        "what_worked": plan.get("what_worked", ""),
        "action_items": list(plan.get("action_items", [])),
        "replay": _replay_reference(session),
    }
    return data


def render_markdown(data: dict[str, Any]) -> str:
    """Deterministic Markdown rendering of the structured postmortem."""
    lines: list[str] = []
    lines.append(f"# {data.get('title', 'Postmortem')}")
    lines.append("")
    lines.append(f"> {data.get('blameless_statement', '')}")
    lines.append("")

    inc = data.get("incident", {})
    lines.append("## Incident")
    lines.append("")
    lines.append(f"- **Difficulty:** {inc.get('difficulty') or 'n/a'}")
    if inc.get("summary"):
        lines.append(f"- **Summary:** {inc['summary']}")
    if inc.get("detection_signal"):
        lines.append(f"- **Detection signal:** {inc['detection_signal']}")
    lines.append("")

    lines.append("## Root cause")
    lines.append("")
    lines.append(data.get("root_cause") or "_Root cause not recorded._")
    lines.append("")

    mttr = data.get("mttr", {})
    lines.append("## Impact & MTTR")
    lines.append("")
    lines.append(f"- **Time to detect:** {_fmt_duration(mttr.get('time_to_detect_seconds'))}")
    lines.append(f"- **Time to mitigate:** {_fmt_duration(mttr.get('time_to_mitigate_seconds'))}")
    lines.append(f"- **MTTR (detect -> resolve):** {mttr.get('mttr_human', 'n/a')}")
    lines.append("")

    escalations = data.get("escalations") or []
    if escalations:
        lines.append("## Escalations")
        lines.append("")
        for esc in escalations:
            lines.append(f"- Step {esc.get('step')}: {esc.get('note', esc.get('kind', ''))}")
        lines.append("")

    timeline = data.get("timeline") or []
    lines.append("## Timeline")
    lines.append("")
    if timeline:
        for ev in timeline:
            offset = ev.get("offset_seconds")
            stamp = _fmt_duration(offset) if offset is not None else (ev.get("at") or "?")
            marker = "**[action]** " if ev.get("kind") == "action" else ""
            lines.append(f"- `+{stamp}` {marker}`{ev.get('command', '')}`")
    else:
        lines.append("_No recorded commands for this run._")
    lines.append("")

    if data.get("what_worked"):
        lines.append("## What worked")
        lines.append("")
        lines.append(data["what_worked"])
        lines.append("")

    action_items = data.get("action_items") or []
    lines.append("## Follow-up action items")
    lines.append("")
    if action_items:
        for item in action_items:
            lines.append(f"- [ ] {item}")
    else:
        lines.append("_No action items recorded._")
    lines.append("")

    replay = data.get("replay")
    if replay and replay.get("available"):
        lines.append("## Replay")
        lines.append("")
        lines.append(
            f"A terminal replay is available "
            f"({replay.get('event_count', 0)} events, "
            f"{_fmt_duration(replay.get('total_duration'))})."
        )
        lines.append("")

    return "\n".join(lines)


def generate_postmortem(run, session=None, make_public: bool = True):
    """Build + persist a :class:`~apps.labs.models.Postmortem` for an IncidentRun.

    Idempotent per IncidentRun (OneToOne): regenerating refreshes the data and
    Markdown but keeps the same ``public_token`` so an already-shared link stays
    valid. Returns the Postmortem instance.
    """
    from .models import Postmortem

    if session is None:
        session = getattr(run, "lab_session", None)

    data = build_postmortem_data(run, session=session)
    markdown = render_markdown(data)

    pm, _created = Postmortem.objects.get_or_create(
        incident_run=run,
        defaults={
            "lab_session": session,
            "title": data.get("title", ""),
            "data": data,
            "markdown": markdown,
            "is_public": make_public,
        },
    )
    if not _created:
        pm.lab_session = session
        pm.title = data.get("title", "")
        pm.data = data
        pm.markdown = markdown
        pm.save(update_fields=["lab_session", "title", "data", "markdown"])
    return pm
