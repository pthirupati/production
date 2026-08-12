"""Rule-based FixitLab support assistant.

Free / no paid API. The responder is a scored intent engine: each intent has
keyword + regex matchers (and an optional technology affinity), and returns a
specific, multi-step answer with concrete commands. When the user is inside a
lab session the page_path (``/lab/<session_id>``) is resolved to the active
scenario/technology so answers can be tailored to what they are working on.

Lab ticket *operations* (@team mentions, patching, disk/NIC provisioning) are
still owned by the Jira team bots inside the lab session and are redirected
there — see apps.jira_integration.team_bots.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_QUICK_TOPICS = [
    {"label": "Launch a lab", "prompt": "How do I launch a lab?"},
    {"label": "Subscribe", "prompt": "How do I subscribe to a technology?"},
    {"label": "Interviews", "prompt": "How do mock interviews work?"},
    {"label": "Contact support", "prompt": "Who do I contact for help?"},
]

DEFAULT_WELCOME = (
    "Hi! I'm the FixitLab Assistant — your platform guide for subscriptions, launching labs, "
    "interviews, certificates, and who to contact.\n\n"
    "I can also help with technical how-tos and troubleshooting for VMware, Linux, Kubernetes, "
    "Docker, and networking. Ask me something like \"vm won't power on\" or \"ssh connection refused\".\n\n"
    "Lab ticket actions (@team mentions, patching, provisioning disks/NICs) belong in the Jira "
    "panel inside your lab session — not here."
)

JIRA_LAB_REDIRECT = (
    "That's a lab ticket action — use the Jira panel in the lab runner, not this assistant.\n\n"
    "Inside the ticket you can:\n"
    "• Ask the customer bot about impact, timeline, symptoms, or logs\n"
    "• Mention @backup team, @database team, @application team for patching prep\n"
    "• Mention @storage team to provision disks or @network team for NIC/IP\n\n"
    "Team bots reply after ~30 seconds and update the simulated server. "
    "Then continue in the terminal."
)

# Topics handled only by Jira bots inside an active lab session. Kept narrow so
# that generic technical questions ("how do I add a datastore?") still get a
# real answer instead of a redirect.
_JIRA_LAB_KEYWORDS = (
    "@backup", "@database", "@application", "@storage", "@network", "@dba",
    "customer bot", "team bot", "backup team", "database team",
    "application team", "storage team", "network team",
    "stop database for patch", "start database", "start application",
    "take backup", "change window", "proceeding with patch", "precheck",
    "postcheck", "patching workflow",
)

# Keywords that, when combined with a Jira/ticket word, mean the user wants
# ticket *operations* rather than a how-to explanation.
_JIRA_ACTION_HINTS = (
    "mention", "team", "@", "stop ", "start ", "take backup", "patch",
    "change window", "provision", "drain",
)


def _is_jira_lab_question(text: str, page_path: str = "") -> bool:
    low = text.lower()
    if any(kw in low for kw in _JIRA_LAB_KEYWORDS):
        return True
    # "jira"/"ticket"/"incident" only redirects when it looks like an action
    # request, not an informational "how does jira work" question — those are
    # handled explicitly by the jira_help intent below.
    if any(w in low for w in ("jira", "ticket", "incident")) and any(
        h in low for h in _JIRA_ACTION_HINTS
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


# ---------------------------------------------------------------------------
# Context awareness — resolve the active lab session from the page path.
# ---------------------------------------------------------------------------

_SESSION_PATH_RE = re.compile(r"/lab/([0-9a-fA-F-]{8,})")

# Map a technology slug (or words found in scenario slug/title) to a topic group
# used for biasing intent detection and choosing fallback topics.
_TECH_GROUPS = {
    "vmware": "vmware",
    "vsphere": "vmware",
    "esxi": "vmware",
    "rhel-linux": "linux",
    "linux": "linux",
    "shell-script": "linux",
    "ansible": "linux",
    "kubernetes": "kubernetes",
    "k8s": "kubernetes",
    "docker": "docker",
    "container": "docker",
    "networking": "network",
    "network": "network",
    "database": "database",
    "storage": "storage",
}


def resolve_lab_context(page_path: str, user=None) -> dict:
    """Best-effort lookup of the scenario/technology behind a ``/lab/<id>`` path.

    Returns a dict with ``scenario_slug``, ``technology_slug``, ``scenario_title``
    and a derived ``group`` (vmware/linux/kubernetes/docker/network/...). All keys
    are empty strings when no context is available. Never raises.

    SECURITY (audit Z3-9): ``page_path`` is supplied by the caller on an
    ``AllowAny`` endpoint, and this used to look the session up by id ALONE. Anyone
    holding a session UUID — including an anonymous caller — got back that session's
    scenario slug, title and technology. UUID4 makes it unguessable, so the impact is
    small, but "unguessable" is not an access control: the id leaks through logs,
    screenshots, shared URLs and referrers. The lookup is now scoped to the
    requesting user, and an unauthenticated caller gets no context at all rather
    than someone else's.
    """
    ctx = {"scenario_slug": "", "technology_slug": "", "scenario_title": "", "group": ""}
    if not page_path:
        return ctx
    if user is None or not getattr(user, "is_authenticated", False):
        return ctx
    match = _SESSION_PATH_RE.search(page_path)
    if not match:
        return ctx
    session_id = match.group(1)
    try:
        from apps.labs.models import LabSession

        session = (
            LabSession.objects.filter(id=session_id, user=user)
            .select_related("scenario", "scenario__technology")
            .first()
        )
        if not session or not session.scenario_id:
            return ctx
        scenario = session.scenario
        tech = getattr(scenario, "technology", None)
        ctx["scenario_slug"] = (scenario.slug or "").lower()
        ctx["scenario_title"] = scenario.title or ""
        ctx["technology_slug"] = (getattr(tech, "slug", "") or "").lower()
        ctx["group"] = _group_for_context(ctx)
    except Exception as exc:  # pragma: no cover - context is best-effort
        logger.debug("support bot context lookup failed: %s", exc)
    return ctx


def _group_for_context(ctx: dict) -> str:
    tech = ctx.get("technology_slug", "")
    if tech in _TECH_GROUPS:
        return _TECH_GROUPS[tech]
    haystack = f"{ctx.get('technology_slug', '')} {ctx.get('scenario_slug', '')} {ctx.get('scenario_title', '')}".lower()
    for key, group in _TECH_GROUPS.items():
        if key in haystack:
            return group
    return ""


def _detect_group(text: str) -> str:
    """Detect a technology group purely from the user's wording."""
    low = text.lower()
    if any(w in low for w in ("vmware", "vsphere", "esxi", "esxcli", "vim-cmd", "vcenter", "vmkernel", "vmotion", "datastore", "vmdk")):
        return "vmware"
    if any(w in low for w in ("kubernetes", "k8s", "kubectl", "pod", "kubelet", "namespace", "deployment", "crashloop")):
        return "kubernetes"
    if any(w in low for w in ("docker", "container", "dockerfile", "compose", "image pull")):
        return "docker"
    if any(w in low for w in ("systemd", "systemctl", "journalctl", "fstab", "selinux", "linux", "permission denied", "chmod", "chown")):
        return "linux"
    if any(w in low for w in ("ssh", "ping", "dns", "firewall", "iptables", "port", "tcp", "subnet", "route", "network")):
        return "network"
    return ""


