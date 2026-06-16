"""Rule-based FixitLab support assistant — platform help only (not Jira ticket ops)."""

from __future__ import annotations

import re
from typing import Optional

from django.conf import settings

DEFAULT_QUICK_TOPICS = [
    {"label": "Launch a lab", "prompt": "How do I launch a lab?"},
    {"label": "Subscribe", "prompt": "How do I subscribe to a technology?"},
    {"label": "Interviews", "prompt": "How do mock interviews work?"},
    {"label": "Contact support", "prompt": "Who do I contact for help?"},
]

DEFAULT_WELCOME = (
    "Hi! I'm the FixitLab Assistant — your platform guide for subscriptions, launching labs, "
    "interviews, certificates, and who to contact.\n\n"
    "Lab ticket questions (customer impact, @team mentions, patching, disks, NICs) belong in "
    "the Jira panel inside your lab session — not here."
)

JIRA_LAB_REDIRECT = (
    "That belongs in your lab's Jira ticket — use the Jira panel in the lab runner, not this assistant.\n\n"
    "Inside the ticket you can:\n"
    "• Ask the customer bot about impact, timeline, symptoms, or logs\n"
    "• Mention @backup team, @database team, @application team for patching prep\n"
    "• Mention @storage team to provision disks or @network team for NIC/IP\n\n"
    "Team bots reply after ~30 seconds and update the simulated server. "
    "Then continue in the terminal."
)

# Topics handled only by Jira bots inside an active lab session.
_JIRA_LAB_KEYWORDS = (
    "jira", "ticket", "incident", "change window", "@backup", "@database", "@application",
    "@storage", "@network", "customer bot", "team bot", "backup team", "database team",
    "application team", "storage team", "network team", "patching workflow", "precheck",
    "postcheck", "mount filesystem", "mount -a", "fdisk", "pvcreate", "lvextend",
    "secondary ip", "nic ", "proceeding with patch", "stop database", "stop application",
    "start database", "start application", "take backup", "rescan", "scsi",
)


def _is_jira_lab_question(text: str, page_path: str = "") -> bool:
    low = text.lower()
    if any(kw in low for kw in _JIRA_LAB_KEYWORDS):
        return True
    if "/lab/" in (page_path or "") and any(
        w in low for w in ("patch", "reboot", "disk", "lvm", "network", "team", "ticket")
    ):
        return True
    return False


def _support_email() -> str:
    try:
        from apps.adminpanel.platform_config import get_settings_row

        row = get_settings_row()
        return row.support_email or getattr(settings, "SUPPORT_EMAIL", "support@fixitlab.com")
    except Exception:
        return getattr(settings, "SUPPORT_EMAIL", "support@fixitlab.com")


def _payment_email() -> str:
    try:
        from apps.adminpanel.platform_config import get_settings_row

        row = get_settings_row()
        return row.payment_email or getattr(settings, "PAYMENT_EMAIL", "")
    except Exception:
        return getattr(settings, "PAYMENT_EMAIL", "")


def support_bot_config() -> dict:
    from apps.adminpanel.platform_config import get_settings_row

    row = get_settings_row()
    topics = row.support_bot_quick_topics if row.support_bot_quick_topics else DEFAULT_QUICK_TOPICS
    custom_faq = row.support_bot_custom_faq or []
    return {
        "enabled": bool(row.support_bot_enabled),
        "name": row.support_bot_name or "FixitLab Assistant",
        "welcome_message": row.support_bot_welcome_message or DEFAULT_WELCOME,
        "quick_topics": topics,
        "typing_delay_ms": int(row.support_bot_typing_delay_ms or 1200),
        "support_email": _support_email(),
        "custom_faq_count": len(custom_faq),
    }


def _match_custom_faq(text: str, custom_faq: list) -> Optional[str]:
    low = text.lower()
    for entry in custom_faq:
        keywords = entry.get("keywords") or []
        if any(kw.lower() in low for kw in keywords if kw):
            return entry.get("answer", "").strip()
    return None


def _suggestions_for_context(text: str) -> list[str]:
    low = text.lower()
    if any(w in low for w in ("lab", "terminal", "scenario", "validate")):
        return [
            "How do I launch a lab?",
            "What if validation fails?",
            "Who do I contact for help?",
        ]
    return [
        "How do I subscribe to a technology?",
        "How do mock interviews work?",
        "Who do I contact for help?",
    ]


