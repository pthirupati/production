"""ServiceNow-style ITSM vocabulary — ticket types, states, priorities, teams.

Kept in one module so the models, the team-action engine, the serializers and
the tests all agree on the canonical keys. The simulation never talks to a real
ServiceNow instance — these mirror the well-known OOTB values so the lab feels
authentic to anyone who has used the real product.
"""

from __future__ import annotations

# ── Ticket types (ServiceNow tables) ──────────────────────────────────────────
TYPE_INCIDENT = "incident"
TYPE_REQUEST = "request"          # sc_req_item / Service Request
TYPE_CHANGE = "change"            # change_request
TYPE_PROBLEM = "problem"

TICKET_TYPES = [
    (TYPE_INCIDENT, "Incident"),
    (TYPE_REQUEST, "Service Request"),
    (TYPE_CHANGE, "Change"),
    (TYPE_PROBLEM, "Problem"),
]

# Per-type record number prefix (ServiceNow: INC0001234, RITM..., CHG..., PRB...).
TYPE_PREFIX = {
    TYPE_INCIDENT: "INC",
    TYPE_REQUEST: "RITM",
    TYPE_CHANGE: "CHG",
    TYPE_PROBLEM: "PRB",
}

# ── States (ServiceNow incident state model) ──────────────────────────────────
STATE_NEW = "new"
STATE_IN_PROGRESS = "in_progress"
STATE_ON_HOLD = "on_hold"
STATE_RESOLVED = "resolved"
STATE_CLOSED = "closed"
STATE_CANCELLED = "cancelled"

TICKET_STATES = [
    (STATE_NEW, "New"),
    (STATE_IN_PROGRESS, "In Progress"),
    (STATE_ON_HOLD, "On Hold"),
    (STATE_RESOLVED, "Resolved"),
    (STATE_CLOSED, "Closed"),
    (STATE_CANCELLED, "Cancelled"),
]

# Allowed manual transitions (the engine may move tickets outside this when a
# team action auto-resolves a sub-ticket). Mirrors ServiceNow's forward flow.
ALLOWED_TRANSITIONS = {
    STATE_NEW: [STATE_IN_PROGRESS, STATE_ON_HOLD, STATE_CANCELLED],
    STATE_IN_PROGRESS: [STATE_ON_HOLD, STATE_RESOLVED, STATE_CANCELLED],
    STATE_ON_HOLD: [STATE_IN_PROGRESS, STATE_RESOLVED, STATE_CANCELLED],
    STATE_RESOLVED: [STATE_CLOSED, STATE_IN_PROGRESS],
    STATE_CLOSED: [],
    STATE_CANCELLED: [],
}

ACTIVE_STATES = {STATE_NEW, STATE_IN_PROGRESS, STATE_ON_HOLD}
TERMINAL_STATES = {STATE_CLOSED, STATE_CANCELLED}

# ── Priority (ServiceNow P1–P5) ───────────────────────────────────────────────
PRIORITY_CRITICAL = "1"
PRIORITY_HIGH = "2"
PRIORITY_MODERATE = "3"
PRIORITY_LOW = "4"
PRIORITY_PLANNING = "5"

PRIORITIES = [
    (PRIORITY_CRITICAL, "1 - Critical"),
    (PRIORITY_HIGH, "2 - High"),
    (PRIORITY_MODERATE, "3 - Moderate"),
    (PRIORITY_LOW, "4 - Low"),
    (PRIORITY_PLANNING, "5 - Planning"),
]

# SLA target in minutes per priority — drives the SLA timer / breach badge.
SLA_MINUTES = {
    PRIORITY_CRITICAL: 60,
    PRIORITY_HIGH: 240,
    PRIORITY_MODERATE: 480,
    PRIORITY_LOW: 1440,
    PRIORITY_PLANNING: 2880,
}

# ── Assignment groups / teams ─────────────────────────────────────────────────
# key → human label. A ticket is assigned to one team; sub-tickets are routed to
# another. The team-action engine (engine.py) maps a team + a request to a sim
# mutation (e.g. Storage → add a disk).
TEAM_SERVICE_DESK = "service_desk"
TEAM_STORAGE = "storage"
TEAM_BACKUP = "backup"
TEAM_NETWORK = "network"
TEAM_APP = "app"
TEAM_DATABASE = "database"
TEAM_SECURITY = "security"

TEAMS = [
    (TEAM_SERVICE_DESK, "Service Desk"),
    (TEAM_STORAGE, "Storage Team"),
    (TEAM_BACKUP, "Backup Team"),
    (TEAM_NETWORK, "Network Team"),
    (TEAM_APP, "App / Middleware Team"),
    (TEAM_DATABASE, "Database Team"),
    (TEAM_SECURITY, "Security Team"),
]

TEAM_LABELS = dict(TEAMS)

# ── Close codes (ServiceNow incident close_code) ──────────────────────────────
CLOSE_CODES = [
    ("solved_permanently", "Solved (Permanently)"),
    ("solved_workaround", "Solved (Workaround)"),
    ("solved_remote", "Solved Remotely"),
    ("not_solved", "Not Solved (Not Reproducible)"),
    ("closed_complete", "Closed/Complete"),
]


def team_label(key: str) -> str:
    return TEAM_LABELS.get(key, key.replace("_", " ").title() if key else "Unassigned")