# ---------------------------------------------------------------------------
# Intent engine
# ---------------------------------------------------------------------------

# KB-style section labels (used inside answers as "see ..." references).
KB = "Knowledge Base"


def _b(text: str) -> str:
    """Mark a phrase important; rendered as plain text after markdown strip."""
    return f"**{text}**"


def _kb(section: str) -> str:
    return f"\n\nKB: {KB} → {section}"


# Each intent: keywords (any-match), optional regex (any-match), optional
# `group` affinity (adds score when the detected/context group matches), and a
# builder returning the answer string. Higher total score wins.
_INTENTS: list[dict] = []


def _intent(name, keywords=(), patterns=(), group="", weight=1.0):
    """Decorator to register an intent's answer builder."""

    compiled = [re.compile(p, re.I) for p in patterns]

    def deco(fn):
        _INTENTS.append(
            {
                "name": name,
                "keywords": tuple(k.lower() for k in keywords),
                "patterns": compiled,
                "group": group,
                "weight": weight,
                "build": fn,
            }
        )
        return fn

    return deco


def _score_intent(intent: dict, low: str, group: str) -> float:
    score = 0.0
    for kw in intent["keywords"]:
        if kw in low:
            # Longer/multi-word keywords are stronger signals.
            score += 1.0 + (0.5 if " " in kw else 0.0)
    for pat in intent["patterns"]:
        if pat.search(low):
            score += 1.5
    if score and intent["group"] and intent["group"] == group:
        score += 1.25  # technology context/affinity boost
    return score * intent["weight"]


# ---- Platform / account intents ------------------------------------------


@_intent(
    "launch_lab",
    keywords=("launch a lab", "launch lab", "start a lab", "start lab", "open lab",
              "begin lab", "how to lab", "run a lab", "spin up a lab"),
    patterns=(r"\bhow .*\blab\b.*\b(start|launch|run|begin|open)\b",),
)
def _i_launch(ctx, **kw):
    extra = ""
    if ctx.get("scenario_title"):
        extra = f"\n\nYou're currently in {_b(ctx['scenario_title'])} — just use the terminal below and click Validate when the objectives are met."
    return (
        "Launching a lab\n"
        "1. Go to Technologies in the sidebar and pick a stack (e.g. Linux, VMware, Kubernetes).\n"
        "2. Open a scenario and click Start Lab (subscription required for most scenarios).\n"
        "3. Use the embedded terminal — commands run on a simulated server.\n"
        "4. Complete the objectives, run Validate, then Stop Lab when finished.\n\n"
        "During the lab, open the Jira panel for ticket and team coordination." + extra
    )


@_intent(
    "subscribe",
    keywords=("subscribe", "subscription", "pricing", "upgrade plan", "purchase", "renew",
              "how much", "cost", "price", "buy access", "unlock technology"),
    patterns=(r"\bhow (do|can) i (pay|subscribe|buy)\b",),
)
def _i_subscribe(ctx, support="", payment="", **kw):
    pay_line = f"\n• Billing questions: {payment}" if payment else ""
    return (
        "Subscriptions\n"
        "• Subscriptions are per technology — pay only for the stacks you need.\n"
        "• Open Pricing or Subscriptions to view plans and renew.\n"
        "• After payment, every scenario for that technology unlocks immediately.\n"
        "• You can keep using labs you already started until they expire.\n"
        f"• Support: {support}{pay_line}"
    )


@_intent(
    "billing_problem",
    keywords=("payment failed", "charged twice", "refund", "invoice", "receipt",
              "billing issue", "card declined", "double charge", "cancel subscription"),
)
def _i_billing(ctx, support="", payment="", **kw):
    contact = payment or support
    return (
        "Billing & payments\n"
        f"• Failed or duplicate charge: email {contact} with the date, amount, and last 4 digits — do not retry blindly.\n"
        "• Refunds: request within the window shown on the Pricing page; processed to the original method.\n"
        "• Invoices/receipts: Profile → Billing, or ask support to resend.\n"
        "• Cancel: subscriptions are per technology — cancel from Subscriptions; access stays active until the period ends.\n\n"
        "Subscriptions do not auto-charge a new technology you didn't buy."
    )


@_intent(
    "interview",
    keywords=("interview", "mock interview", "interview studio", "resume", "rounds",
              "voice interview", "proctor"),
    patterns=(r"\bhow .*interview", r"\binterview.*work"),
    group="",
)
def _i_interview(ctx, **kw):
    return (
        "AI Interview Studio\n"
        "1. Open Interviews from the sidebar (or /mock-interviews when logged out).\n"
        "2. Upload a resume and pick the rounds (technical, behavioral, system design).\n"
        "3. Allow microphone access — and camera when a round requires proctoring.\n"
        "4. Answer out loud; the assistant scores each round and gives feedback.\n\n"
        "• Interview plans are separate from technology lab subscriptions (see Pricing).\n"
        "• Pass all rounds to earn a certificate (FIXIT-INT-… ID), verifiable at Verify Certificate."
    )


