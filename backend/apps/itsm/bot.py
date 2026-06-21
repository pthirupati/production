"""ITSM assignment-group bot — the automated fulfiller voice on a ticket.

This is the ServiceNow analogue of the Jira team bots: when a ticket is opened,
transferred, has a sub-ticket raised, or is fulfilled, the *assigned team* posts a
realistic work note (acknowledgement / status update / resolution), exactly like a
real fulfiller working the queue. The user can also ask the assignment group a
question on the ticket and get a context-aware answer.

It is FREE / rule-based: the answer engine is the existing support intent engine
(`apps.support.service.generate_support_reply`), imported read-only. We never call
a paid API. To make the generic engine answer *as the assignment group for this
ticket*, we:

  * scope it to the ticket's lab session by synthesising the `/lab/<session_id>`
    page_path the support engine already understands (so it resolves the
    scenario/technology and tailors the steps), and
  * bias intent detection toward the ticket's team/type by seeding the question
    with the team's domain keywords when the user's wording is thin.

The note builders return plain strings; `apps.itsm.services` decides when to post
them (right after the corresponding lifecycle action) so views and tests share one
code path. Nothing here mutates the database — services owns persistence.
"""

from __future__ import annotations

import logging

from . import constants as C

logger = logging.getLogger(__name__)


# ── Fulfiller personas ─────────────────────────────────────────────────────────
# Each assignment group answers in a recognisable ServiceNow-fulfiller voice. The
# `domain` keywords are folded into the support engine's question when the user's
# own wording does not already imply a technology group, so a question asked on,
# say, a Storage ticket biases toward storage/disk answers.
TEAM_PERSONA: dict[str, dict] = {
    C.TEAM_SERVICE_DESK: {
        "name": "Service Desk",
        "domain": "",
        "greeting": "Service Desk has the ticket and is triaging it now.",
    },
    C.TEAM_STORAGE: {
        "name": "Storage Team",
        "domain": "disk lvm datastore storage filesystem volume",
        "greeting": "Storage Team has picked up the request.",
    },
    C.TEAM_BACKUP: {
        "name": "Backup Team",
        "domain": "backup restore snapshot recovery",
        "greeting": "Backup Team has the request in queue.",
    },
    C.TEAM_NETWORK: {
        "name": "Network Team",
        "domain": "network nic ip firewall port dns route connectivity",
        "greeting": "Network Team is reviewing the request.",
    },
    C.TEAM_APP: {
        "name": "App / Middleware Team",
        "domain": "service systemd application middleware process",
        "greeting": "App / Middleware Team has the ticket.",
    },
    C.TEAM_DATABASE: {
        "name": "Database Team",
        "domain": "database service connection",
        "greeting": "Database Team has the request.",
    },
    C.TEAM_SECURITY: {
        "name": "Security Team",
        "domain": "permission selinux access firewall",
        "greeting": "Security Team is assessing the request.",
    },
}


def team_author(team: str) -> str:
    """The bot's display name for a team (its ServiceNow assignment-group name)."""
    persona = TEAM_PERSONA.get(team)
    return persona["name"] if persona else C.team_label(team)


def _persona(team: str) -> dict:
    return TEAM_PERSONA.get(team) or {
        "name": C.team_label(team),
        "domain": "",
        "greeting": f"{C.team_label(team)} has the ticket.",
    }


# ── Event work notes (the fulfiller voice on lifecycle changes) ─────────────────
# These return (author, body) — services.py posts them as KIND_SYSTEM notes so they
# render as the assigned team in the activity stream, like a real fulfiller update.


def note_on_open(ticket) -> tuple[str, str]:
    """Acknowledgement posted by the assignment group when a ticket is opened."""
    persona = _persona(ticket.assignment_group)
    sla = ""
    if ticket.sla_due_at:
        sla = f" Target response is tracked against the {ticket.get_priority_display()} SLA."
    return (
        persona["name"],
        f"{persona['greeting']} We've reviewed **{ticket.number}** and will update this ticket "
        f"with progress. Add a comment below if you have more detail or a question for us.{sla}",
    )