def generate_support_reply(
    user_text: str,
    *,
    is_authenticated: bool = False,
    page_path: str = "",
) -> dict:
    """Return assistant reply with optional follow-up suggestions."""
    from apps.adminpanel.platform_config import get_settings_row

    row = get_settings_row()
    custom_faq = row.support_bot_custom_faq or []
    text = (user_text or "").strip()
    low = text.lower()
    support = _support_email()
    payment = _payment_email()
    delay = int(row.support_bot_typing_delay_ms or 1200)

    if _is_jira_lab_question(text, page_path):
        return {
            "reply": JIRA_LAB_REDIRECT,
            "suggestions": [
                "How do I launch a lab?",
                "Who do I contact for help?",
            ],
            "typing_delay_ms": delay,
        }

    custom = _match_custom_faq(text, custom_faq)
    if custom:
        return {
            "reply": custom,
            "suggestions": _suggestions_for_context(text),
            "typing_delay_ms": delay,
        }

    if not text or any(w in low for w in ("hello", "hi", "hey", "help", "start")):
        welcome = row.support_bot_welcome_message or DEFAULT_WELCOME
        if not is_authenticated:
            welcome += "\n\nSign in or create a free account from the top menu to launch labs and track progress."
        return {
            "reply": welcome,
            "suggestions": [t["prompt"] for t in (row.support_bot_quick_topics or DEFAULT_QUICK_TOPICS)[:4]],
            "typing_delay_ms": delay,
        }

    if any(w in low for w in ("launch", "start lab", "open lab", "begin lab", "how to lab")):
        reply = (
            "Launching a lab\n"
            "1. Go to Technologies in the sidebar and pick a stack (e.g. Linux).\n"
            "2. Open a scenario and click Start Lab (subscription required for most scenarios).\n"
            "3. Use the embedded terminal — commands run on a simulated server.\n"
            "4. Complete objectives, run Validate, then Stop Lab when finished.\n\n"
            "During the lab, open the Jira panel for ticket and team coordination."
        )
    elif any(w in low for w in ("subscribe", "subscription", "pricing", "pay", "purchase", "renew")):
        pay_line = f"\nBilling questions: {payment}" if payment else ""
        reply = (
            "Subscriptions\n"
            "• Subscriptions are per technology — pay only for stacks you need.\n"
            "• Open Pricing or Subscriptions to view plans and renew.\n"
            "• After payment, scenarios for that technology unlock immediately.\n"
            f"• Support: {support}{pay_line}"
        )
    elif any(w in low for w in ("interview", "mock interview", "voice", "camera", "mic")):
        reply = (
            "AI Interview Studio\n"
            "• Open Interviews from the sidebar (or /mock-interviews when logged out).\n"
            "• Upload a resume, pick rounds, and allow microphone (and camera when required).\n"
            "• Plans are separate from technology lab subscriptions — see Pricing.\n"
            "• Certificates verify at Verify Certificate (FIXIT-INT-… IDs)."
        )
    elif any(w in low for w in ("contact", "email", "support", "who to", "reach", "issue", "bug", "problem")):
        pay_line = f"\n• Payments / refunds: {payment}" if payment else ""
        reply = (
            "Who to contact\n"
            f"• General support & labs: {support}\n"
            f"{pay_line}\n"
            "• In-app: Community forum, FAQ page, or this assistant (platform questions only).\n"
            "• Account: Profile → notification preferences or delete account.\n\n"
            "For active lab incidents, use the Jira panel in your lab session."
        )
    elif any(w in low for w in ("validation", "validate", "pass", "check solution", "verify lab")):
        reply = (
            "Validation\n"
            "• Click Validate in the lab UI when objectives are complete.\n"
            "• The checker runs terminal state plus any scenario requirements.\n"
            "• Use hints if stuck — limited hints per scenario.\n"
            "• Ticket/team steps must be done in the Jira panel before validation can pass."
        )
    elif any(w in low for w in ("hint", "stuck", "clue")):
        reply = (
            "Hints\n"
            "• Each scenario has a limited number of hints.\n"
            "• Open the hints panel in the lab runner — progressive hints avoid spoiling the full answer.\n"
            "• After time expires you can view the solution explanation."
        )
    elif any(w in low for w in ("certificate", "achievement", "badge")):
        reply = (
            "Certificates & achievements\n"
            "• Complete scenarios to earn achievements and technology progress.\n"
            "• Interview campaigns issue FIXIT-INT certificates when all rounds pass.\n"
            "• Verify any certificate at Verify Certificate in the menu."
        )
    elif any(w in low for w in ("disable", "turn off", "hide bot", "stop bot")):
        reply = (
            "Hide this assistant\n"
            "• Click X on the chat panel or the floating Help button to minimize.\n"
            "• To disable permanently: Profile → FixitLab Assistant toggle.\n"
            "• Admins can disable the bot platform-wide in Admin → Platform Settings."
        )
    elif any(w in low for w in ("technology", "technologies", "browse", "catalog")):
        reply = (
            "Technologies\n"
            "• Sidebar → Technologies lists all stacks (Linux, networking, etc.).\n"
            "• Each technology page shows scenarios by difficulty.\n"
            "• Subscribe to unlock full scenario access for that stack."
        )
    elif any(w in low for w in ("team", "organization", "invite", "org")):
        reply = (
            "My Team\n"
            "• Sidebar → My Team for organization invites and member analytics.\n"
            "• Managers can track learner progress; learners use their own accounts."
        )
    elif page_path and "/lab/" in page_path:
        reply = (
            "You're in a lab session. Use the terminal for commands and Validate when done. "
            "For ticket updates, customer questions, or @team coordination, use the Jira panel — not this assistant."
        )
    else:
        reply = (
            "I'm not sure about that. I help with platform usage:\n"
            "• Launching labs • Subscriptions • Interviews • Certificates • Contacts\n\n"
            f"For lab ticket/team questions, use the Jira panel in your lab. "
            f"Or email {support} for human support."
        )

    reply = re.sub(r"\*\*([^*]+)\*\*", r"\1", reply)

    return {
        "reply": reply,
        "suggestions": _suggestions_for_context(text),
        "typing_delay_ms": delay,
    }