@_intent(
    "interview_mic_camera",
    keywords=("mic not working", "microphone not working", "camera not working",
              "can't hear", "no audio", "permission denied camera", "allow microphone",
              "browser blocked", "mic blocked", "camera blocked"),
    patterns=(r"\b(mic|microphone|camera).*(not|won'?t|can'?t|block|deny|denied)\b",),
    weight=1.6,
)
def _i_interview_media(ctx, **kw):
    return (
        "Microphone / camera not working in interviews\n"
        "1. Check the browser permission: click the lock/camera icon in the address bar and set Microphone (and Camera) to Allow, then reload.\n"
        "2. Make sure no other app (Zoom/Meet) is holding the device.\n"
        "3. In OS settings, confirm the browser has microphone/camera access.\n"
        "4. Try Chrome/Edge in a non-incognito window — incognito often blocks devices.\n"
        "5. Pick the right device from the in-app device selector before starting.\n\n"
        "Still silent? Reload the interview page — the studio re-requests permission on load."
    )


@_intent(
    "contact_support",
    keywords=("contact", "reach support", "talk to a human", "email support", "who to",
              "report a bug", "report bug", "raise a complaint", "human support"),
    patterns=(r"\bwho .*\b(contact|email|reach)\b",),
)
def _i_contact(ctx, support="", payment="", **kw):
    pay_line = f"\n• Payments / refunds: {payment}" if payment else ""
    return (
        "Who to contact\n"
        f"• General support & labs: {support}{pay_line}\n"
        "• In-app: Community forum, FAQ page, or this assistant (platform + how-to questions).\n"
        "• Account: Profile → notification preferences or delete account.\n\n"
        "For active lab incidents, use the Jira panel in your lab session."
    )


@_intent(
    "validation",
    keywords=("validation", "validate", "check solution", "verify lab", "objectives",
              "did i pass", "mark complete", "grade", "score lab"),
    patterns=(r"\bvalidat", r"\bwhy .*not pass", r"\bcheck .*solution"),
)
def _i_validation(ctx, **kw):
    return (
        "Validation\n"
        "• Click Validate in the lab UI once the objectives are complete.\n"
        "• The checker inspects the live server state (files, services, config) plus any scenario rules.\n"
        "• If it fails, read the per-objective result — it names exactly what's missing.\n"
        "• Ticket/team steps must be finished in the Jira panel before validation can pass.\n"
        "• Use hints if stuck (limited per scenario)."
    )


@_intent(
    "hints",
    keywords=("hint", "stuck", "clue", "give me a hint", "i'm lost", "solution",
              "show answer", "walkthrough"),
)
def _i_hints(ctx, **kw):
    return (
        "Hints & solutions\n"
        "• Each scenario has a limited number of progressive hints — open the Hints panel in the lab runner.\n"
        "• Hints reveal the approach step by step without spoiling the full answer.\n"
        "• After the timer expires (or all hints are used) you can view the solution explanation.\n"
        "• Using hints reduces the score for that scenario but still records completion."
    )


@_intent(
    "certificate",
    keywords=("certificate", "achievement", "badge", "verify certificate", "credential",
              "completion proof", "diploma"),
)
def _i_certificate(ctx, **kw):
    return (
        "Certificates & achievements\n"
        "• Completing scenarios earns achievements and advances technology progress.\n"
        "• Interview campaigns issue a FIXIT-INT certificate when every round passes.\n"
        "• Verify any certificate (yours or a candidate's) at Verify Certificate in the menu using its FIXIT-INT-… ID."
    )


@_intent(
    "disable_bot",
    keywords=("disable assistant", "turn off bot", "hide bot", "stop bot", "close assistant",
              "disable chat", "hide assistant", "mute bot"),
)
def _i_disable(ctx, **kw):
    return (
        "Hide this assistant\n"
        "• Click X on the chat panel, or the floating Help button, to minimize it.\n"
        "• To disable it for your account: Profile → FixitLab Assistant toggle.\n"
        "• Admins can disable the bot platform-wide in Admin → Platform Settings."
    )


@_intent(
    "browse_tech",
    keywords=("technology", "technologies", "browse", "catalog", "what can i learn",
              "available stacks", "course list"),
)
def _i_browse(ctx, **kw):
    return (
        "Technologies\n"
        "• Sidebar → Technologies lists every stack (Linux, VMware, Kubernetes, Docker, Networking, Database, and more).\n"
        "• Each technology page shows its scenarios grouped by difficulty.\n"
        "• Subscribe to a technology to unlock full scenario access for that stack."
    )


@_intent(
    "team_org",
    keywords=("my team", "organization", "invite member", "org account", "manager",
              "team analytics", "seats", "learner progress"),
)
def _i_team(ctx, **kw):
    return (
        "My Team / organizations\n"
        "• Sidebar → My Team for organization invites and member analytics.\n"
        "• Managers can track each learner's scenario progress and scores.\n"
        "• Learners use their own accounts; invite them by email from the team page."
    )


@_intent(
    "jira_help",
    keywords=("how does jira work", "what is the jira panel", "jira panel", "how do tickets work",
              "what are the team bots", "how do team mentions"),
    patterns=(r"\bhow .*\bjira\b.*work", r"\bwhat .*\bjira\b"),
)
def _i_jira_help(ctx, **kw):
    return (
        "How the lab Jira panel works\n"
        "• Many scenarios open a simulated incident ticket alongside the terminal.\n"
        "• The customer bot answers questions about impact, timeline, and symptoms — just type in the ticket.\n"
        "• Mention a team to get action: @backup team, @database team, @application team (patching prep), "
        "@storage team (provision disks), @network team (NIC/IP).\n"
        "• Team bots reply after ~30s and actually change the simulated server (e.g. attach a disk).\n\n"
        "Do this inside the Jira panel of your lab — not in this assistant."
    )


# ---- VMware intents -------------------------------------------------------


