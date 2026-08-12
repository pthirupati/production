"""Jira @team mention bots — delayed replies that change simulation state."""

from __future__ import annotations

import logging
import re
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

TEAM_AUTHORS = {
    "backup": "Backup Team",
    "database": "Database Team",
    "application": "Application Team",
    "storage": "Storage Team",
    "network": "Network Team",
    "security": "Security Team",
    "changemgmt": "Change Management Bot",
}

MENTION_PATTERNS = {
    "backup": re.compile(r"@?\s*backup\s+team\b|@backup\b|@\s*team\s+backup\b", re.I),
    "database": re.compile(r"@?\s*database\s+team\b|@database\b|@dba\b|@\s*team\s+database\b", re.I),
    "application": re.compile(r"@?\s*application\s+team\b|@application\b|@app\s+team\b|@\s*team\s+application\b", re.I),
    "storage": re.compile(r"@?\s*storage\s+team\b|@storage\b|@\s*team\s+storage\b", re.I),
    "network": re.compile(r"@?\s*network\s+team\b|@network\b|@\s*team\s+network\b", re.I),
    "security": re.compile(r"@?\s*security\s+team\b|@security\b|@\s*team\s+security\b", re.I),
}

_NEAR_MISS_MENTION = re.compile(
    r"@\s*[\w.-]+|"
    r"\b(storage|network|backup|database|application|security|dba)\s+team\b|"
    r"\bteam\s+(storage|network|backup|database|application|security)\b",
    re.I,
)


def looks_like_failed_team_mention(text: str) -> bool:
    """True when the learner tried to ping a team but parse_team_mentions missed it."""
    if not text or parse_team_mentions(text):
        return False
    return bool(_NEAR_MISS_MENTION.search(text))


def build_mention_coach_reply() -> tuple[str, str]:
    return (
        TEAM_AUTHORS["changemgmt"],
        "I saw an @mention that didn't match a known ops team. Try one of these exact forms "
        "(they unlock the change window):\n\n"
        "- `@storage team` — attach / expand disk\n"
        "- `@network team` — NIC / VLAN / IP\n"
        "- `@backup team` — backup before patching\n"
        "- `@database team` / `@application team` — stop or start services\n"
        "- `@security team` — firewall / access approval\n\n"
        "Example: `@storage team please add disk for LVM`",
    )


def team_reply_delay_seconds() -> int:
    return int(getattr(settings, "JIRA_TEAM_REPLY_DELAY_SECONDS", 30))


def parse_team_mentions(text: str) -> list[str]:
    if not text:
        return []
    found = []
    for key, pattern in MENTION_PATTERNS.items():
        if pattern.search(text):
            found.append(key)
    return found


def _is_stop_request(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in ("stop", "shutdown", "shut down", "down", "quiesce", "freeze"))


def _is_start_request(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in ("start", "bring up", "bringup", "online", "restore", "restart"))


def _is_backup_request(text: str) -> bool:
    low = text.lower()
    return "backup" in low and any(
        w in low for w in ("take", "create", "full", "snapshot", "please", "before", "patch")
    )


def _is_disk_request(text: str) -> bool:
    low = text.lower()
    return any(
        w in low
        for w in (
            "add disk", "attach disk", "attach new disk", "provision disk",
            "new disk", "allocate disk", "attach", "provision",
        )
    ) and "disk" in low


def _is_nic_request(text: str) -> bool:
    low = text.lower()
    return any(
        w in low
        for w in (
            "add nic", "add ip", "secondary ip", "network interface", "vlan",
            "attach nic", "configure eth", "eth0", "eth1", "nic", "ip address",
            "firewall", "routing",
        )
    )


def _is_security_request(text: str) -> bool:
    low = text.lower()
    return any(
        w in low
        for w in (
            "approve", "approval", "firewall", "access", "sign-off", "sign off",
            "change window", "allow", "permit",
        )
    )


