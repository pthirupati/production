"""Rule-based FixitLab support assistant — answers common how-to questions."""

from __future__ import annotations

import re
from typing import Optional

from django.conf import settings

DEFAULT_QUICK_TOPICS = [
    {"label": "Launch a lab", "prompt": "How do I launch a lab?"},
    {"label": "Subscribe", "prompt": "How do I subscribe to a technology?"},
    {"label": "Jira in labs", "prompt": "How does Jira work during simulation labs?"},
    {"label": "Patching workflow", "prompt": "How do I coordinate patching with Jira teams?"},
    {"label": "Contact support", "prompt": "Who do I contact for help?"},
]

DEFAULT_WELCOME = (
    "Hi! I'm the FixitLab Assistant. Ask me how to use the platform — launching labs, "
    "subscriptions, Jira workflows, interviews, or who to contact for an issue."
)


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
    if any(w in low for w in ("jira", "ticket", "patch", "team")):
        return [
            "How do I coordinate patching with Jira teams?",
            "How does the Jira customer bot work?",
            "Who do I contact for help?",
        ]
    if any(w in low for w in ("lab", "terminal", "scenario")):
        return [
            "How do I launch a lab?",
            "What if validation fails?",
            "How do I use hints?",
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

    custom = _match_custom_faq(text, custom_faq)
    if custom:
        return {
            "reply": custom,
            "suggestions": _suggestions_for_context(text),
            "typing_delay_ms": int(row.support_bot_typing_delay_ms or 1200),
        }

    if not text or any(w in low for w in ("hello", "hi", "hey", "help", "start")):
        welcome = row.support_bot_welcome_message or DEFAULT_WELCOME
        if not is_authenticated:
            welcome += "\n\nSign in or create a free account from the top menu to launch labs and track progress."
        return {
            "reply": welcome,
            "suggestions": [t["prompt"] for t in (row.support_bot_quick_topics or DEFAULT_QUICK_TOPICS)[:4]],
            "typing_delay_ms": int(row.support_bot_typing_delay_ms or 1200),
        }

    if any(w in low for w in ("launch", "start lab", "open lab", "begin lab", "how to lab")):
        reply = (
            "**Launching a lab**\n"
            "1. Go to **Technologies** in the sidebar and pick a stack (e.g. Linux).\n"
            "2. Open a scenario and click **Start Lab** (subscription required for most scenarios).\n"
            "3. Use the embedded terminal — commands run on a simulated server.\n"
            "4. Complete objectives, run validation, then **Stop Lab** when finished.\n\n"
            "Demo scenarios are available without a subscription from the scenario page."
        )
    elif any(w in low for w in ("subscribe", "subscription", "pricing", "pay", "purchase", "renew")):
        pay_line = f"\nBilling questions: **{payment}**" if payment else ""
        reply = (
            "**Subscriptions**\n"
            "• Subscriptions are **per technology** — pay only for stacks you need.\n"
            "• Open **Pricing** or **Subscriptions** to view plans and renew.\n"
            "• After payment, scenarios for that technology unlock immediately.\n"
            f"• Support: **{support}**{pay_line}"
        )
    elif any(w in low for w in ("jira", "ticket", "incident", "change window")):
        reply = (
            "**Jira in FixitLab**\n"
            "• Each scenario can have a simulated Jira ticket with customer notes.\n"
            "• Comment on the ticket to ask the **customer bot** about impact, timeline, or symptoms.\n"
            "• Mention **@backup team**, **@database team**, **@application team** for patching prep.\n"
            "• Mention **@storage team** to provision disks (LVM labs) or **@network team** for NIC/IP.\n"
            "• Team bots reply after ~30 seconds and update the lab environment — then continue in the terminal.\n\n"
            "The original Jira customer bot still works for non-team questions."
        )
    elif any(w in low for w in ("patch", "patching", "reboot", "yum update", "dnf update")):
        reply = (
            "**Patching workflow (realistic simulation)**\n"
            "1. In Jira, ask **@backup team**, **@database team**, and **@application team** to stop services and take backup.\n"
            "2. Wait for bot confirmations (~30s), then run **precheck** in the terminal.\n"
            "3. Apply patches, **reboot**, run **postcheck**.\n"
            "4. If apps fail to start, check Jira — you may need to fix mounts (`mount -a`) before asking teams to start again.\n"
            "5. Ask teams to **start** database and application in Jira when done."
        )
    elif any(w in low for w in ("lvm", "disk", "storage", "extend", "volume")):
        reply = (
            "**Disk / LVM labs**\n"
            "• Request a new disk in Jira: mention **@storage team** to add/attach a disk.\n"
            "• After the bot confirms (~30s), verify with `fdisk -l` or `lsblk` in the terminal.\n"
            "• If the disk is missing, rescan SCSI (`echo 1 > /sys/class/scsi_host/.../scan`) or ask storage again in Jira.\n"
            "• Then create PV/VG/LV and extend filesystems as the scenario requires."
        )
    elif any(w in low for w in ("network", "nic", "ip addr", "vlan", "interface")):
        reply = (
            "**Network labs**\n"
            "• Ask **@network team** in Jira to add a NIC or secondary IP.\n"
            "• After confirmation, verify with `ip addr` or `nmcli` in the terminal.\n"
            "• Configure interfaces per scenario objectives, then validate."
        )
    elif any(w in low for w in ("interview", "mock interview", "voice", "camera", "mic")):
        reply = (
            "**AI Interview Studio**\n"
            "• Open **Interviews** from the sidebar (or /mock-interviews when logged out).\n"
            "• Upload a resume, pick rounds, and allow microphone (and camera when required).\n"
            "• Plans are separate from technology lab subscriptions — see **Pricing**.\n"
            "• Certificates verify at **Verify Certificate** (`FIXIT-INT-…` IDs)."
        )
    elif any(w in low for w in ("contact", "email", "support", "who to", "reach", "issue", "bug", "problem")):
        pay_line = f"\n• **Payments / refunds:** {payment}" if payment else ""
        reply = (
            "**Who to contact**\n"
            f"• **General support & labs:** {support}\n"
            f"{pay_line}\n"
            "• **In-app:** Community forum, FAQ page, or this assistant.\n"
            "• **Account:** Profile → notification preferences or delete account.\n\n"
            "For lab-specific blockers, include scenario name and what you tried in the terminal."
        )
    elif any(w in low for w in ("validation", "validate", "pass", "check solution", "verify lab")):
        reply = (
            "**Validation**\n"
            "• Run the scenario's validate command or click **Validate** in the lab UI.\n"
            "• Ensure all objectives are met (services up, config correct, Jira steps done if required).\n"
            "• Patching labs need precheck/postcheck and team coordination in Jira.\n"
            "• Review hints if stuck — limited hints per scenario."
        )
    elif any(w in low for w in ("hint", "stuck", "clue")):
        reply = (
            "**Hints**\n"
            "• Each scenario has a limited number of hints.\n"
            "• Open the hints panel in the lab runner — progressive hints avoid spoiling the full answer.\n"
            "• After time expires you can view the solution explanation."
        )
    elif any(w in low for w in ("certificate", "achievement", "badge")):
        reply = (
            "**Certificates & achievements**\n"
            "• Complete scenarios to earn achievements and technology progress.\n"
            "• Interview campaigns issue **FIXIT-INT** certificates when all rounds pass.\n"
            "• Verify any certificate at **Verify Certificate** in the menu."
        )
    elif any(w in low for w in ("disable", "turn off", "hide bot", "stop bot")):
        reply = (
            "**Hide this assistant**\n"
            "• Click the **X** on the chat panel or the floating bot button to minimize.\n"
            "• To disable permanently: **Profile → Preferences → FixitLab Assistant** and turn it off.\n"
            "• Admins can disable the bot platform-wide in Admin → Platform Settings."
        )
    elif any(w in low for w in ("technology", "technologies", "browse", "catalog")):
        reply = (
            "**Technologies**\n"
            "• Sidebar → **Technologies** lists all stacks (Linux, networking, etc.).\n"
            "• Each technology page shows scenarios by difficulty.\n"
            "• Subscribe to unlock full scenario access for that stack."
        )
    elif any(w in low for w in ("team", "organization", "invite", "org")):
        reply = (
            "**My Team**\n"
            "• Sidebar → **My Team** for organization invites and member analytics (if your org uses FixitLab).\n"
            "• Managers can track learner progress; learners use their own accounts."
        )
    elif page_path and "/lab/" in page_path:
        reply = (
            "You're in a lab session. Use the terminal for commands, the Jira panel for ticket/team coordination, "
            "and **Validate** when objectives are complete. Ask me about Jira teams, patching, disks, or validation."
        )
    else:
        reply = (
            f"I'm not sure about that specific question. Try asking about:\n"
            "• Launching labs • Subscriptions • Jira & team bots • Patching • LVM/disk • Network • Interviews\n\n"
            f"Or email **{support}** with details and we'll help you directly."
        )

    reply = re.sub(r"\*\*([^*]+)\*\*", r"\1", reply)

    return {
        "reply": reply,
        "suggestions": _suggestions_for_context(text),
        "typing_delay_ms": int(row.support_bot_typing_delay_ms or 1200),
    }