@_intent(
    "vmware_vm_power",
    keywords=("vm won't power on", "vm wont power on", "cannot power on", "won't start vm",
              "power on failed", "vm not powering", "guest won't boot", "failed to power on",
              "vm powered off"),
    patterns=(r"\bvm\b.*(power|start|boot).*(fail|won'?t|can'?t|not)", r"power[- ]?on.*fail"),
    group="vmware",
    weight=1.1,
)
def _i_vmw_power(ctx, **kw):
    return (
        "VM won't power on (vSphere/ESXi)\n"
        "1. Find the VM: " + _b("vim-cmd vmsvc/getallvms") + " — note its VMID.\n"
        "2. Check current state: " + _b("vim-cmd vmsvc/power.getstate <VMID>") + ".\n"
        "3. Try to power on: " + _b("vim-cmd vmsvc/power.on <VMID>") + " and read the exact error.\n"
        "Common causes & fixes:\n"
        "• \"Insufficient resources\" → check host with " + _b("esxcli system memory get") + " / DRS or reservations.\n"
        "• \"File locked / cannot open the disk\" → another host holds a lock: "
        + _b("vmkfstools -D /vmfs/volumes/<ds>/<vm>/<disk>.vmdk") + " then release the stale lock.\n"
        "• Datastore full → " + _b("df -h") + " on the host; free space or migrate.\n"
        "• \"VM needs consolidation\" → Snapshots → Consolidate.\n"
        "4. Inspect logs: " + _b("/vmfs/volumes/<ds>/<vm>/vmware.log") + " for the precise failure."
        + _kb("VMware → VM power operations")
    )


@_intent(
    "vmware_host_disconnect",
    keywords=("host disconnected", "host not responding", "esxi disconnected",
              "host unreachable", "host greyed out", "reconnect host"),
    patterns=(r"host.*(disconnect|not respond|unreach|grey)",),
    group="vmware",
    weight=1.1,
)
def _i_vmw_host(ctx, **kw):
    return (
        "ESXi host disconnected / not responding in vCenter\n"
        "1. Ping the host management IP; confirm it's reachable from vCenter.\n"
        "2. SSH to the host and check the management agents:\n"
        "   • " + _b("/etc/init.d/hostd status") + " and " + _b("/etc/init.d/vpxa status") + "\n"
        "   • Restart if needed: " + _b("/etc/init.d/hostd restart && /etc/init.d/vpxa restart") + "\n"
        "3. Verify the host isn't out of memory: " + _b("esxtop") + " (press m for memory).\n"
        "4. In vCenter: right-click the host → Connection → Reconnect.\n"
        "5. If it stays disconnected, check time sync (NTP) and that 902/443 aren't blocked between host and vCenter."
        + _kb("VMware → Host connectivity")
    )


@_intent(
    "vmware_datastore",
    keywords=("add a datastore", "add datastore", "create datastore", "mount datastore",
              "new datastore", "vmfs datastore", "present lun"),
    patterns=(r"\b(add|create|mount|new).*datastore",),
    group="vmware",
    weight=1.1,
)
def _i_vmw_datastore(ctx, **kw):
    return (
        "Add a datastore (VMFS) to ESXi\n"
        "1. Rescan so the host sees new storage: " + _b("esxcli storage core adapter rescan --all") + ".\n"
        "2. List visible devices: " + _b("esxcli storage core device list") + " — copy the device naa.* ID.\n"
        "3. Create the VMFS datastore (GUI: Host → Datastores → New Datastore → VMFS), or via CLI:\n"
        "   " + _b("vmkfstools -C vmfs6 -S <DatastoreName> /vmfs/devices/disks/<naa.id>:1") + "\n"
        "4. Confirm it mounted: " + _b("esxcli storage filesystem list") + ".\n"
        "5. For NFS instead: " + _b("esxcli storage nfs add -H <nfs-server> -s /export -v <Name>") + ".\n\n"
        "Tip: if the LUN doesn't appear, verify zoning/initiator on the storage side first."
        + _kb("VMware → Datastores & storage")
    )


@_intent(
    "vmware_vmotion",
    keywords=("vmotion failed", "vmotion error", "migration failed", "cannot migrate vm",
              "vmotion stuck", "live migration"),
    patterns=(r"vmotion.*(fail|error|stuck)", r"migrat.*vm.*fail"),
    group="vmware",
)
def _i_vmw_vmotion(ctx, **kw):
    return (
        "vMotion / migration failing\n"
        "1. Confirm both hosts have a VMkernel adapter tagged for vMotion on the same subnet: "
        + _b("esxcli network ip interface ipv4 get") + ".\n"
        "2. Test connectivity on the vMotion VMkernel: " + _b("vmkping -I vmk1 <other-host-vmk-ip>") + ".\n"
        "3. CPU mismatch (\"not compatible\") → enable EVC on the cluster to the lowest common baseline.\n"
        "4. Shared storage: the VM's datastore must be visible to the target host (or use Storage vMotion).\n"
        "5. Read the failure reason in Recent Tasks; check " + _b("/var/log/vmkernel.log") + " on both hosts."
        + _kb("VMware → vMotion")
    )


# ---- Linux intents --------------------------------------------------------


@_intent(
    "linux_service_failed",
    keywords=("service failed", "service won't start", "systemctl failed", "failed to start",
              "unit failed", "service not starting", "daemon won't start", "service dead"),
    patterns=(r"(service|daemon|unit).*(fail|won'?t start|not start|dead)", r"systemctl.*fail"),
    group="linux",
    weight=1.1,
)
def _i_linux_service(ctx, **kw):
    return (
        "A Linux service won't start (systemd)\n"
        "1. Check status + recent error: " + _b("systemctl status <name>") + ".\n"
        "2. Read the full logs: " + _b("journalctl -u <name> -n 80 --no-pager") + " (add -b for this boot).\n"
        "3. Validate the unit/config before retrying (e.g. " + _b("nginx -t") + ", " + _b("sshd -t") + ").\n"
        "4. Common causes: port already in use (" + _b("ss -ltnp | grep <port>") + "), wrong file "
        "permissions/SELinux denial, or a bad path in the unit file.\n"
        "5. Reload after editing a unit: " + _b("systemctl daemon-reload && systemctl restart <name>") + ".\n"
        "6. Make it persist: " + _b("systemctl enable --now <name>") + "."
        + _kb("Linux → systemd services")
    )