def resolve_team_actions(text: str, teams: list[str], scenario_slug: str = "") -> list[tuple[str, str]]:
    """Return list of (team_key, action_id) to execute when bot replies."""
    slug = (scenario_slug or "").lower()
    actions: list[tuple[str, str]] = []
    low = text.lower()

    if "backup" in teams and (_is_backup_request(text) or _is_stop_request(text) or "patch" in low):
        actions.append(("backup", "backup_taken"))
    elif "backup" in teams and ("please" in low or "team" in low):
        # Bare "@backup team please …" still completes the backup hand-off.
        actions.append(("backup", "backup_taken"))

    if "database" in teams:
        if _is_start_request(text):
            actions.append(("database", "database_started"))
        elif _is_stop_request(text) or "patch" in low or "maintenance" in low or "please" in low:
            actions.append(("database", "database_stopped"))

    if "application" in teams:
        if _is_start_request(text):
            actions.append(("application", "application_started"))
        elif _is_stop_request(text) or "patch" in low or "please" in low:
            actions.append(("application", "application_stopped"))

    if "storage" in teams and (_is_disk_request(text) or "disk" in low or "lvm" in slug or "please" in low):
        actions.append(("storage", "storage_disk_added"))

    if "network" in teams and (
        _is_nic_request(text) or "network" in slug or "nic" in low or "eth" in low or "please" in low
    ):
        actions.append(("network", "network_nic_added"))

    if "security" in teams and (_is_security_request(text) or "please" in low or "firewall" in slug):
        actions.append(("security", "security_approved"))

    return actions


def build_team_reply(
    teams: list[str],
    actions: list[tuple[str, str]],
    ticket,
    user_text: str,
) -> tuple[str, str]:
    """Build consolidated bot reply. Returns (author, message)."""
    scenario = ticket.scenario
    slug = (scenario.slug or "").lower()
    lines: list[str] = []

    action_ids = {a[1] for a in actions}

    if "backup_taken" in action_ids:
        lines.append("✓ Full backup completed and verified on backup server.")
    if "database_stopped" in action_ids:
        lines.append("✓ Database stopped — all connections drained. Safe to patch.")
    if "application_stopped" in action_ids:
        lines.append("✓ Application stopped — load balancer health checks disabled.")
    if "database_started" in action_ids:
        if "mount" in user_text.lower() and "fix" in user_text.lower():
            lines.append("✓ Acknowledged mount fix. Starting database now…")
        else:
            lines.append("✓ Database started and accepting connections.")
    if "application_started" in action_ids:
        lines.append("✓ Application started — health checks passing.")
    if "storage_disk_added" in action_ids:
        dev = "/dev/sdb"
        if hasattr(ticket, "last_session") and ticket.last_session_id:
            from apps.labs.provisioner.simulation.ops_state import get_simulation_engine_for_session
            eng = get_simulation_engine_for_session(str(ticket.last_session_id))
            if eng and eng.shell.state.pending_storage_device:
                dev = eng.shell.state.pending_storage_device
        lines.append(
            f"✓ New disk provisioned: **{dev}** (50 GiB).\n"
            f"Run `fdisk -l {dev}` or `lsblk` on the server to confirm. "
            f"If not visible, run `echo 1 > /sys/class/scsi_host/host0/scan` or request rescan."
        )
    if "network_nic_added" in action_ids:
        ip = "10.0.0.20/24"
        lines.append(
            f"✓ Secondary NIC/IP configured: **{ip}** on eth0.\n"
            f"Verify with `ip addr show dev eth0` on the server."
        )
    if "security_approved" in action_ids:
        lines.append(
            "✓ Security review complete — firewall / access change **approved** for this change window.\n"
            "You may proceed with the documented remediation."
        )

    if not lines:
        if "patch" in slug:
            return (
                TEAM_AUTHORS["changemgmt"],
                "Please mention @backup team, @database team, and @application team "
                "to stop services and take backup before patching.\n\n"
                "Example: `@database team @application team @backup team — please stop DB/app and take backup for patching.`",
            )
        if "lvm" in slug:
            return (
                TEAM_AUTHORS["storage"],
                "Request disk with: `@storage team please add a 50G disk for LVM extension.`",
            )
        return (
            TEAM_AUTHORS["changemgmt"],
            "Mention a team: @backup team, @database team, @application team, "
            "@storage team, @network team, or @security team.",
        )

    if len(teams) > 1 and any(a[1].endswith("_stopped") or a[1] == "backup_taken" for a in actions):
        header = "Change window ready — all requested actions completed:\n\n"
        return TEAM_AUTHORS["changemgmt"], header + "\n".join(lines) + "\n\nYou may proceed with prechecks and patching."

    if any(a[1].endswith("_started") for a in actions):
        return TEAM_AUTHORS["changemgmt"], "Services restored:\n\n" + "\n".join(lines)

    author = TEAM_AUTHORS.get(teams[0], TEAM_AUTHORS["changemgmt"])
    return author, "\n".join(lines)