def note_on_transfer(ticket, from_team: str) -> tuple[str, str]:
    """Acknowledgement posted by the NEW assignment group after a transfer."""
    persona = _persona(ticket.assignment_group)
    return (
        persona["name"],
        f"Ticket received from {C.team_label(from_team)}. {persona['name']} now owns "
        f"**{ticket.number}** and is picking it up. We'll post our findings as work notes here.",
    )


def note_on_subticket_raised(sub) -> tuple[str, str]:
    """Acknowledgement the assisting team posts on the new sub-ticket it receives."""
    persona = _persona(sub.assignment_group)
    return (
        persona["name"],
        f"{persona['greeting']} Request **{sub.number}** — \"{sub.short_description}\" — is in our "
        f"queue. We'll action it and resolve this request, then notify the parent ticket.",
    )


def note_on_fulfilled(sub) -> tuple[str, str]:
    """Closing summary the assisting team posts when it resolves a sub-ticket.

    The engine's own handler already posts the technical detail (e.g. the /dev path
    for a disk); this is the fulfiller's human sign-off on top of it.
    """
    persona = _persona(sub.assignment_group)
    return (
        persona["name"],
        f"Work complete on **{sub.number}**. {persona['name']} is resolving this request — "
        f"see the work notes above for what changed and any action needed on your side.",
    )


# ── Ask-the-assignment-group (comment → bot reply) ──────────────────────────────


def _scoped_page_path(ticket) -> str:
    """Synthesize the `/lab/<session_id>` path the support engine resolves context from."""
    session_id = getattr(ticket, "session_id", None)
    return f"/lab/{session_id}" if session_id else ""


def _bias_question(ticket, question: str) -> str:
    """Seed the question with the team's domain keywords for thin/ambiguous wording.

    The support engine scores intents by keyword/regex/technology-group affinity. If
    the user's question already names a technology we leave it alone; otherwise we
    append the assignment group's domain terms so the answer comes back in the
    ticket's lane (e.g. a bare "what should I check?" on a Storage ticket leans
    toward storage guidance) rather than a generic fallback.
    """
    from apps.support.service import _detect_group, resolve_lab_context

    if _detect_group(question):
        return question  # user already implied a technology group
    ctx = resolve_lab_context(_scoped_page_path(ticket))
    if ctx.get("group"):
        return question  # the lab session resolves a group on its own
    domain = _persona(ticket.assignment_group).get("domain", "")
    return f"{question} {domain}".strip() if domain else question


def answer_question(ticket, question: str) -> dict:
    """Produce the assignment group's reply to a user comment on the ticket.

    Returns {"author", "reply", "intent"}. Reuses the free support intent engine,
    scoped to this ticket's session/scenario and biased toward its team's domain.
    Never raises — on any failure it returns a safe fulfiller acknowledgement.
    """
    persona = _persona(ticket.assignment_group)
    author = persona["name"]
    text = (question or "").strip()
    if not text:
        return {
            "author": author,
            "reply": f"{author} here — add a question or detail and we'll help on this ticket.",
            "intent": "empty",
        }
    try:
        from apps.support.service import generate_support_reply

        result = generate_support_reply(
            _bias_question(ticket, text),
            is_authenticated=True,
            page_path=_scoped_page_path(ticket),
        )
        reply = (result.get("reply") or "").strip()
        intent = result.get("intent") or "fallback"
    except Exception as exc:  # pragma: no cover - the engine is in-process & safe
        logger.warning("ITSM ask-bot engine failed for %s: %s", ticket.number, exc)
        reply = ""
        intent = "error"

    if not reply:
        reply = (
            "We've noted your question on this ticket and are looking into it. "
            "Share the exact error or command output and we'll guide the next step."
        )
    # Front it with the fulfiller voice so it reads like the assignment group, not a
    # generic assistant, and remind the user of the ticket they're on.
    prefix = f"{author} on **{ticket.number}**:\n\n"
    return {"author": author, "reply": prefix + reply, "intent": intent}