@_intent(
    "linux_disk_full",
    keywords=("disk full", "no space left", "filesystem full", "out of disk", "100% disk",
              "cannot write disk full", "df full"),
    patterns=(r"no space left", r"disk.*full", r"100% .*\b(disk|/)\b"),
    group="linux",
    weight=1.1,
)
def _i_linux_disk(ctx, **kw):
    return (
        "Disk full / \"No space left on device\"\n"
        "1. See which mount is full: " + _b("df -h") + ".\n"
        "2. Find the big directories: " + _b("du -xh / 2>/dev/null | sort -rh | head -20") + ".\n"
        "3. Check for deleted-but-open files holding space: " + _b("lsof +L1") + " (restart that process to release).\n"
        "4. Out of inodes (space looks free but writes fail)? " + _b("df -i") + ".\n"
        "5. Safe cleanups: " + _b("journalctl --vacuum-size=200M") + ", rotate/clear old logs in /var/log, clear package cache.\n"
        "6. Need more space and it's LVM: " + _b("lvextend -r -L +10G /dev/<vg>/<lv>") + " (the -r resizes the filesystem)."
        + _kb("Linux → Storage & filesystems")
    )


@_intent(
    "linux_permission",
    keywords=("permission denied", "access denied", "operation not permitted", "cannot access",
              "chmod", "chown", "sudo required", "not owner"),
    patterns=(r"permission denied", r"not permitted"),
    group="linux",
)
def _i_linux_perm(ctx, **kw):
    return (
        "\"Permission denied\" on Linux\n"
        "1. Inspect the target: " + _b("ls -l <path>") + " (owner, group, mode) and " + _b("id") + " (your uid/groups).\n"
        "2. Fix ownership: " + _b("chown user:group <path>") + "; fix mode: " + _b("chmod 640 <file>") + " / " + _b("chmod 750 <dir>") + ".\n"
        "3. Whole tree: add -R, e.g. " + _b("chown -R user:group <dir>") + ".\n"
        "4. If commands need root, prefix with " + _b("sudo") + " (check " + _b("sudo -l") + " for what you're allowed).\n"
        "5. Still denied on RHEL? It's likely SELinux — see " + _b("ausearch -m AVC -ts recent") + " and restore context with "
        + _b("restorecon -Rv <path>") + "."
        + _kb("Linux → Permissions & SELinux")
    )


@_intent(
    "linux_high_load",
    keywords=("high cpu", "high load", "server slow", "load average", "100% cpu",
              "out of memory", "oom", "memory leak", "system slow"),
    patterns=(r"high (cpu|load|memory)", r"\boom\b", r"server (slow|hung|frozen)"),
    group="linux",
)
def _i_linux_load(ctx, **kw):
    return (
        "Server is slow / high CPU or memory\n"
        "1. Top consumers right now: " + _b("top -o %CPU") + " (or " + _b("htop") + "); for memory press Shift+M.\n"
        "2. Load average vs cores: " + _b("uptime") + " and " + _b("nproc") + " — load >> cores means saturation.\n"
        "3. Disk I/O wait: " + _b("iostat -xz 1 3") + " (high %util / await = storage bottleneck).\n"
        "4. Memory pressure / OOM kills: " + _b("free -h") + " and " + _b("dmesg -T | grep -i oom") + ".\n"
        "5. Per-process detail: " + _b("ps aux --sort=-%mem | head") + " then investigate the top PID.\n"
        "6. Persisting? Check " + _b("journalctl -p err -b") + " for repeated errors driving the load."
        + _kb("Linux → Performance triage")
    )


@_intent(
    "linux_boot",
    keywords=("won't boot", "wont boot", "kernel panic", "emergency mode", "rescue mode",
              "fstab error", "boot failure", "grub", "stuck at boot"),
    patterns=(r"(won'?t|can'?t|fail).*boot", r"kernel panic", r"emergency mode"),
    group="linux",
)
def _i_linux_boot(ctx, **kw):
    return (
        "Linux won't boot / drops to emergency mode\n"
        "1. Most common cause is a bad /etc/fstab entry. Boot to emergency shell and run " + _b("journalctl -xb") + " to see the failed mount.\n"
        "2. Remount root writable: " + _b("mount -o remount,rw /") + ", then fix /etc/fstab (comment the bad line or add " + _b("nofail") + ").\n"
        "3. Re-test mounts without rebooting: " + _b("mount -a") + " — it must return cleanly.\n"
        "4. Filesystem corruption: " + _b("fsck -y /dev/<device>") + " on the unmounted FS.\n"
        "5. GRUB/kernel issue → boot a previous kernel from the GRUB menu, then rebuild initramfs/grub config.\n"
        "6. Reboot once mount -a is clean."
        + _kb("Linux → Boot & init")
    )


# ---- SSH / networking intents --------------------------------------------


@_intent(
    "ssh_refused",
    keywords=("ssh connection refused", "connection refused", "ssh refused", "can't ssh",
              "cannot ssh", "ssh not working", "ssh timeout", "ssh permission denied",
              "ssh closed by remote", "publickey", "ssh login"),
    patterns=(r"ssh.*(refus|time|fail|denied|closed|connect)", r"connection refused",
              r"permission denied \(publickey", r"\bssh\b"),
    group="network",
    weight=1.4,
)
def _i_ssh(ctx, **kw):
    return (
        "SSH connection refused / can't connect\n"
        "\"Connection refused\" means you reached the host but nothing is listening on the SSH port:\n"
        "1. On the server, is sshd running? " + _b("systemctl status sshd") + " → start with " + _b("systemctl enable --now sshd") + ".\n"
        "2. Is it listening on 22? " + _b("ss -ltnp | grep :22") + ".\n"
        "3. From the client, test reachability + port: " + _b("ping <host>") + " then " + _b("nc -vz <host> 22") + ".\n"
        "4. Firewall blocking it? " + _b("firewall-cmd --add-service=ssh --permanent && firewall-cmd --reload") + " (or check iptables/security groups).\n"
        "If instead you get \"Permission denied (publickey)\": check key/permissions — "
        + _b("chmod 600 ~/.ssh/id_*") + ", confirm the public key is in the server's " + _b("~/.ssh/authorized_keys") + ", "
        "and watch " + _b("journalctl -u sshd -f") + " while you retry."
        + _kb("Networking → SSH access")
    )