def build_mount_failure_reply(ticket) -> tuple[str, str]:
    return (
        TEAM_AUTHORS["application"],
        "⚠ Cannot start application — **mount filesystem issue** detected after reboot.\n\n"
        "Please check `/etc/fstab` and run `mount -a` on the server terminal. "
        "Reply here when the mount is fixed and we will start database and application.",
    )


def is_help_request(text: str) -> bool:
    low = (text or "").lower()
    return any(
        w in low
        for w in (
            "need help", "need a hint", "stuck", "hint please", "any hint",
            "how do i", "what should i", "next step", "guide me", "coach me",
            "help me", "not sure", "where do i start",
        )
    )


def build_coach_reply(ticket) -> tuple[str, str]:
    """Scenario-aware coaching from the ticket body / scenario objectives."""
    scenario = getattr(ticket, "scenario", None)
    objectives = []
    if scenario is not None:
        try:
            from apps.question_bank.scenario_copy import public_objectives
            objectives = list(public_objectives(scenario.objectives or []) or [])
        except Exception:
            objectives = list(scenario.objectives or []) if isinstance(scenario.objectives, list) else []

    desc = (getattr(ticket, "description", None) or "")[:4000]
    # Prefer acceptance-criteria section from the generated ticket body.
    criteria = []
    if "### Acceptance criteria" in desc:
        chunk = desc.split("### Acceptance criteria", 1)[1]
        chunk = chunk.split("###", 1)[0]
        for line in chunk.splitlines():
            line = line.strip()
            if line.startswith("- "):
                criteria.append(line[2:].strip())
    if not criteria and objectives:
        criteria = [str(o) for o in objectives[:6]]

    tools = ""
    if "### Lab tools for this scenario" in desc:
        tools = desc.split("### Lab tools for this scenario", 1)[1].split("###", 1)[0].strip()

    lines = [
        "I'm the Change Management coach on this incident. Here's how to unblock yourself "
        "without spoiling the root cause:",
        "",
        "**1. Re-read the ticket** — Summary, Impact, and Acceptance criteria are your "
        "definition of done.",
    ]
    if criteria:
        lines += ["", "**Acceptance criteria to hit:**"]
        for c in criteria[:6]:
            lines.append(f"- {c}")
    lines += [
        "",
        "**2. Use the right console** — Lab terminal is the production-like server; "
        "technology GUIs (VMware / AWS / AWX / Commvault / storage / SOC / datacenter) "
        "are ops consoles onto the same infra.",
    ]
    if tools:
        lines += ["", "**Tools for this ticket:**", tools]
    lines += [
        "",
        "**3. Collaborate** — If you need a disk, NIC, backup, or firewall change, "
        "@mention `@storage team`, `@network team`, `@backup team`, or `@security team` "
        "in a comment. They will reply and unlock the change window.",
        "",
        "**4. Verify** — After the fix, confirm against acceptance criteria, add a "
        "resolution comment with root cause, then mark the lab complete.",
        "",
        "Reply with what you already tried (commands / console actions) if you want a "
        "narrower nudge.",
    ]
    return TEAM_AUTHORS["changemgmt"], "\n".join(lines)


