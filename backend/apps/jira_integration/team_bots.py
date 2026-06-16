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
    "backup": re.compile(r"@?\s*backup\s*team|@backup\b", re.I),
    "database": re.compile(r"@?\s*database\s*team|@database\b|@dba\b", re.I),
    "application": re.compile(r"@?\s*application\s*team|@application\b|@app\s*team", re.I),
    "storage": re.compile(r"@?\s*storage\s*team|@storage\b", re.I),
    "network": re.compile(r"@?\s*network\s*team|@network\b", re.I),
    "security": re.compile(r"@?\s*security\s*team|@security\b", re.I),
}


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
    return "backup" in low and any(w in low for w in ("take", "create", "full", "snapshot", "please"))


def _is_disk_request(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in ("add disk", "attach disk", "provision disk", "new disk", "allocate disk"))


def _is_nic_request(text: str) -> bool:
    low = text.lower()
    return any(w in low for w in ("add nic", "add ip", "secondary ip", "network interface", "vlan", "attach nic"))


def resolve_team_actions(text: str, teams: list[str], scenario_slug: str = "") -> list[tuple[str, str]]:
    """Return list of (team_key, action_id) to execute when bot replies."""
    slug = (scenario_slug or "").lower()
    actions: list[tuple[str, str]] = []
    low = text.lower()

    if "backup" in teams and (_is_backup_request(text) or _is_stop_request(text) or "patch" in low):
        actions.append(("backup", "backup_taken"))

    if "database" in teams:
        if _is_start_request(text):
            actions.append(("database", "database_started"))
        elif _is_stop_request(text) or "patch" in low:
            actions.append(("database", "database_stopped"))

    if "application" in teams:
        if _is_start_request(text):
            actions.append(("application", "application_started"))
        elif _is_stop_request(text) or "patch" in low:
            actions.append(("application", "application_stopped"))

    if "storage" in teams and (_is_disk_request(text) or "disk" in low or "lvm" in slug):
        actions.append(("storage", "storage_disk_added"))

    if "network" in teams and (_is_nic_request(text) or "network" in slug or "nic" in low):
        actions.append(("network", "network_nic_added"))

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
            "Mention a team: @backup team, @database team, @application team, @storage team, or @network team.",
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
    except Exception as exc:
        logger.warning("Celery unavailable for team reply, delivering immediately: %s", exc)
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
        return

    engine = None
    if session_id:
        from apps.labs.provisioner.simulation.ops_state import (
            apply_team_ops_action,
            get_simulation_engine_for_session,
        )
        engine = get_simulation_engine_for_session(session_id)

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
            add_comment(ticket, None, mount_msg, session=ticket.last_session, author=mount_author)
            return
        for action in start_actions:
            apply_team_ops_action(engine, action, scenario_slug)

    add_comment(ticket, None, message, session=ticket.last_session, author=author)