@_intent(
    "network_connectivity",
    keywords=("cannot connect", "can't connect", "no connectivity", "can't reach", "cannot reach",
              "ping fails", "no route to host", "host unreachable", "connection timed out",
              "network down", "can't ping"),
    patterns=(r"(can'?t|cannot|unable).*(connect|reach|ping)", r"no route to host", r"connection timed out"),
    group="network",
    weight=1.05,
)
def _i_net(ctx, **kw):
    return (
        "Can't connect / no network connectivity\n"
        "Work outward layer by layer:\n"
        "1. Link/IP: " + _b("ip addr") + " (have an address?) and " + _b("ip link") + " (is the NIC UP?).\n"
        "2. Gateway: " + _b("ip route") + " then " + _b("ping <gateway>") + " — local network OK?\n"
        "3. Internet: " + _b("ping 8.8.8.8") + " (raw IP) — works but names don't? It's DNS.\n"
        "4. DNS: " + _b("cat /etc/resolv.conf") + " and " + _b("dig <host>") + " (or nslookup).\n"
        "5. Specific service: " + _b("nc -vz <host> <port>") + " to see if the port is open/filtered.\n"
        "6. Firewall on either end: " + _b("firewall-cmd --list-all") + " / security-group rules.\n\n"
        "\"No route to host\" = routing/firewall; \"Connection refused\" = reached host, service down; "
        "\"timed out\" = packets dropped (firewall/wrong IP)."
        + _kb("Networking → Connectivity triage")
    )


@_intent(
    "dns_issue",
    keywords=("dns not resolving", "name resolution", "can't resolve", "cannot resolve",
              "nslookup fails", "dig fails", "host not found", "name or service not known"),
    patterns=(r"(can'?t|cannot|won'?t).*resolv", r"name (resolution|or service)"),
    group="network",
)
def _i_dns(ctx, **kw):
    return (
        "DNS not resolving\n"
        "1. What resolver is in use? " + _b("cat /etc/resolv.conf") + ".\n"
        "2. Query directly against it: " + _b("dig @<resolver-ip> <hostname>") + " (or nslookup).\n"
        "3. Bypass DNS to prove it's name-only: " + _b("ping 8.8.8.8") + " works but " + _b("ping google.com") + " fails → DNS.\n"
        "4. /etc/hosts overrides or stale entries: " + _b("getent hosts <hostname>") + ".\n"
        "5. systemd-resolved boxes: " + _b("resolvectl status") + " and " + _b("resolvectl query <host>") + ".\n"
        "6. Fix: point resolv.conf at a working resolver (e.g. 1.1.1.1) or repair the internal DNS server."
        + _kb("Networking → DNS")
    )


@_intent(
    "network_nic_ip",
    keywords=("add a nic", "add nic", "add an ip", "add ip", "second ip", "secondary ip",
              "configure interface", "assign ip", "new network interface", "set static ip"),
    patterns=(r"\b(add|assign|configure|set).*(nic|ip|interface)\b",),
    group="network",
)
def _i_nic(ctx, **kw):
    lab_note = ""
    if ctx.get("scenario_slug"):
        lab_note = (
            "\n\nNote: in this lab, provisioning a NIC/IP is done by the platform — "
            "mention @network team in the Jira panel and it will attach the interface to the simulated server."
        )
    return (
        "Add a NIC / assign an IP on Linux\n"
        "1. List interfaces: " + _b("ip addr") + " (or " + _b("nmcli device status") + ").\n"
        "2. Temporary IP (lost on reboot): " + _b("ip addr add 10.0.0.20/24 dev eth0") + " then " + _b("ip link set eth0 up") + ".\n"
        "3. Persistent with NetworkManager: " + _b("nmcli con mod <conn> +ipv4.addresses 10.0.0.20/24") + " then " + _b("nmcli con up <conn>") + ".\n"
        "4. Add a default route if needed: " + _b("ip route add default via 10.0.0.1") + ".\n"
        "5. Verify: " + _b("ip addr show dev eth0") + " and " + _b("ping <gateway>") + "." + lab_note
        + _kb("Networking → Interfaces & IP")
    )


# ---- Kubernetes intents ---------------------------------------------------


@_intent(
    "k8s_pod_pending",
    keywords=("pod pending", "pod stuck pending", "pod not scheduling", "unschedulable",
              "pod won't start", "pod not starting", "pending state"),
    patterns=(r"pod.*(pending|unschedulab|won'?t start|not start)",),
    group="kubernetes",
    weight=1.1,
)
def _i_k8s_pending(ctx, **kw):
    return (
        "Pod stuck in Pending (Kubernetes)\n"
        "1. Read the events — they say exactly why: " + _b("kubectl describe pod <pod> -n <ns>") + " (look at the bottom).\n"
        "Typical reasons:\n"
        "• \"Insufficient cpu/memory\" → no node has room; check " + _b("kubectl top nodes") + " and the pod's requests, or scale the cluster.\n"
        "• \"node(s) had taint ... that the pod didn't tolerate\" → add a toleration or pick another node.\n"
        "• \"pod has unbound immediate PersistentVolumeClaims\" → the PVC isn't bound: " + _b("kubectl get pvc -n <ns>") + ".\n"
        "• nodeSelector/affinity matches nothing → check labels with " + _b("kubectl get nodes --show-labels") + ".\n"
        "2. Confirm nodes are Ready: " + _b("kubectl get nodes") + "."
        + _kb("Kubernetes → Scheduling")
    )