def schedule_team_replies(ticket, user_text: str, session=None) -> dict:
    """
    Parse mentions, schedule delayed Jira replies, return metadata for API response.
    """
    teams = parse_team_mentions(user_text)
    if not teams:
        return {"scheduled": False, "teams": []}

    scenario_slug = ticket.scenario.slug if ticket.scenario_id else ""
    actions = resolve_team_actions(user_text, teams, scenario_slug)
    author, message = build_team_reply(teams, actions, ticket, user_text)

    session_id = str(session.id) if session else (
        str(ticket.last_session_id) if ticket.last_session_id else ""
    )

    delay = team_reply_delay_seconds()
    try:
        from apps.jira_integration.pending_team_replies import enqueue_pending_team_reply

        enqueue_pending_team_reply(
            issue_key=ticket.issue_key,
            session_id=session_id,
            author=author,
            message=message,
            actions=[a[1] for a in actions],
            scenario_slug=scenario_slug,
            delay_seconds=delay,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to enqueue durable pending team reply: %s", exc)

    try:
        from celery_app.tasks import deliver_jira_team_reply

        deliver_jira_team_reply.apply_async(
            kwargs={
                "issue_key": ticket.issue_key,
                "session_id": session_id,
                "author": author,
                "message": message,
                "actions": [a[1] for a in actions],
                "scenario_slug": scenario_slug,
            },
            countdown=delay,
        )
        logger.info(
            "Queued team reply issue=%s author=%s delay=%ss teams=%s",
            ticket.issue_key, author, delay, teams,
        )
    except Exception as exc:
        logger.warning("Celery unavailable for team reply, delivering immediately: %s", exc)
        try:
            from apps.jira_integration.pending_team_replies import cancel_pending_for_issue
            cancel_pending_for_issue(ticket.issue_key)
        except Exception:
            pass
        deliver_team_reply_now(
            ticket.issue_key, session_id, author, message, [a[1] for a in actions], scenario_slug
        )
        return {"scheduled": False, "teams": teams, "delivered": True}

    return {
        "scheduled": True,
        "teams": teams,
        "delay_seconds": delay,
        "pending_author": author,
    }


def deliver_team_reply_now(
    issue_key: str,
    session_id: str,
    author: str,
    message: str,
    actions: list[str],
    scenario_slug: str = "",
) -> None:
    from .models import UserScenarioJiraTicket
    from .simulated import add_comment

    ticket = UserScenarioJiraTicket.objects.filter(issue_key=issue_key).first()
    if not ticket:
        logger.warning(
            "Dropping team reply — ticket missing issue_key=%s author=%s",
            issue_key, author,
        )
        return

    engine = None
    engine_is_live = False  # True when we found the engine in *this* process's memory
    if session_id:
        from apps.labs.provisioner.simulation.ops_state import (
            apply_team_ops_action,
            get_simulation_engine_for_session,
        )

        engine = get_simulation_engine_for_session(session_id)
        if engine is None:
            # ops_state.get_simulation_engine_for_session() reads entry["engine"],
            # but register_sim_session() stores the engine under
            # entry["state"]["engine"] — so the live in-process engine is missed
            # even inside the web worker. Look it up under the real key too.
            engine = _live_engine_from_registry(session_id)
        engine_is_live = engine is not None

        # BUG C fix: the Celery worker that runs this delayed reply is a *separate
        # process* from the web/gunicorn worker that holds the in-memory
        # `_SIM_SESSIONS` engine, so the lookup above returns None there and the
        # requested team action (backup_taken / *_stopped / disk / nic …) was
        # silently dropped — teams "replied" but never acted. Fall back to the
        # DB-persisted engine snapshot so the action is applied and re-persisted;
        # the learner's next terminal command restores the mutated state.
        if engine is None:
            engine = _restore_engine_from_snapshot(session_id)

    start_actions = [a for a in actions if a.endswith("_started")]
    prep_actions = [a for a in actions if not a.endswith("_started")]

    for action in prep_actions:
        apply_team_ops_action(engine, action, scenario_slug)

    if start_actions and engine:
        state = engine.shell.state
        if (
            state.mount_issue_after_reboot
            and state.rebooted_after_patch
            and not state.mount_filesystems_fixed
        ):
            mount_author, mount_msg = build_mount_failure_reply(ticket)
            # A restored-from-snapshot engine was mutated to report the mount
            # failure path; persist that too so state stays coherent.
            if engine is not None and not engine_is_live:
                _persist_engine_snapshot(session_id, engine)
            add_comment(ticket, None, mount_msg, session=ticket.last_session, author=mount_author)
            return
        for action in start_actions:
            apply_team_ops_action(engine, action, scenario_slug)

    # If we operated on a snapshot-restored engine (Celery worker had no live
    # engine), write the mutated state back to the DB snapshot so it survives
    # into the web worker on the learner's next command. When the engine was
    # already live in-process, the web worker's normal per-command persistence
    # owns the snapshot and we must NOT clobber it here.
    if engine is not None and not engine_is_live and (prep_actions or start_actions):
        _persist_engine_snapshot(session_id, engine)

    add_comment(ticket, None, message, session=ticket.last_session, author=author)


def _live_engine_from_registry(session_id: str):
    """Return the in-process live engine for this session, or None.

    Reads the real storage location (`entry["state"]["engine"]`) that
    register_sim_session writes to. Only useful when the delivery runs in the
    same process that holds the engine (e.g. the sync fallback inside gunicorn);
    a separate Celery worker will have an empty registry and get None here.
    """
    try:
        from apps.labs.provisioner.simulation.shell import get_sim_session
    except Exception:  # pragma: no cover - defensive import guard
        return None
    entry = get_sim_session(str(session_id))
    if not entry:
        return None
    state = entry.get("state")
    if isinstance(state, dict):
        return state.get("engine")
    return None


def _restore_engine_from_snapshot(session_id: str):
    """Rebuild the simulation engine from LabSession.simulation_snapshot.

    Used by the Celery worker (a different process than the web worker that owns
    the in-memory engine registry) so team-bot actions still mutate real state.
    Returns None if there is no usable snapshot.
    """
    try:
        from apps.labs.models import LabSession
        from apps.labs.provisioner.simulation.sim_persistence import restore_engine
    except Exception as exc:  # pragma: no cover - defensive import guard
        logger.warning("Cannot import snapshot restore for team reply: %s", exc)
        return None

    snap = (
        LabSession.objects.filter(id=session_id)
        .values_list("simulation_snapshot", flat=True)
        .first()
    )
    if not snap:
        return None
    try:
        return restore_engine(snap)
    except Exception as exc:
        logger.warning("Failed to restore engine snapshot for team reply session=%s: %s", session_id, exc)
        return None


def _persist_engine_snapshot(session_id: str, engine) -> None:
    """Write a mutated (snapshot-restored) engine back to the DB snapshot."""
    try:
        from apps.labs.models import LabSession
        from apps.labs.provisioner.simulation.sim_persistence import snapshot_engine
    except Exception as exc:  # pragma: no cover - defensive import guard
        logger.warning("Cannot import snapshot save for team reply: %s", exc)
        return
    try:
        snap = snapshot_engine(engine)
        LabSession.objects.filter(id=session_id).update(simulation_snapshot=snap)
    except Exception as exc:
        logger.warning("Failed to persist engine snapshot for team reply session=%s: %s", session_id, exc)