@_intent(
    "k8s_crashloop",
    keywords=("crashloopbackoff", "crash loop", "pod crashing", "container restarting",
              "restart count", "pod keeps restarting", "exit code"),
    patterns=(r"crashloop", r"(pod|container).*(crash|restart)"),
    group="kubernetes",
    weight=1.1,
)
def _i_k8s_crash(ctx, **kw):
    return (
        "Pod in CrashLoopBackOff (Kubernetes)\n"
        "1. Get the crash logs — current and previous container:\n"
        "   " + _b("kubectl logs <pod> -n <ns>") + " and " + _b("kubectl logs <pod> -n <ns> --previous") + ".\n"
        "2. Why it last died: " + _b("kubectl describe pod <pod> -n <ns>") + " → Last State / Exit Code / Reason.\n"
        "Common fixes:\n"
        "• Exit 1 / app error → fix config/env or the image command.\n"
        "• OOMKilled → raise the memory limit in the container spec.\n"
        "• Failing liveness probe → loosen the probe path/timing while the app warms up.\n"
        "• CreateContainerConfigError → a referenced ConfigMap/Secret is missing.\n"
        "3. Iterate: " + _b("kubectl get pods -n <ns> -w") + " to watch restarts settle."
        + _kb("Kubernetes → Pod lifecycle")
    )


@_intent(
    "k8s_imagepull",
    keywords=("imagepullbackoff", "errimagepull", "cannot pull image", "image pull failed",
              "pull access denied", "manifest unknown"),
    patterns=(r"imagepull|errimagepull", r"pull.*(image|access)"),
    group="kubernetes",
)
def _i_k8s_pull(ctx, **kw):
    return (
        "ImagePullBackOff / ErrImagePull (Kubernetes)\n"
        "1. See the exact pull error: " + _b("kubectl describe pod <pod> -n <ns>") + " (Events).\n"
        "2. Check the image name/tag is correct and exists in the registry (no typo, tag not deleted).\n"
        "3. Private registry → you need an imagePullSecret: "
        + _b("kubectl create secret docker-registry regcred --docker-server=... --docker-username=... --docker-password=...") + " "
        "then reference it in the pod spec (imagePullSecrets).\n"
        "4. From a node, test the pull manually: " + _b("crictl pull <image>") + " (or docker pull) to isolate network vs auth.\n"
        "5. Air-gapped/proxy clusters: confirm the node can reach the registry."
        + _kb("Kubernetes → Images & registries")
    )


@_intent(
    "k8s_general",
    keywords=("kubectl", "kubernetes", "k8s", "deployment not", "service not reachable",
              "node notready", "node not ready", "rollout"),
    patterns=(r"\bkubectl\b", r"node.*not ?ready"),
    group="kubernetes",
)
def _i_k8s_general(ctx, **kw):
    return (
        "Kubernetes troubleshooting starter\n"
        "• Cluster health: " + _b("kubectl get nodes") + " and " + _b("kubectl get pods -A") + ".\n"
        "• Why is X broken? Almost always: " + _b("kubectl describe <kind> <name> -n <ns>") + " then " + _b("kubectl logs <pod> -n <ns>") + ".\n"
        "• Service has no endpoints? " + _b("kubectl get endpoints <svc> -n <ns>") + " — empty means the selector matches no ready pods.\n"
        "• Node NotReady? " + _b("kubectl describe node <node>") + " and check kubelet: " + _b("systemctl status kubelet") + " on that node.\n"
        "• Rollout stuck? " + _b("kubectl rollout status deploy/<name> -n <ns>") + " and " + _b("kubectl rollout undo") + " to revert.\n\n"
        "Tell me the symptom (pending, crashloop, image pull, no endpoints) for exact steps."
        + _kb("Kubernetes → Triage map")
    )


# ---- Docker intents -------------------------------------------------------


@_intent(
    "docker_container_exit",
    keywords=("container won't start", "container exits", "container keeps restarting",
              "docker container stopped", "container exited", "docker run fails"),
    patterns=(r"container.*(exit|won'?t start|keeps restart|stopped)", r"docker run.*fail"),
    group="docker",
    weight=1.1,
)
def _i_docker_exit(ctx, **kw):
    return (
        "Docker container won't stay running\n"
        "1. List with status/exit code: " + _b("docker ps -a") + ".\n"
        "2. Read why it exited: " + _b("docker logs <container>") + " (add --tail 100).\n"
        "3. Inspect the exact exit code/state: " + _b("docker inspect <container> --format '{{.State.ExitCode}} {{.State.Error}}'") + ".\n"
        "Common causes:\n"
        "• The main process finished (containers stop when PID 1 exits) — run a long-lived foreground process.\n"
        "• Bad CMD/ENTRYPOINT or missing binary → override to debug: " + _b("docker run -it --entrypoint sh <image>") + ".\n"
        "• OOM (exit 137) → raise " + _b("--memory") + " or fix the leak.\n"
        "4. Port already in use? " + _b("docker run -p 8080:80 ...") + " fails if 8080 is taken — pick another host port."
        + _kb("Docker → Container lifecycle")
    )


@_intent(
    "docker_general",
    keywords=("docker", "dockerfile", "docker compose", "docker image", "build image",
              "docker network", "volume mount"),
    patterns=(r"\bdocker\b", r"dockerfile"),
    group="docker",
)
def _i_docker_general(ctx, **kw):
    return (
        "Docker basics & troubleshooting\n"
        "• Build: " + _b("docker build -t myapp:1.0 .") + " (needs a Dockerfile in the context dir).\n"
        "• Run detached with a port + volume: " + _b("docker run -d -p 8080:80 -v $PWD/data:/data myapp:1.0") + ".\n"
        "• Shell into a running container: " + _b("docker exec -it <container> sh") + ".\n"
        "• Logs: " + _b("docker logs -f <container>") + "; resource use: " + _b("docker stats") + ".\n"
        "• Compose stack: " + _b("docker compose up -d") + " / " + _b("docker compose logs -f") + ".\n"
        "• Networking between containers: put them on the same user-defined network and use the service name as the hostname.\n\n"
        "Tell me the specific error (exits immediately, can't pull, port in use) for targeted steps."
        + _kb("Docker → Getting started")
    )


# ---------------------------------------------------------------------------
# Fallback suggestions
# ---------------------------------------------------------------------------

_GROUP_TOPICS = {
    "vmware": [
        "VM won't power on",
        "ESXi host disconnected",
        "How do I add a datastore?",
    ],
    "linux": [
        "A service won't start",
        "Disk is full",
        "Permission denied error",
    ],
    "kubernetes": [
        "Pod stuck in Pending",
        "Pod in CrashLoopBackOff",
        "ImagePullBackOff error",
    ],
    "docker": [
        "Container won't stay running",
        "How do I run a container?",
        "Can't connect between containers",
    ],
    "network": [
        "SSH connection refused",
        "Cannot connect / no route to host",
        "DNS not resolving",
    ],
    "database": [
        "A service won't start",
        "Disk is full",
        "Who do I contact for help?",
    ],
    "storage": [
        "Disk is full",
        "How do I add a datastore?",
        "A service won't start",
    ],
}

_PLATFORM_TOPICS = [
    "How do I launch a lab?",
    "How do I subscribe to a technology?",
    "How do mock interviews work?",
    "Who do I contact for help?",
]


def _suggestions_for(text: str, group: str) -> list[str]:
    low = text.lower()
    if group and group in _GROUP_TOPICS:
        return _GROUP_TOPICS[group]
    if any(w in low for w in ("lab", "terminal", "scenario", "validate", "hint")):
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


def _fallback_reply(text: str, group: str, support: str, ctx: dict) -> str:
    """Clarifying question + top relevant topics — never a flat 'I can't help'."""
    if group and group in _GROUP_TOPICS:
        label = {
            "vmware": "VMware/vSphere",
            "linux": "Linux",
            "kubernetes": "Kubernetes",
            "docker": "Docker",
            "network": "networking",
            "database": "database",
            "storage": "storage",
        }.get(group, group)
        topics = "\n".join(f"• {t}" for t in _GROUP_TOPICS[group])
        ctx_line = ""
        if ctx.get("scenario_title"):
            ctx_line = f" for {ctx['scenario_title']}"
        return (
            f"I can definitely help with {label}{ctx_line} — I just need a bit more detail.\n\n"
            "What exactly are you seeing — the error message or the command that's failing? "
            "Common things I can walk you through:\n"
            f"{topics}\n\n"
            f"Or, for anything I can't solve, email {support}."
        )
    return (
        "I want to give you a precise answer — can you tell me a little more?\n\n"
        "For example: which technology (VMware, Linux, Kubernetes, Docker, networking) and the exact "
        "error or command that's failing.\n\n"
        "I can also help with platform topics: launching labs, subscriptions, interviews, certificates, "
        f"and contacts. For human help, email {support}."
    )


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def generate_support_reply(
    user_text: str,
    *,
    is_authenticated: bool = False,
    page_path: str = "",
    user=None,
) -> dict:
    """Return assistant reply with optional follow-up suggestions.

    The reply is chosen by scoring registered intents against the message and
    the (optional) active lab context. Falls back to a clarifying question that
    still offers the most relevant topics.
    """
    from apps.adminpanel.platform_config import get_settings_row

    row = get_settings_row()
    custom_faq = row.support_bot_custom_faq or []
    text = (user_text or "").strip()
    low = text.lower()
    support = _support_email()
    payment = _payment_email()
    delay = int(row.support_bot_typing_delay_ms or 1200)

    # Context: scenario/technology behind the current lab session, plus any
    # technology group implied by the user's own wording.
    ctx = resolve_lab_context(page_path, user=user)
    group = ctx.get("group") or _detect_group(text)

    # 1. Lab ticket *actions* still belong to the Jira team bots.
    if _is_jira_lab_question(text, page_path):
        return {
            "reply": JIRA_LAB_REDIRECT,
            "suggestions": ["How do I launch a lab?", "Who do I contact for help?"],
            "typing_delay_ms": delay,
        }

    # 2. Admin-defined custom FAQ overrides built-in intents.
    custom = _match_custom_faq(text, custom_faq)
    if custom:
        return {
            "reply": custom,
            "suggestions": _suggestions_for(text, group),
            "typing_delay_ms": delay,
        }

    # 3. Greeting / empty / generic help → welcome.
    if not text or low in ("hi", "hello", "hey", "help", "start") or any(
        low.startswith(g) for g in ("hi ", "hello ", "hey ", "help ")
    ):
        welcome = row.support_bot_welcome_message or DEFAULT_WELCOME
        if not is_authenticated:
            welcome += "\n\nSign in or create a free account from the top menu to launch labs and track progress."
        return {
            "reply": welcome,
            "suggestions": [t["prompt"] for t in (row.support_bot_quick_topics or DEFAULT_QUICK_TOPICS)[:4]],
            "typing_delay_ms": delay,
        }

    # 4. Score every intent; the best match wins.
    best = None
    best_score = 0.0
    for intent in _INTENTS:
        score = _score_intent(intent, low, group)
        if score > best_score:
            best_score = score
            best = intent

    if best is not None and best_score > 0:
        reply = best["build"](ctx, support=support, payment=payment)
    else:
        reply = _fallback_reply(text, group, support, ctx)

    # Strip markdown emphasis — the widget renders plain text.
    reply = re.sub(r"\*\*([^*]+)\*\*", r"\1", reply)

    return {
        "reply": reply,
        "suggestions": _suggestions_for(text, group),
        "typing_delay_ms": delay,
        "intent": best["name"] if (best and best_score > 0) else "fallback",
    }


def record_support_feedback(
    *, message: str, reply: str, helpful: bool, page_path: str = "", username: str = ""
) -> None:
    """Persist thumbs up/down feedback. Free: logged for later review, no API."""
    try:
        logger.info(
            "support_bot_feedback helpful=%s user=%s path=%s msg=%r",
            helpful,
            username or "anon",
            page_path,
            (message or "")[:200],
        )
    except Exception:  # pragma: no cover - never break the request on logging
        pass
