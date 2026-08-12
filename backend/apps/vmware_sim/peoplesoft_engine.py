"""
In-memory Oracle PeopleSoft (PIA) GUI simulator for training labs.

Models a realistic PeopleSoft PeopleTools world that a learner administers
through the PeopleSoft Internet Architecture (PIA) browser UI rather than a
terminal. The engine tracks:

  - portal      : PIA portal navigation — modules (Workforce Administration,
                  Financials, ...), components, and the menu/breadcrumb tree.
                  Components can require a permission/role to be accessible.
  - process     : Process Scheduler — process_runs[] each with an instance id,
                  process name, status (queued|running|success|error), and the
                  server (PSNT/PSUNX) it ran on.
  - security    : roles[], permission_lists[] (each granting components +
                  permissions), and users[] {oprid, roles, locked, ...}.
  - integration : Integration Broker — nodes[] {name, status active|down} and
                  services[] {name, active}.
  - migration   : Application Designer / Change Assistant — DEV/TEST/PROD
                  environments each with their own managed object definitions,
                  change projects built in DEV, and change packages that are
                  compared, applied along DEV -> TEST -> PROD, conflict on site
                  customisations, and can be rolled back out of an environment.

Each scenario preset puts this world into a clearly *broken* state (a process
run stuck in error, a user missing the role that unlocks a component, a
permission list missing a permission, a down IB node, a mis-set component
config, a locked operator account). The fix is exposed purely through
``apply_action`` (rerun_process / run_process, assign_role, add_permission /
add_role_to_permlist, restart_ib_node / activate_service, navigate +
set_component_config, unlock_user / reset_password). An unknown action or a
missing session always returns ``{"ok": False, "error": ...}`` and never raises.

``validate_peoplesoft_lab`` grades the lab by checking the broken state was
fixed via the intended PIA action. A fresh session always fails; only the
intended remediation flips it to pass.

Sessions live in the Django cache (Redis in production) for multi-worker
safety, mirroring the VMware / K8s / Docker / monitoring / nmap / windows
engines (SESSION_TTL=7200). Pure stdlib — no external/paid dependencies.
"""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from django.core.cache import cache

from .peoplesoft_v2_facades import apply_v2_action, ensure_v2

SESSION_TTL = 7200  # 2-hour TTL matching the other simulator engines


def _session_key(session_id: str) -> str:
    return f"peoplesoft_session:{session_id}"


def _load_session(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save_session(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _event(state: dict, message: str, severity: str = "info") -> None:
    state.setdefault("events", []).insert(0, {
        "time": _now_iso(), "message": message, "severity": severity,
    })
    state["events"] = state["events"][:40]


# Process Scheduler run statuses understood by the engine.
_RUN_STATUSES = ("queued", "running", "success", "error", "cancelled")
# Integration Broker node statuses.
_NODE_STATUSES = ("active", "down")


# ---------------------------------------------------------------------------
# Base PeopleSoft world (the "real" environment the learner administers).
# Presets clone this and break exactly one thing.
# ---------------------------------------------------------------------------

ENV_NAME = "HCM92DMO"
PEOPLETOOLS = "8.59.10"
APP_RELEASE = "PeopleSoft HCM 9.2 (Update Image 45)"


def _component(comp_id: str, name: str, *, menu: str, market: str = "GBL",
               require_permission: str = "", config: dict | None = None) -> dict:
    """A PIA component (a content page reachable from the menu tree).

    require_permission: the permission key a user's roles must grant (via a
    permission list) to open the component. Empty => publicly reachable.
    """
    return {
        "id": comp_id,
        "name": name,
        "menu": menu,
        "market": market,
        "require_permission": require_permission,
        "config": dict(config or {}),
    }


def _module(mod_id: str, name: str, components: list[dict]) -> dict:
    return {"id": mod_id, "name": name, "components": components}


def _process_run(instance: int, name: str, status: str, *, server: str = "PSUNX",
                 process_type: str = "Application Engine", run_control: str = "",
                 distribution: str = "", message: str = "") -> dict:
    return {
        "instance": instance,
        "name": name,
        "process_type": process_type,
        "status": status if status in _RUN_STATUSES else "queued",
        "server": server,
        "run_control": run_control or name.lower(),
        "distribution": distribution or ("Posted" if status == "success" else "N/A"),
        "message": message,
        "run_datetime": _now_iso(),
    }


def _perm_list(pl_id: str, name: str, *, permissions: list[str],
               components: list[str] | None = None, description: str = "") -> dict:
    return {
        "id": pl_id,
        "name": name,
        "description": description,
        "permissions": list(permissions),
        "components": list(components or []),
    }


def _role(role_id: str, name: str, *, permission_lists: list[str], description: str = "") -> dict:
    return {
        "id": role_id,
        "name": name,
        "description": description,
        "permission_lists": list(permission_lists),
    }


def _user(oprid: str, *, name: str, roles: list[str], locked: bool = False,
          enabled: bool = True, email: str = "", failed_logins: int = 0) -> dict:
    return {
        "oprid": oprid,
        "name": name,
        "roles": list(roles),
        "locked": bool(locked),
        "enabled": bool(enabled),
        "email": email or f"{oprid.lower()}@fixitlab.example",
        "failed_logins": int(failed_logins),
    }


def _ib_node(name: str, status: str, *, node_type: str = "PIA", default_user: str = "PS") -> dict:
    return {
        "name": name,
        "status": status if status in _NODE_STATUSES else "active",
        "node_type": node_type,
        "default_user": default_user,
    }


def _ib_service(name: str, *, active: bool = True, operations: list[str] | None = None) -> dict:
    return {
        "name": name,
        "active": bool(active),
        "operations": list(operations or []),
    }


# ---------------------------------------------------------------------------
# Application Designer / Change Assistant — the DEV -> TEST -> PROD migration
# lifecycle. This is a *sibling* of portal/process/security/integration under
# world["migration"]; the flat top-level world shape the existing ~150 labs and
# their checkers read (world["portal"]["modules"], world["security"], ...) is
# deliberately left untouched.
#
# Model:
#   environments[] : DEV / TEST / PROD, each holding its OWN objects{} map of
#                    definition name -> {version, body, customised}. Objects are
#                    always copied by VALUE on promotion (see _copy_object), so
#                    applying to TEST can never alias into PROD.
#   projects[]     : App Designer change projects built in DEV — a list of
#                    object names plus the DEV version captured at build time.
#   packages[]     : Change Assistant change packages cut from a project. Each
#                    carries the frozen payload (name -> object snapshot) and an
#                    apply history so a bad patch can be rolled back.
# ---------------------------------------------------------------------------

# Ordered promotion path. A package must be applied to each environment in turn;
# skipping straight from DEV to PROD is rejected the way Change Assistant does.
_ENV_ORDER = ("DEV", "TEST", "PROD")
# Change package lifecycle states.
_PKG_STATUSES = ("built", "applied", "rolled_back")


def _ps_object(name: str, *, version: int = 1, body: str = "",
               customised: bool = False, obj_type: str = "Page") -> dict:
    """One App Designer managed definition (Record / Page / PeopleCode / ...).

    customised: True marks a site-local change made directly in an environment.
    A promotion landing on a customised object is a *conflict* and is refused
    until the learner resolves it (keep-customisation or accept-vendor).
    """
    return {
        "name": name,
        "type": obj_type,
        "version": int(version),
        "body": body or f"-- {name} definition v{version}",
        "customised": bool(customised),
    }


def _copy_object(obj: dict) -> dict:
    """Deep-ish copy of a managed object.

    Promotion MUST copy by value: an object dict shared between two
    environments would make a TEST apply silently mutate PROD and make a
    rollback appear to succeed while leaving PROD dirty.
    """
    return copy.deepcopy(obj)


def _environment(name: str, objects: list[dict]) -> dict:
    return {
        "name": name,
        "objects": {o["name"]: _copy_object(o) for o in objects},
        "last_applied_package": "",
    }


def _base_migration() -> dict:
    """Three environments seeded to a consistent, already-promoted baseline."""
    baseline = [
        _ps_object("PSU_JOB_DATA_PAGE", version=3, obj_type="Page"),
        _ps_object("PSU_EXPENSE_AE", version=2, obj_type="App Engine"),
        _ps_object("PSU_VOUCHER_REC", version=5, obj_type="Record"),
    ]
    return {
        "environments": [
            _environment("DEV", baseline),
            _environment("TEST", baseline),
            _environment("PROD", baseline),
        ],
        "projects": [],
        "packages": [],
        "next_package_seq": 1,
    }


# ---------------------------------------------------------------------------
# Employee Self-Service (ESS) records — the Fluid self-service pages read these
# keyed off the signed-in operator's OPRID. Each operator maps 1:1 to an
# EMPLID with Job Data, an open-enrollment Benefits event, and a paycheck.
# ---------------------------------------------------------------------------

# Health plans available in the open-enrollment catalog (Benefits eBenefits).
def _health_plan(plan_id: str, name: str, *, deductible: str, oop: str, premium: str) -> dict:
    return {"id": plan_id, "name": name, "deductible": deductible, "oop": oop, "premium": premium}


_BENEFITS_STEPS = [
    {"key": "personal", "label": "Personal Information"},
    {"key": "health", "label": "Health Benefits"},
    {"key": "life", "label": "Life and AD&D"},
    {"key": "disability", "label": "Disability"},
    {"key": "savings", "label": "Savings"},
    {"key": "review", "label": "Review and Submit"},
]


def _ss_profile(oprid: str, *, empl_id: str, name: str, job: dict,
                paycheck: dict, benefits: dict) -> dict:
    """A self-service record for one operator (OPRID -> EMPLID)."""
    return {
        "oprid": oprid,
        "empl_id": empl_id,
        "name": name,
        "job": dict(job),
        "paycheck": dict(paycheck),
        "benefits": dict(benefits),
    }


def _base_self_service() -> dict:
    """ESS records keyed by OPRID. Presets/actions mutate these in place."""
    return {
        "benefit_plans": [
            _health_plan("ppo", "PPO Select", deductible="$1,500", oop="$6,000", premium="$142/mo"),
            _health_plan("hdhp", "HDHP + HSA", deductible="$3,000", oop="$7,500", premium="$98/mo"),
            _health_plan("hmo", "HMO Classic", deductible="$500", oop="$4,000", premium="$165/mo"),
        ],
        "benefit_steps": [dict(s) for s in _BENEFITS_STEPS],
        "profiles": {
            "PS": _ss_profile(
                "PS", empl_id="00000001", name="PeopleSoft Super User",
                job={
                    "company": "FIXIT", "business_unit": "CORP", "department": "IT Security",
                    "location": "Bengaluru", "job_code": "SYSADMIN", "job_title": "Systems Administrator",
                    "reports_to": "IT Director", "fte": "1.0", "pay_group": "MONTHLY",
                    "tax_location": "IN-BLR", "pay_frequency": "Semi-monthly", "salary_plan": "IND-IT-01",
                    "grade": "G13", "comp_rate": "₹96,000/mo", "benefits_program": "FIXIT-IND",
                    "status": "Active", "hire_date": "2020-01-06", "service_date": "2020-01-06",
                    "reg_temp": "Regular", "effective_date": "2020-01-06",
                },
                paycheck=_paycheck_defaults(net=3620.15, ytd=48210.0),
                benefits=_benefits_defaults(elected="ppo"),
            ),
            "HCMADMIN": _ss_profile(
                "HCMADMIN", empl_id="00001234", name="HCM Admin",
                job={
                    "company": "FIXIT", "business_unit": "ITOPS", "department": "Infrastructure",
                    "location": "Hyderabad", "job_code": "HRADMIN", "job_title": "HCM Administrator",
                    "reports_to": "HR Director", "fte": "1.0", "pay_group": "MONTHLY",
                    "tax_location": "IN-HYD", "pay_frequency": "Semi-monthly", "salary_plan": "IND-HR-01",
                    "grade": "G12", "comp_rate": "₹85,000/mo", "benefits_program": "FIXIT-IND",
                    "status": "Active", "hire_date": "2022-03-15", "service_date": "2022-03-15",
                    "reg_temp": "Regular", "effective_date": "2026-01-01",
                },
                paycheck=_paycheck_defaults(net=3432.25, ytd=41287.5),
                benefits=_benefits_defaults(elected="ppo"),
            ),
            "FINUSER": _ss_profile(
                "FINUSER", empl_id="00002468", name="Finance User",
                job={
                    "company": "FIXIT", "business_unit": "FIN", "department": "Accounts Payable",
                    "location": "Pune", "job_code": "APCLERK", "job_title": "AP Analyst",
                    "reports_to": "Controller", "fte": "1.0", "pay_group": "BIWEEKLY",
                    "tax_location": "IN-PUN", "pay_frequency": "Bi-weekly", "salary_plan": "IND-FIN-01",
                    "grade": "G10", "comp_rate": "₹68,000/mo", "benefits_program": "FIXIT-IND",
                    "status": "Active", "hire_date": "2023-07-01", "service_date": "2023-07-01",
                    "reg_temp": "Regular", "effective_date": "2026-01-01",
                },
                paycheck=_paycheck_defaults(net=2810.0, ytd=33720.0),
                benefits=_benefits_defaults(elected="hmo"),
            ),
        },
    }


def _paycheck_defaults(*, net: float, ytd: float) -> dict:
    return {
        "company": "FixitLab India Pvt Ltd",
        "period_start": "2026-06-01",
        "period_end": "2026-06-15",
        "pay_date": "2026-06-20",
        "earnings": [
            {"type": "Regular Pay", "hours": 80, "amount": 4250.0},
            {"type": "Overtime", "hours": 4, "amount": 318.75},
        ],
        "taxes": [
            {"type": "Federal Income Tax", "amount": -612.0},
            {"type": "State Income Tax", "amount": -198.5},
        ],
        "deductions": [
            {"type": "401(k)", "amount": -255.0},
            {"type": "Medical PPO", "amount": -71.0},
        ],
        "net_pay": net,
        "ytd_net": ytd,
        "deposit": "HDFC ****4821",
    }


def _benefits_defaults(*, elected: str) -> dict:
    return {
        "event": "Open Enrollment",
        "event_status": "Open",       # Open | Submitted
        "elected_plan": elected,       # currently elected health plan id
        "submitted_plan": "",          # plan id captured at submit time
        "submitted_at": "",
    }


def _find_profile(world: dict, oprid: str) -> dict | None:
    """Self-service record for an OPRID, falling back to the PS super user."""
    ss = world.get("self_service") or {}
    profiles = ss.get("profiles") or {}
    uid = (oprid or "").strip()
    if uid and uid in profiles:
        return profiles[uid]
    # case-insensitive match
    for key, prof in profiles.items():
        if key.lower() == uid.lower():
            return prof
    return None


def _base_world() -> dict:
    """The realistic base PeopleSoft environment used by every scenario."""
    return {
        "env": {
            "name": ENV_NAME,
            "peopletools": PEOPLETOOLS,
            "app_release": APP_RELEASE,
            "database": "Oracle 19c (PSHCM)",
            "web_server": "Oracle WebLogic 12.2.1",
            "app_server": "PSAPPSRV (domain HCM92)",
        },
        "session": {"logged_in": False, "oprid": "PS"},
        # PIA portal: modules -> components, plus the current breadcrumb path.
        "portal": {
            "current_path": [],          # list of breadcrumb labels
            "current_component": None,    # component id currently open
            "modules": [
                _module("wfa", "Workforce Administration", [
                    _component("job_data", "Job Data", menu="Administer Workforce",
                               require_permission="HC_JOB_DATA"),
                    _component("personal_data", "Personal Data", menu="Administer Workforce",
                               require_permission=""),
                    _component("position_data", "Position Data", menu="Manage Positions",
                               require_permission="HC_POSITION_DATA",
                               config={"auto_create_position": "Y", "max_head_count": 1}),
                ]),
                _module("fin", "Financials", [
                    _component("voucher_entry", "Voucher Entry", menu="Accounts Payable",
                               require_permission="FIN_AP_VOUCHER"),
                    _component("journal_entry", "Journal Entry", menu="General Ledger",
                               require_permission=""),
                ]),
                _module("peopletools", "PeopleTools", [
                    _component("process_monitor", "Process Monitor", menu="Process Scheduler",
                               require_permission=""),
                    _component("security_users", "User Profiles", menu="Security",
                               require_permission=""),
                    _component("ib_nodes", "Integration Broker Nodes", menu="Integration Broker",
                               require_permission=""),
                ]),
            ],
        },
        # Process Scheduler.
        "process": {
            "servers": [
                {"name": "PSUNX", "status": "up", "os": "Linux"},
                {"name": "PSNT", "status": "up", "os": "Windows"},
            ],
            "next_instance": 1010,
            "runs": [
                _process_run(1001, "PAYROLL_CALC", "success", server="PSUNX",
                             run_control="payroll_biweekly"),
                _process_run(1002, "GL_JOURNAL_POST", "success", server="PSUNX",
                             run_control="gl_post"),
                _process_run(1003, "XRFWIN", "success", server="PSNT",
                             process_type="SQR Report", run_control="xref"),
            ],
        },
        # Security.
        "security": {
            "permission_lists": [
                _perm_list("HCSPPALL", "HCSPPALL", permissions=["HC_JOB_DATA", "HC_PERSONAL_DATA"],
                           components=["job_data", "personal_data"],
                           description="HCM core self-service + admin"),
                _perm_list("HCCPPRM", "HCCPPRM", permissions=["HC_POSITION_DATA"],
                           components=["position_data"], description="Position management"),
                _perm_list("EPFP1000", "EPFP1000", permissions=["FIN_GL_JOURNAL"],
                           components=["journal_entry"], description="Financials GL"),
                _perm_list("PTPT1000", "PTPT1000",
                           permissions=["PT_PROCESS_MONITOR", "PT_SECURITY", "PT_IB"],
                           components=["process_monitor", "security_users", "ib_nodes"],
                           description="PeopleTools administration"),
            ],
            "roles": [
                _role("HC_ADMIN", "HCM Administrator",
                      permission_lists=["HCSPPALL", "HCCPPRM"],
                      description="Full HCM administration"),
                _role("FIN_ANALYST", "Financials Analyst",
                      permission_lists=["EPFP1000"], description="GL + AP analyst"),
                _role("PT_ADMIN", "PeopleTools Administrator",
                      permission_lists=["PTPT1000"], description="PeopleTools/security admin"),
            ],
            "users": [
                _user("PS", name="PeopleSoft Super User",
                      roles=["HC_ADMIN", "FIN_ANALYST", "PT_ADMIN"]),
                _user("HCMADMIN", name="HCM Admin", roles=["HC_ADMIN"]),
                _user("FINUSER", name="Finance User", roles=["FIN_ANALYST"]),
            ],
        },
        # Integration Broker.
        "integration": {
            "nodes": [
                _ib_node("PSFT_HR", "active"),
                _ib_node("PSFT_EP", "active"),
                _ib_node("QE_LOCAL", "active", node_type="PIA"),
            ],
            "services": [
                _ib_service("PERSON_BASIC_SYNC", active=True,
                            operations=["PERSON_BASIC_SYNC.VERSION_3"]),
                _ib_service("ROLESYNCHRONIZATION", active=True,
                            operations=["ROLESYNCHRONIZATION.VERSION_1"]),
                _ib_service("USER_PROFILE", active=True,
                            operations=["USER_PROFILE.VERSION_84"]),
            ],
        },
        # Employee Self-Service (Fluid pages) — records keyed by OPRID.
        "self_service": _base_self_service(),
        # App Designer / Change Assistant migration lifecycle. Sibling key —
        # the flat shape above is unchanged so existing checkers keep working.
        "migration": _base_migration(),
        "events": [],
    }


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------

def _find_component(world: dict, comp_id: str) -> dict | None:
    cid = (comp_id or "").strip()
    if not cid:
        return None
    for mod in world["portal"]["modules"]:
        for comp in mod["components"]:
            if comp["id"] == cid or comp["name"].lower() == cid.lower():
                return comp
    return None


def _find_module_for_component(world: dict, comp_id: str) -> dict | None:
    for mod in world["portal"]["modules"]:
        for comp in mod["components"]:
            if comp["id"] == comp_id:
                return mod
    return None


def _find_run(world: dict, instance: Any) -> dict | None:
    try:
        inst = int(instance)
    except (TypeError, ValueError):
        return None
    for run in world["process"]["runs"]:
        if run["instance"] == inst:
            return run
    return None


def _find_role(world: dict, role_id: str) -> dict | None:
    rid = (role_id or "").strip()
    if not rid:
        return None
    for role in world["security"]["roles"]:
        if role["id"] == rid or role["name"].lower() == rid.lower():
            return role
    return None


def _find_perm_list(world: dict, pl_id: str) -> dict | None:
    pid = (pl_id or "").strip()
    if not pid:
        return None
    for pl in world["security"]["permission_lists"]:
        if pl["id"] == pid or pl["name"].lower() == pid.lower():
            return pl
    return None


def _find_user(world: dict, oprid: str) -> dict | None:
    uid = (oprid or "").strip()
    if not uid:
        return None
    for user in world["security"]["users"]:
        if user["oprid"].lower() == uid.lower() or user["name"].lower() == uid.lower():
            return user
    return None


def _find_node(world: dict, name: str) -> dict | None:
    nm = (name or "").strip()
    if not nm:
        return None
    for node in world["integration"]["nodes"]:
        if node["name"].lower() == nm.lower():
            return node
    return None


def _find_service(world: dict, name: str) -> dict | None:
    nm = (name or "").strip()
    if not nm:
        return None
    for svc in world["integration"]["services"]:
        if svc["name"].lower() == nm.lower():
            return svc
    return None


def _migration(world: dict) -> dict:
    """Migration sub-world, self-healing for sessions cached before it existed."""
    mig = world.get("migration")
    if not isinstance(mig, dict) or "environments" not in mig:
        mig = _base_migration()
        world["migration"] = mig
    return mig


def _find_env(world: dict, name: str) -> dict | None:
    nm = (name or "").strip().upper()
    if not nm:
        return None
    for env in _migration(world)["environments"]:
        if env["name"] == nm:
            return env
    return None


def _find_project(world: dict, name: str) -> dict | None:
    nm = (name or "").strip()
    if not nm:
        return None
    for proj in _migration(world)["projects"]:
        if proj["name"].lower() == nm.lower():
            return proj
    return None


def _find_package(world: dict, pkg_id: str) -> dict | None:
    pid = (pkg_id or "").strip()
    if not pid:
        return None
    for pkg in _migration(world)["packages"]:
        if pkg["id"].lower() == pid.lower():
            return pkg
    return None


def _compare_report(world: dict, source: str, target: str,
                    object_names: list[str] | None = None) -> dict:
    """App Designer compare report: source env definitions vs target env.

    Mirrors the real compare's per-object outcomes:
      absent          — target has no such object (new definition)
      upgrade         — source is a newer version than target
      same            — identical version
      customisation   — target version was changed locally (customised flag);
                        promoting would overwrite site-local work.
    """
    src = _find_env(world, source)
    tgt = _find_env(world, target)
    if not src or not tgt:
        return {}
    names = list(object_names) if object_names else sorted(src["objects"])
    rows = []
    for name in names:
        s_obj = src["objects"].get(name)
        if not s_obj:
            continue
        t_obj = tgt["objects"].get(name)
        if t_obj is None:
            outcome = "absent"
        elif t_obj.get("customised"):
            outcome = "customisation"
        elif s_obj["version"] > t_obj["version"]:
            outcome = "upgrade"
        elif s_obj["version"] == t_obj["version"]:
            outcome = "same"
        else:
            outcome = "target_newer"
        rows.append({
            "object": name,
            "type": s_obj.get("type", "Page"),
            "source_version": s_obj["version"],
            "target_version": (t_obj or {}).get("version"),
            "target_customised": bool((t_obj or {}).get("customised")),
            "action": outcome,
        })
    return {
        "source": src["name"],
        "target": tgt["name"],
        "generated_at": _now_iso(),
        "rows": rows,
        "conflicts": [r["object"] for r in rows if r["action"] == "customisation"],
    }


def _user_permissions(world: dict, user: dict) -> set[str]:
    """All permission keys a user holds, resolved role -> permission list."""
    perms: set[str] = set()
    pl_by_id = {pl["id"]: pl for pl in world["security"]["permission_lists"]}
    for role_id in user.get("roles", []):
        role = _find_role(world, role_id)
        if not role:
            continue
        for pl_id in role.get("permission_lists", []):
            pl = pl_by_id.get(pl_id) or _find_perm_list(world, pl_id)
            if pl:
                perms.update(pl.get("permissions", []))
    return perms


def _current_user(world: dict) -> dict | None:
    return _find_user(world, world.get("session", {}).get("oprid") or "PS")


def _enqueue_run(world: dict, state: dict, name: str, *, status: str = "queued",
                 server: str = "PSUNX", process_type: str = "Application Engine",
                 run_control: str = "", message: str = "") -> dict:
    """Enqueue a Process Scheduler run (self-service submissions land here).

    Reuses the existing process.runs model + next_instance counter so the
    Process Monitor and the rerun/cancel plumbing pick the new run up
    automatically. Returns the created run dict.
    """
    proc = world["process"]
    inst = proc["next_instance"]
    proc["next_instance"] = inst + 1
    run = _process_run(inst, name, status, server=server, process_type=process_type,
                       run_control=run_control or name.lower(), message=message)
    # Stamp a wall-clock epoch so non-terminal runs can advance queued ->
    # running -> success over real time in get_state (see _advance_lifecycle).
    if run["status"] in ("queued", "running"):
        run["enqueued_epoch"] = time.time()
    proc["runs"].insert(0, run)
    return run


# Wall-clock lifecycle thresholds (seconds) for self-service background jobs.
_RUN_TO_RUNNING_S = 4
_RUN_TO_SUCCESS_S = 9


def _advance_lifecycle(world: dict) -> bool:
    """Advance queued/running Process Scheduler runs on wall-clock time.

    Self-service submissions enqueue runs; over real elapsed time they move
    queued -> running -> success so the Process Monitor updates without any
    extra learner action. Returns True if any run changed (so the caller can
    persist). Runs without an enqueued_epoch (the preset's broken 'error' run,
    or already-terminal seed data) are left untouched.
    """
    changed = False
    now = time.time()
    for run in world.get("process", {}).get("runs", []):
        if run.get("status") not in ("queued", "running"):
            continue
        epoch = run.get("enqueued_epoch")
        if epoch is None:
            continue
        elapsed = now - float(epoch)
        if elapsed >= _RUN_TO_SUCCESS_S and run["status"] != "success":
            run["status"] = "success"
            run["distribution"] = "Posted"
            run["message"] = ""
            run["run_datetime"] = _now_iso()
            run.pop("enqueued_epoch", None)
            changed = True
        elif elapsed >= _RUN_TO_RUNNING_S and run["status"] == "queued":
            run["status"] = "running"
            changed = True
    return changed


# ---------------------------------------------------------------------------
# Scenario presets — break exactly one thing + attach a validation goal.
# Validation reads only `goal` + current world state.
# ---------------------------------------------------------------------------

def _apply_preset(state: dict, slug: str) -> None:
    world = state["world"]
    s = (slug or "").lower()

    # 1. Rerun a failed Process Scheduler job.
    if "rerun" in s or "process-error" in s or "failed-process" in s or "scheduler" in s:
        world["process"]["runs"].insert(0, _process_run(
            1009, "GL_JOURNAL_POST", "error", server="PSUNX", run_control="gl_post_jun",
            message="Process terminated abnormally — see message log (SQL error / locked table)."))
        state["goal"] = {
            "kind": "process_success",
            "title": "Rerun the failed GL_JOURNAL_POST process",
            "target_instance": 1009,
            "target_process": "GL_JOURNAL_POST",
            "objective": ("In Process Monitor, the GL_JOURNAL_POST run (instance 1009) ended in "
                          "Error. Rerun it from the Process Scheduler so it completes Successfully."),
        }
        return

    # 2. Grant a user the missing role to access a component.
    if "grant-role" in s or "missing-role" in s or "role-access" in s or "component-access" in s:
        user = _find_user(world, "FINUSER")
        # FINUSER has only FIN_ANALYST -> cannot open Voucher Entry (needs FIN_AP_VOUCHER).
        # Make Voucher Entry require AP voucher permission, held only by an AP role.
        world["security"]["permission_lists"].append(_perm_list(
            "EPAP1000", "EPAP1000", permissions=["FIN_AP_VOUCHER"],
            components=["voucher_entry"], description="Accounts Payable voucher entry"))
        world["security"]["roles"].append(_role(
            "AP_PROCESSOR", "Accounts Payable Processor",
            permission_lists=["EPAP1000"], description="Enter and process AP vouchers"))
        state["goal"] = {
            "kind": "user_can_access",
            "title": "Grant FINUSER access to Voucher Entry",
            "target_user": "FINUSER",
            "target_component": "voucher_entry",
            "require_role": "AP_PROCESSOR",
            "objective": ("FINUSER cannot open the Voucher Entry component (Accounts Payable). "
                          "Assign the AP_PROCESSOR role to FINUSER in User Profiles so the "
                          "FIN_AP_VOUCHER permission unlocks the component."),
        }
        return

    # 3. Add a missing permission to a permission list.
    if "permission-list" in s or "add-permission" in s or "missing-permission" in s or "permlist" in s:
        # HCMADMIN holds HC_ADMIN -> HCSPPALL + HCCPPRM. Remove HC_POSITION_DATA from
        # HCCPPRM so Position Data becomes inaccessible until the permission is re-added.
        pl = _find_perm_list(world, "HCCPPRM")
        if pl and "HC_POSITION_DATA" in pl["permissions"]:
            pl["permissions"].remove("HC_POSITION_DATA")
        state["goal"] = {
            "kind": "permlist_has_permission",
            "title": "Restore the HC_POSITION_DATA permission to HCCPPRM",
            "target_permlist": "HCCPPRM",
            "require_permission": "HC_POSITION_DATA",
            "verify_component": "position_data",
            "objective": ("The HCCPPRM permission list is missing the HC_POSITION_DATA "
                          "permission, so Position Data no longer opens for HCM admins. "
                          "Add HC_POSITION_DATA back to the HCCPPRM permission list."),
        }
        return

    # 4. Bring a down Integration Broker node back active.
    if "ib-node" in s or "integration-broker" in s or "node-down" in s or "ib-down" in s:
        node = _find_node(world, "PSFT_HR")
        if node:
            node["status"] = "down"
        state["goal"] = {
            "kind": "ib_node_active",
            "title": "Bring the PSFT_HR Integration Broker node back online",
            "target_node": "PSFT_HR",
            "objective": ("The PSFT_HR Integration Broker node is Down, so HR message "
                          "publish/subscribe is failing. Restart/Ping the node from the "
                          "Integration Broker Nodes page to bring it Active."),
        }
        return

    # 5. Navigate to + correct a component config.
    if "component-config" in s or "config" in s or "auto-create" in s or "correct-config" in s:
        comp = _find_component(world, "position_data")
        if comp:
            # A bad config blocks new hires from creating positions.
            comp["config"]["auto_create_position"] = "N"
            comp["config"]["max_head_count"] = 0
        state["goal"] = {
            "kind": "component_config",
            "title": "Correct the Position Data component configuration",
            "target_component": "position_data",
            "require_config": {"auto_create_position": "Y", "max_head_count": 1},
            "require_navigated": True,
            "objective": ("Position Data is misconfigured (auto_create_position=N, "
                          "max_head_count=0), blocking new positions. Navigate to the "
                          "Position Data component and set auto_create_position=Y and "
                          "max_head_count to at least 1."),
        }
        return

    # 6. Reset a locked operator account.
    if "locked-account" in s or "unlock" in s or "reset-password" in s or "operator-account" in s or "account-lock" in s:
        user = _find_user(world, "HCMADMIN")
        if user:
            user["locked"] = True
            user["failed_logins"] = 6
        state["goal"] = {
            "kind": "user_unlocked",
            "title": "Reset the locked HCMADMIN operator account",
            "target_user": "HCMADMIN",
            "objective": ("The HCMADMIN operator account is locked after repeated failed "
                          "sign-ins. Unlock the account (Account Locked Out = N) in User "
                          "Profiles so the administrator can sign in again."),
        }
        return

    # 7. Promote a fix DEV -> TEST -> PROD through Change Assistant, working
    #    around a site customisation that TEST made to one of the objects.
    #    Excludes the rollback keywords so a "back-out-change-package" slug
    #    lands on the rollback lab below rather than here.
    if (("promote" in s or "migration" in s or "change-package" in s
         or "change-assistant" in s)
            and not ("rollback" in s or "bad-patch" in s or "back-out" in s)):
        mig = _migration(world)
        dev = _find_env(world, "DEV")
        test = _find_env(world, "TEST")
        # DEV holds the fix; TEST customised the same page locally, so the
        # compare report will flag a conflict the learner has to resolve.
        dev["objects"]["PSU_EXPENSE_AE"]["version"] = 3
        dev["objects"]["PSU_EXPENSE_AE"]["body"] = (
            "-- PSU_EXPENSE_AE v3: fixes the duplicate-reimbursement defect")
        test["objects"]["PSU_JOB_DATA_PAGE"]["customised"] = True
        test["objects"]["PSU_JOB_DATA_PAGE"]["version"] = 4
        state["goal"] = {
            "kind": "package_promoted",
            "title": "Promote the expense fix from DEV to PROD",
            "target_objects": ["PSU_EXPENSE_AE"],
            "require_version": {"PSU_EXPENSE_AE": 3},
            "require_environments": ["TEST", "PROD"],
            "protect_customisation": {"TEST": ["PSU_JOB_DATA_PAGE"]},
            "objective": (
                "The PSU_EXPENSE_AE fix (version 3) is finished in DEV but PROD is still "
                "running version 2. Build an Application Designer change project over "
                "PSU_EXPENSE_AE, cut a Change Assistant package, run a compare report, and "
                "apply it to TEST and then PROD. TEST has a local customisation of "
                "PSU_JOB_DATA_PAGE that must survive the promotion."),
        }
        return

    # 8. Back a bad change package out of PROD.
    if "bad-patch" in s or "rollback" in s or "back-out" in s:
        mig = _migration(world)
        prod = _find_env(world, "PROD")
        dev = _find_env(world, "DEV")
        # A regression shipped: PROD is running v9 of the voucher record, which
        # broke AP. The pre-patch definition (v5) is captured in the package
        # history so a rollback restores it exactly.
        bad = _ps_object("PSU_VOUCHER_REC", version=9, obj_type="Record",
                         body="-- PSU_VOUCHER_REC v9: regression — drops the vendor key")
        dev["objects"]["PSU_VOUCHER_REC"] = _copy_object(bad)
        before = {"PSU_VOUCHER_REC": _copy_object(prod["objects"]["PSU_VOUCHER_REC"])}
        prod["objects"]["PSU_VOUCHER_REC"] = _copy_object(bad)
        prod["last_applied_package"] = "CP-014"
        mig["packages"].append({
            "id": "CP-014",
            "project": "PSU_AP_HOTFIX",
            "source": "DEV",
            "status": "applied",
            "created_at": _now_iso(),
            "payload": {"PSU_VOUCHER_REC": _copy_object(bad)},
            "applied_to": ["TEST", "PROD"],
            "history": [
                {"environment": "TEST", "action": "apply", "at": _now_iso(),
                 "before": {"PSU_VOUCHER_REC": _copy_object(before["PSU_VOUCHER_REC"])},
                 "objects": ["PSU_VOUCHER_REC"]},
                {"environment": "PROD", "action": "apply", "at": _now_iso(),
                 "before": before, "objects": ["PSU_VOUCHER_REC"]},
            ],
        })
        state["goal"] = {
            "kind": "package_rolled_back",
            "title": "Roll change package CP-014 out of PROD",
            "target_package": "CP-014",
            "target_environment": "PROD",
            "target_objects": ["PSU_VOUCHER_REC"],
            "restore_version": {"PSU_VOUCHER_REC": 5},
            "objective": (
                "Change package CP-014 shipped a regression: PSU_VOUCHER_REC version 9 "
                "drops the vendor key and Accounts Payable is failing in PROD. Roll CP-014 "
                "back out of PROD in Change Assistant so PROD returns to version 5."),
        }
        return

    # Default goal so an unrecognised slug still presents a real task.
    world["process"]["runs"].insert(0, _process_run(
        1009, "GL_JOURNAL_POST", "error", server="PSUNX", run_control="gl_post_default",
        message="Process terminated abnormally."))
    state["goal"] = {
        "kind": "process_success",
        "title": "Rerun the failed process",
        "target_instance": 1009,
        "target_process": "GL_JOURNAL_POST",
        "objective": "A Process Scheduler run ended in Error — rerun it so it completes Successfully.",
    }


# ---------------------------------------------------------------------------
# Session lifecycle (mirrors the other engines)
# ---------------------------------------------------------------------------

def _ensure_session(session_id: str, scenario_slug: str = "") -> dict:
    key = str(session_id)
    entry = _load_session(key)
    if entry is None:
        state = {"world": _base_world()}
        _apply_preset(state, scenario_slug)
        entry = {"session_id": key, "scenario_slug": scenario_slug, "state": state,
                 "created_at": _now_iso()}
        _save_session(key, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure_session(session_id, scenario_slug)
    ensure_v2(entry["state"]["world"])
    # Advance any queued/running self-service jobs on wall-clock, then persist
    # so the Process Monitor reflects the progression across polls/workers.
    _advance_lifecycle(entry["state"]["world"])
    _save_session(str(session_id), entry)
    state = copy.deepcopy(entry["state"])
    world = state["world"]
    goal = state.get("goal", {})

    proc = world["process"]
    sec = world["security"]
    integ = world["integration"]

    # Derive the access map for the currently signed-in operator so the UI can
    # show which components the menu tree should grey-out (locked).
    current = _current_user(world)
    held = _user_permissions(world, current) if current else set()
    accessible: dict[str, bool] = {}
    for mod in world["portal"]["modules"]:
        for comp in mod["components"]:
            req = comp.get("require_permission")
            accessible[comp["id"]] = (not req) or (req in held)

    # Self-service record for the signed-in operator (Fluid pages read this).
    current_oprid = world["session"].get("oprid", "PS")
    ess_profile = _find_profile(world, current_oprid)

    mig = _migration(world)

    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "inventory": world,
        "v2": world.get("v2", {}),
        "goal": goal,
        "events": world.get("events", []),
        "access": accessible,
        # Self-service record for the signed-in operator (Fluid pages read this).
        "ess_profile": ess_profile,
        # App Designer / Change Assistant lifecycle state + the last compare run.
        "migration": mig,
        "compare_report": state.get("last_compare"),
        "summary": {
            "env": world["env"]["name"],
            "peopletools": world["env"]["peopletools"],
            "logged_in": world["session"].get("logged_in", False),
            "current_oprid": current_oprid,
            "current_component": world["portal"].get("current_component"),
            "breadcrumb": world["portal"].get("current_path", []),
            "modules_total": len(world["portal"]["modules"]),
            "components_total": sum(len(m["components"]) for m in world["portal"]["modules"]),
            "process_runs_total": len(proc["runs"]),
            "process_runs_error": sum(1 for r in proc["runs"] if r["status"] == "error"),
            "process_runs_success": sum(1 for r in proc["runs"] if r["status"] == "success"),
            "process_runs_running": sum(1 for r in proc["runs"] if r["status"] in ("queued", "running")),
            "roles_total": len(sec["roles"]),
            "permission_lists_total": len(sec["permission_lists"]),
            "users_total": len(sec["users"]),
            "users_locked": sum(1 for u in sec["users"] if u.get("locked")),
            "ib_nodes_total": len(integ["nodes"]),
            "ib_nodes_down": sum(1 for n in integ["nodes"] if n["status"] == "down"),
            "ib_services_inactive": sum(1 for sv in integ["services"] if not sv.get("active")),
            "goal_title": goal.get("title", ""),
            "objective": goal.get("objective", ""),
            "queries": len((world.get("v2") or {}).get("queries") or []),
            "journals": len((world.get("v2") or {}).get("journals") or []),
            "environments_total": len(mig["environments"]),
            "change_projects_total": len(mig["projects"]),
            "change_packages_total": len(mig["packages"]),
            "change_packages_applied": sum(1 for p in mig["packages"] if p.get("applied_to")),
            "compare_conflicts": len((state.get("last_compare") or {}).get("conflicts") or []),
        },
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


# ---------------------------------------------------------------------------
# Actions — the PIA verbs the learner performs to fix the world.
# Every handler returns {"ok": bool, ...}. Unknown actions never raise.
# ---------------------------------------------------------------------------

def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    entry = _load_session(str(session_id))
    if not entry:
        return {"ok": False, "error": "PeopleSoft session not found"}
    state = entry["state"]
    world = state["world"]

    try:
        result = _dispatch(world, state, action, payload)
    except Exception as exc:  # never 500 — surface as a friendly error
        return {"ok": False, "error": f"action failed: {exc}"}

    if result.get("ok"):
        _save_session(str(session_id), entry)
    return result


def _dispatch(world: dict, state: dict, action: str, payload: dict) -> dict:
    act = (action or "").strip()

    # ---- PIA sign-in gate (cosmetic; not graded) ----
    if act in ("login", "sign_in", "signon"):
        oprid = (payload.get("oprid") or payload.get("user") or "PS").strip() or "PS"
        user = _find_user(world, oprid)
        if user and user.get("locked"):
            return {"ok": False, "error": f"Operator {user['oprid']} is locked out — "
                                          "cannot sign in until the account is unlocked."}
        world["session"]["logged_in"] = True
        world["session"]["oprid"] = (user or {}).get("oprid", oprid)
        _event(state, f"Operator {world['session']['oprid']} signed in to PIA")
        return {"ok": True, "message": f"Signed in as {world['session']['oprid']}"}

    if act in ("logout", "sign_out", "signoff"):
        world["session"]["logged_in"] = False
        _event(state, "Operator signed out of PIA")
        return {"ok": True, "message": "Signed out"}

    # ---- Portal navigation ----
    if act in ("navigate", "open_component", "goto"):
        comp_id = payload.get("component") or payload.get("component_id") or payload.get("path")
        comp = _find_component(world, comp_id)
        if not comp:
            return {"ok": False, "error": f"Component '{comp_id}' not found in the menu"}
        mod = _find_module_for_component(world, comp["id"])
        # Access check against the current operator's effective permissions.
        current = _current_user(world)
        req = comp.get("require_permission")
        if req and current is not None:
            held = _user_permissions(world, current)
            if req not in held:
                return {"ok": False,
                        "error": (f"You are not authorized to access {comp['name']} — your "
                                  f"roles do not grant the '{req}' permission.")}
        world["portal"]["current_component"] = comp["id"]
        world["portal"]["current_path"] = [
            mod["name"] if mod else "", comp["menu"], comp["name"]]
        comp["visited"] = True
        _event(state, f"Navigated to {comp['name']}")
        return {"ok": True, "message": f"Opened {comp['name']}",
                "component": comp["id"], "config": comp.get("config", {})}

    # ---- Process Scheduler ----
    if act in ("run_process", "run"):
        name = (payload.get("name") or payload.get("process") or "").strip()
        if not name:
            return {"ok": False, "error": "A process name is required"}
        server = payload.get("server") or "PSUNX"
        proc = world["process"]
        inst = proc["next_instance"]
        proc["next_instance"] = inst + 1
        run = _process_run(inst, name, "success", server=server,
                           run_control=payload.get("run_control") or name.lower())
        proc["runs"].insert(0, run)
        _event(state, f"Submitted process {name} (instance {inst}) — completed Successfully")
        return {"ok": True, "message": f"{name} ran successfully (instance {inst})",
                "instance": inst}

    if act in ("rerun_process", "rerun", "restart_process"):
        run = _find_run(world, payload.get("instance") or payload.get("instance_id"))
        if not run:
            # Allow rerun-by-name if no instance specified.
            name = (payload.get("name") or payload.get("process") or "").strip()
            run = next((r for r in world["process"]["runs"]
                        if name and r["name"].lower() == name.lower()), None)
        if not run:
            return {"ok": False, "error": "Process run not found in Process Monitor"}
        if run["status"] == "success":
            return {"ok": True, "message": f"{run['name']} (instance {run['instance']}) "
                                           "already completed successfully"}
        run["status"] = "success"
        run["message"] = ""
        run["distribution"] = "Posted"
        run["run_datetime"] = _now_iso()
        _event(state, f"Reran {run['name']} (instance {run['instance']}) — now Successful")
        return {"ok": True, "message": f"{run['name']} reran successfully",
                "instance": run["instance"]}

    if act in ("cancel_process", "cancel"):
        run = _find_run(world, payload.get("instance"))
        if not run:
            return {"ok": False, "error": "Process run not found"}
        run["status"] = "cancelled"
        _event(state, f"Cancelled {run['name']} (instance {run['instance']})")
        return {"ok": True, "message": f"{run['name']} cancelled"}

    # ---- Employee Self-Service (Fluid) submissions ----
    # Each self-service submit updates the operator's ESS record and enqueues a
    # Process Scheduler run so the Process Monitor reflects the background job.
    if act in ("submit_benefits", "elect_benefits", "enroll_benefits"):
        oprid = (payload.get("oprid") or payload.get("user")
                 or world.get("session", {}).get("oprid") or "PS")
        prof = _find_profile(world, oprid)
        if not prof:
            return {"ok": False, "error": f"No self-service record for operator {oprid}"}
        plan = (payload.get("plan") or payload.get("plan_id")
                or prof["benefits"].get("elected_plan") or "").strip()
        plans = (world.get("self_service") or {}).get("benefit_plans") or []
        if plan and not any(p["id"] == plan for p in plans):
            return {"ok": False, "error": f"Health plan '{plan}' is not in the enrollment catalog"}
        ben = prof["benefits"]
        ben["elected_plan"] = plan or ben.get("elected_plan")
        ben["submitted_plan"] = ben["elected_plan"]
        ben["event_status"] = "Submitted"
        ben["submitted_at"] = _now_iso()
        run = _enqueue_run(world, state, "BEN_ENROLL", process_type="Application Engine",
                           run_control=f"ben_{prof['oprid'].lower()}")
        _event(state, f"{prof['oprid']} submitted Open Enrollment (plan {ben['submitted_plan']}) "
                      f"— queued BEN_ENROLL (instance {run['instance']})")
        return {"ok": True, "message": f"Open Enrollment submitted for {prof['oprid']}",
                "instance": run["instance"], "benefits": ben}

    if act in ("save_job_data", "submit_job_data", "update_job_data"):
        oprid = (payload.get("oprid") or payload.get("user")
                 or world.get("session", {}).get("oprid") or "PS")
        prof = _find_profile(world, oprid)
        if not prof:
            return {"ok": False, "error": f"No self-service record for operator {oprid}"}
        updates = payload.get("job") if isinstance(payload.get("job"), dict) else {}
        if not updates:
            key = payload.get("field") or payload.get("key")
            if key is not None:
                updates = {str(key): payload.get("value")}
        if updates:
            prof["job"].update(updates)
        run = _enqueue_run(world, state, "PERSONAL_DATA_SYNC", process_type="Application Engine",
                           run_control=f"persdata_{prof['oprid'].lower()}")
        _event(state, f"{prof['oprid']} saved Job/Personal Data — queued PERSONAL_DATA_SYNC "
                      f"(instance {run['instance']})")
        return {"ok": True, "message": f"Job Data saved for {prof['oprid']}",
                "instance": run["instance"], "job": prof["job"]}

    if act in ("request_paycheck", "reprint_paycheck", "view_paycheck"):
        oprid = (payload.get("oprid") or payload.get("user")
                 or world.get("session", {}).get("oprid") or "PS")
        prof = _find_profile(world, oprid)
        if not prof:
            return {"ok": False, "error": f"No self-service record for operator {oprid}"}
        run = _enqueue_run(world, state, "PAY_ADVICE_PRINT", process_type="SQR Report",
                           server="PSNT", run_control=f"payadv_{prof['oprid'].lower()}")
        _event(state, f"{prof['oprid']} requested a pay advice reprint — queued PAY_ADVICE_PRINT "
                      f"(instance {run['instance']})")
        return {"ok": True, "message": f"Pay advice reprint queued for {prof['oprid']}",
                "instance": run["instance"], "paycheck": prof["paycheck"]}

    # ---- Security: roles / permission lists / users ----
    if act in ("assign_role", "add_role", "grant_role"):
        user = _find_user(world, payload.get("user") or payload.get("oprid"))
        if not user:
            return {"ok": False, "error": "User profile not found"}
        role = _find_role(world, payload.get("role") or payload.get("role_id"))
        if not role:
            return {"ok": False, "error": f"Role '{payload.get('role')}' not found"}
        if role["id"] in user["roles"]:
            return {"ok": True, "message": f"{user['oprid']} already holds {role['name']}"}
        user["roles"].append(role["id"])
        _event(state, f"Assigned role {role['name']} to {user['oprid']}")
        return {"ok": True, "message": f"Assigned {role['name']} to {user['oprid']}"}

    if act in ("remove_role", "revoke_role"):
        user = _find_user(world, payload.get("user") or payload.get("oprid"))
        if not user:
            return {"ok": False, "error": "User profile not found"}
        role = _find_role(world, payload.get("role") or payload.get("role_id"))
        if not role or role["id"] not in user["roles"]:
            return {"ok": False, "error": "User does not hold that role"}
        user["roles"].remove(role["id"])
        _event(state, f"Removed role {role['name']} from {user['oprid']}")
        return {"ok": True, "message": f"Removed {role['name']} from {user['oprid']}"}

    if act in ("add_permission", "add_role_to_permlist", "grant_permission"):
        # Adds a permission key to a permission list (the "Pages/Permissions" tab).
        pl = _find_perm_list(world, payload.get("permission_list") or payload.get("permlist")
                             or payload.get("name"))
        if not pl:
            return {"ok": False, "error": "Permission list not found"}
        perm = (payload.get("permission") or payload.get("perm") or "").strip()
        if not perm:
            return {"ok": False, "error": "A permission key is required"}
        if perm in pl["permissions"]:
            return {"ok": True, "message": f"{pl['name']} already grants {perm}"}
        pl["permissions"].append(perm)
        _event(state, f"Added permission {perm} to permission list {pl['name']}")
        return {"ok": True, "message": f"Added {perm} to {pl['name']}"}

    if act in ("add_permlist_to_role", "add_permission_list"):
        role = _find_role(world, payload.get("role") or payload.get("role_id"))
        pl = _find_perm_list(world, payload.get("permission_list") or payload.get("permlist"))
        if not role or not pl:
            return {"ok": False, "error": "Role or permission list not found"}
        if pl["id"] not in role["permission_lists"]:
            role["permission_lists"].append(pl["id"])
        _event(state, f"Added permission list {pl['name']} to role {role['name']}")
        return {"ok": True, "message": f"Added {pl['name']} to {role['name']}"}

    if act in ("unlock_user", "unlock_account", "reset_lockout"):
        user = _find_user(world, payload.get("user") or payload.get("oprid"))
        if not user:
            return {"ok": False, "error": "User profile not found"}
        user["locked"] = False
        user["failed_logins"] = 0
        _event(state, f"Unlocked operator account {user['oprid']}")
        return {"ok": True, "message": f"{user['oprid']} unlocked"}

    if act in ("reset_password", "set_password"):
        user = _find_user(world, payload.get("user") or payload.get("oprid"))
        if not user:
            return {"ok": False, "error": "User profile not found"}
        # Resetting the password also clears the lockout (PeopleSoft behaviour).
        user["locked"] = False
        user["failed_logins"] = 0
        _event(state, f"Reset password for {user['oprid']}")
        return {"ok": True, "message": f"Password reset for {user['oprid']}"}

    if act in ("enable_user", "disable_user"):
        user = _find_user(world, payload.get("user") or payload.get("oprid"))
        if not user:
            return {"ok": False, "error": "User profile not found"}
        user["enabled"] = act == "enable_user"
        _event(state, f"{'Enabled' if user['enabled'] else 'Disabled'} {user['oprid']}")
        return {"ok": True, "message": f"{user['oprid']} {'enabled' if user['enabled'] else 'disabled'}"}

    # ---- Integration Broker ----
    if act in ("restart_ib_node", "activate_node", "ping_node", "start_node"):
        node = _find_node(world, payload.get("node") or payload.get("name"))
        if not node:
            return {"ok": False, "error": "Integration Broker node not found"}
        node["status"] = "active"
        _event(state, f"Integration Broker node {node['name']} is now Active")
        return {"ok": True, "message": f"{node['name']} is active"}

    if act in ("deactivate_node", "stop_node"):
        node = _find_node(world, payload.get("node") or payload.get("name"))
        if not node:
            return {"ok": False, "error": "Integration Broker node not found"}
        node["status"] = "down"
        _event(state, f"Integration Broker node {node['name']} stopped")
        return {"ok": True, "message": f"{node['name']} is down"}

    if act in ("activate_service", "activate_operation"):
        svc = _find_service(world, payload.get("service") or payload.get("name"))
        if not svc:
            return {"ok": False, "error": "Integration Broker service not found"}
        svc["active"] = True
        _event(state, f"Activated service operation {svc['name']}")
        return {"ok": True, "message": f"{svc['name']} activated"}

    if act in ("deactivate_service",):
        svc = _find_service(world, payload.get("service") or payload.get("name"))
        if not svc:
            return {"ok": False, "error": "Integration Broker service not found"}
        svc["active"] = False
        _event(state, f"Deactivated service operation {svc['name']}")
        return {"ok": True, "message": f"{svc['name']} deactivated"}

    # ---- Component configuration ----
    if act in ("set_component_config", "configure_component", "save_component"):
        comp = _find_component(world, payload.get("component") or payload.get("component_id"))
        if not comp:
            return {"ok": False, "error": "Component not found"}
        cfg = payload.get("config")
        if not isinstance(cfg, dict):
            # Allow flat key/value too: {key, value}
            key = payload.get("key")
            if key is not None:
                cfg = {key: payload.get("value")}
            else:
                return {"ok": False, "error": "A config object (or key/value) is required"}
        comp.setdefault("config", {}).update(cfg)
        comp["visited"] = True
        _event(state, f"Saved configuration for {comp['name']}")
        return {"ok": True, "message": f"Saved {comp['name']} configuration",
                "config": comp["config"]}

    # ---- Application Designer / Change Assistant migration lifecycle ----
    # DEV build -> compare report -> TEST apply -> conflict -> resolve ->
    # PROD promote, with rollback of a bad patch.
    if act in ("edit_object", "modify_object", "customise_object"):
        # Edit a definition inside one environment. Editing anywhere other than
        # DEV is a site customisation — that is what later collides with a
        # promotion and produces the compare-report conflict.
        env = _find_env(world, payload.get("environment") or payload.get("env") or "DEV")
        if not env:
            return {"ok": False, "error": f"Environment '{payload.get('environment')}' not found"}
        name = (payload.get("object") or payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "An object name is required"}
        obj = env["objects"].get(name)
        if not obj:
            obj = _ps_object(name, version=0, obj_type=payload.get("type") or "Page")
            env["objects"][name] = obj
        obj["version"] = int(obj["version"]) + 1
        if payload.get("body"):
            obj["body"] = str(payload["body"])
        # A change made outside DEV is a local customisation.
        if env["name"] != "DEV":
            obj["customised"] = True
        _event(state, f"{env['name']}: saved {name} (version {obj['version']})"
                      + (" — site customisation" if obj.get("customised") else ""))
        return {"ok": True, "message": f"Saved {name} in {env['name']} (v{obj['version']})",
                "object": _copy_object(obj)}

    if act in ("create_project", "build_project", "create_change_project"):
        # App Designer: build a change project in DEV from a list of objects.
        name = (payload.get("project") or payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "A project name is required"}
        if _find_project(world, name):
            return {"ok": False, "error": f"Project '{name}' already exists"}
        src = _find_env(world, payload.get("source") or "DEV")
        if not src:
            return {"ok": False, "error": "Source environment not found"}
        raw = payload.get("objects") or payload.get("object_names") or []
        if isinstance(raw, str):
            raw = [p.strip() for p in raw.split(",") if p.strip()]
        objects = [n for n in raw if n in src["objects"]]
        missing = [n for n in raw if n not in src["objects"]]
        if missing:
            return {"ok": False,
                    "error": f"Not in {src['name']}: {', '.join(missing)}"}
        if not objects:
            return {"ok": False, "error": "A change project needs at least one object"}
        proj = {
            "name": name,
            "source": src["name"],
            "objects": objects,
            # DEV version captured at build time — the package payload is cut
            # from this, so later DEV edits do not leak into a built package.
            "built_versions": {n: src["objects"][n]["version"] for n in objects},
            "created_at": _now_iso(),
        }
        _migration(world)["projects"].append(proj)
        _event(state, f"Built change project {name} in {src['name']} "
                      f"({len(objects)} object(s))")
        return {"ok": True, "message": f"Project {name} built in {src['name']}",
                "project": copy.deepcopy(proj)}

    if act in ("compare_project", "compare_report", "run_compare"):
        # Change Assistant / App Designer compare: source env vs target env.
        proj_name = payload.get("project") or payload.get("name")
        proj = _find_project(world, proj_name) if proj_name else None
        if proj_name and not proj:
            return {"ok": False, "error": f"Project '{proj_name}' not found"}
        source = payload.get("source") or (proj or {}).get("source") or "DEV"
        target = payload.get("target") or payload.get("environment")
        if not target:
            return {"ok": False, "error": "A target environment is required"}
        report = _compare_report(world, source, target,
                                 (proj or {}).get("objects"))
        if not report:
            return {"ok": False, "error": "Source or target environment not found"}
        state["last_compare"] = report
        _event(state, f"Compare report {report['source']} -> {report['target']}: "
                      f"{len(report['rows'])} object(s), "
                      f"{len(report['conflicts'])} conflict(s)")
        return {"ok": True, "message": (f"Compare {report['source']} -> {report['target']} "
                                        f"complete ({len(report['conflicts'])} conflict(s))"),
                "report": report}

    if act in ("create_package", "build_package", "cut_package"):
        # Change Assistant: freeze the project's DEV definitions into a package.
        proj = _find_project(world, payload.get("project") or payload.get("name"))
        if not proj:
            return {"ok": False, "error": "Change project not found — build it in App Designer first"}
        src = _find_env(world, proj["source"])
        if not src:
            return {"ok": False, "error": "Project source environment not found"}
        mig = _migration(world)
        seq = mig["next_package_seq"]
        mig["next_package_seq"] = seq + 1
        pkg_id = (payload.get("package") or payload.get("package_id")
                  or f"CP-{seq:03d}").strip()
        if _find_package(world, pkg_id):
            return {"ok": False, "error": f"Change package '{pkg_id}' already exists"}
        pkg = {
            "id": pkg_id,
            "project": proj["name"],
            "source": src["name"],
            "status": "built",
            "created_at": _now_iso(),
            # Frozen payload — copied by value out of DEV at cut time.
            "payload": {n: _copy_object(src["objects"][n])
                        for n in proj["objects"] if n in src["objects"]},
            # Per-environment apply history; each entry keeps the pre-apply
            # snapshot so rollback restores exactly what was overwritten.
            "applied_to": [],
            "history": [],
        }
        mig["packages"].append(pkg)
        _event(state, f"Cut change package {pkg_id} from project {proj['name']}")
        return {"ok": True, "message": f"Change package {pkg_id} built from {proj['name']}",
                "package_id": pkg_id, "package": copy.deepcopy(pkg)}

    if act in ("apply_package", "promote_package", "promote", "apply_change_package"):
        pkg = _find_package(world, payload.get("package") or payload.get("package_id"))
        if not pkg:
            return {"ok": False, "error": "Change package not found — build it in Change Assistant first"}
        target = _find_env(world, payload.get("target") or payload.get("environment"))
        if not target:
            return {"ok": False, "error": f"Environment '{payload.get('target')}' not found"}
        if target["name"] == pkg["source"]:
            return {"ok": False, "error": f"{pkg['id']} was built in {pkg['source']} — "
                                          "promote it to a downstream environment"}
        # Enforce the DEV -> TEST -> PROD path: every environment between the
        # package source and the target must already have this package applied.
        try:
            src_i = _ENV_ORDER.index(pkg["source"])
            tgt_i = _ENV_ORDER.index(target["name"])
        except ValueError:
            return {"ok": False, "error": "Unknown environment in promotion path"}
        if tgt_i < src_i:
            return {"ok": False, "error": f"Cannot promote backwards to {target['name']}"}
        skipped = [e for e in _ENV_ORDER[src_i + 1:tgt_i] if e not in pkg["applied_to"]]
        if skipped:
            return {"ok": False,
                    "error": (f"{pkg['id']} has not been applied to {', '.join(skipped)} yet — "
                              f"promote through {_ENV_ORDER[src_i + 1]} before {target['name']}.")}
        if target["name"] in pkg["applied_to"]:
            return {"ok": True, "message": f"{pkg['id']} is already applied to {target['name']}"}
        # Customisation conflict: refuse rather than silently overwriting local
        # work. The learner must resolve each conflicting object first.
        force = bool(payload.get("force") or payload.get("overwrite"))
        conflicts = [n for n in pkg["payload"]
                     if (target["objects"].get(n) or {}).get("customised")]
        if conflicts and not force:
            return {"ok": False, "conflicts": conflicts,
                    "error": (f"Customisation conflict applying {pkg['id']} to {target['name']}: "
                              f"{', '.join(sorted(conflicts))} was customised in {target['name']}. "
                              "Run a compare report and resolve each conflict "
                              "(keep_customisation or accept_vendor) before promoting.")}
        # Snapshot what we are about to overwrite so rollback is exact.
        before = {n: _copy_object(target["objects"][n])
                  for n in pkg["payload"] if n in target["objects"]}
        for name, obj in pkg["payload"].items():
            # Copy by VALUE — sharing the dict would make a later TEST edit
            # mutate PROD (and make rollback appear to succeed while dirty).
            target["objects"][name] = _copy_object(obj)
        pkg["applied_to"].append(target["name"])
        pkg["status"] = "applied"
        pkg["history"].append({
            "environment": target["name"], "action": "apply", "at": _now_iso(),
            "before": before, "objects": sorted(pkg["payload"]),
        })
        target["last_applied_package"] = pkg["id"]
        _event(state, f"Applied change package {pkg['id']} to {target['name']} "
                      f"({len(pkg['payload'])} object(s))")
        return {"ok": True, "message": f"{pkg['id']} applied to {target['name']}",
                "environment": target["name"], "objects": sorted(pkg["payload"])}

    if act in ("resolve_conflict", "resolve_customisation"):
        # Resolve one compare-report conflict before promoting.
        #   keep_customisation — keep the target's local definition and drop the
        #                        object from the package payload.
        #   accept_vendor      — discard the local customisation and let the
        #                        package overwrite it.
        target = _find_env(world, payload.get("environment") or payload.get("target"))
        if not target:
            return {"ok": False, "error": f"Environment '{payload.get('environment')}' not found"}
        name = (payload.get("object") or payload.get("name") or "").strip()
        obj = target["objects"].get(name)
        if not obj:
            return {"ok": False, "error": f"{name} not found in {target['name']}"}
        resolution = (payload.get("resolution") or payload.get("action") or "").strip().lower()
        pkg = _find_package(world, payload.get("package") or payload.get("package_id"))
        if resolution in ("accept_vendor", "vendor", "overwrite", "take_source"):
            obj["customised"] = False
            _event(state, f"{target['name']}: accepted vendor definition for {name}")
            return {"ok": True, "message": f"{name} will take the incoming definition in "
                                           f"{target['name']}"}
        if resolution in ("keep_customisation", "keep", "keep_target"):
            if not pkg:
                return {"ok": False, "error": "keep_customisation needs the package id so the "
                                              "object can be dropped from its payload"}
            pkg["payload"].pop(name, None)
            obj["customised"] = False
            _event(state, f"{target['name']}: kept the site customisation of {name} — "
                          f"removed from package {pkg['id']}")
            return {"ok": True, "message": f"Kept {target['name']}'s customisation of {name}; "
                                           f"{name} dropped from {pkg['id']}"}
        return {"ok": False, "error": "resolution must be 'keep_customisation' or 'accept_vendor'"}

    if act in ("rollback_package", "rollback", "back_out_package"):
        # Back a bad patch out of one environment, restoring the exact
        # pre-apply definitions captured in the apply history.
        pkg = _find_package(world, payload.get("package") or payload.get("package_id"))
        if not pkg:
            return {"ok": False, "error": "Change package not found"}
        target = _find_env(world, payload.get("environment") or payload.get("target"))
        if not target:
            return {"ok": False, "error": f"Environment '{payload.get('environment')}' not found"}
        entry = next((h for h in reversed(pkg["history"])
                      if h["environment"] == target["name"] and h["action"] == "apply"), None)
        if not entry or target["name"] not in pkg["applied_to"]:
            return {"ok": False, "error": f"{pkg['id']} is not applied to {target['name']} — "
                                          "nothing to roll back"}
        for name in entry["objects"]:
            prior = entry["before"].get(name)
            if prior is None:
                # The object did not exist before the apply — remove it again.
                target["objects"].pop(name, None)
            else:
                target["objects"][name] = _copy_object(prior)
        pkg["applied_to"].remove(target["name"])
        pkg["status"] = "rolled_back" if not pkg["applied_to"] else "applied"
        pkg["history"].append({
            "environment": target["name"], "action": "rollback", "at": _now_iso(),
            "objects": list(entry["objects"]),
        })
        target["last_applied_package"] = ""
        _event(state, f"Rolled back change package {pkg['id']} from {target['name']}",
               severity="warning")
        return {"ok": True, "message": f"{pkg['id']} rolled back from {target['name']}",
                "environment": target["name"], "objects": list(entry["objects"])}

    if act in ("reset",):
        # Re-seed the world from the preset (fresh start).
        slug = state.get("goal", {}).get("slug") or ""
        new = {"world": _base_world()}
        # Reapply the same goal kind by replaying the preset using the stored scenario.
        _apply_preset(new, slug)
        state["world"] = new["world"]
        state["goal"] = new.get("goal", state.get("goal"))
        _event(state, "Lab reset to initial state")
        return {"ok": True, "message": "Lab reset"}

    v2 = apply_v2_action(world, act, payload)
    if v2 is not None:
        if v2.get("ok"):
            _event(state, v2.get("message") or act)
        return v2

    return {"ok": False, "error": f"unknown action: {action}"}


# ---------------------------------------------------------------------------
# Validation — grade on whether the broken state was fixed via the intended fix.
# ---------------------------------------------------------------------------

def validate_peoplesoft_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load_session(str(session_id)) or _ensure_session(session_id, scenario_slug)
    state = entry["state"]
    world = state["world"]
    goal = state.get("goal") or {}
    kind = goal.get("kind")

    if kind == "process_success":
        run = _find_run(world, goal.get("target_instance"))
        if not run:
            name = (goal.get("target_process") or "")
            run = next((r for r in world["process"]["runs"]
                        if r["name"].lower() == name.lower()), None)
        if not run:
            return False, f"Process run {goal.get('target_instance')} not found in Process Monitor."
        if run["status"] != "success":
            return False, (f"{run['name']} (instance {run['instance']}) is still "
                           f"'{run['status']}'. Rerun it from the Process Scheduler so it "
                           "completes Successfully.")
        return True, (f"{run['name']} (instance {run['instance']}) completed Successfully — "
                      "validation passed.")

    if kind == "user_can_access":
        user = _find_user(world, goal.get("target_user"))
        if not user:
            return False, f"User {goal.get('target_user')} not found."
        comp = _find_component(world, goal.get("target_component"))
        if not comp:
            return False, "Target component not found."
        held = _user_permissions(world, user)
        req = comp.get("require_permission")
        if req and req not in held:
            return False, (f"{user['oprid']} still cannot open {comp['name']} — their roles do "
                           f"not grant the '{req}' permission. Assign the "
                           f"{goal.get('require_role')} role in User Profiles.")
        return True, (f"{user['oprid']} can now open {comp['name']} — validation passed.")

    if kind == "permlist_has_permission":
        pl = _find_perm_list(world, goal.get("target_permlist"))
        if not pl:
            return False, f"Permission list {goal.get('target_permlist')} not found."
        perm = goal.get("require_permission")
        if perm not in pl.get("permissions", []):
            return False, (f"The {pl['name']} permission list still does not grant "
                           f"'{perm}'. Add it on the Permission List's pages/permissions tab.")
        return True, (f"{pl['name']} now grants '{perm}' — validation passed.")

    if kind == "ib_node_active":
        node = _find_node(world, goal.get("target_node"))
        if not node:
            return False, f"Integration Broker node {goal.get('target_node')} not found."
        if node["status"] != "active":
            return False, (f"The {node['name']} node is still {node['status']} — "
                           "restart/ping it on the Integration Broker Nodes page.")
        return True, (f"The {node['name']} node is Active — validation passed.")

    if kind == "component_config":
        comp = _find_component(world, goal.get("target_component"))
        if not comp:
            return False, "Target component not found."
        if goal.get("require_navigated") and not comp.get("visited"):
            return False, (f"Navigate to the {comp['name']} component first, then correct "
                           "its configuration.")
        cfg = comp.get("config", {})
        for key, want in (goal.get("require_config") or {}).items():
            have = cfg.get(key)
            # Numeric "at least" semantics for head-count style thresholds.
            if isinstance(want, int) and not isinstance(want, bool):
                try:
                    if int(have) < want:
                        return False, (f"{comp['name']}: {key} must be at least {want} "
                                       f"(currently {have}).")
                    continue
                except (TypeError, ValueError):
                    return False, f"{comp['name']}: {key} is not set correctly (need {want})."
            if str(have) != str(want):
                return False, (f"{comp['name']}: {key} must be '{want}' (currently '{have}'). "
                               "Set it and save the component.")
        return True, (f"{comp['name']} is configured correctly — validation passed.")

    if kind == "user_unlocked":
        user = _find_user(world, goal.get("target_user"))
        if not user:
            return False, f"User {goal.get('target_user')} not found."
        if user.get("locked"):
            return False, (f"{user['oprid']} is still locked out — unlock the account "
                           "(set Account Locked Out = N) in User Profiles.")
        return True, (f"{user['oprid']} is unlocked and can sign in — validation passed.")

    if kind == "package_promoted":
        # The fix must be live in every required environment at the right
        # version, and any protected site customisation must have survived.
        for env_name in goal.get("require_environments") or []:
            env = _find_env(world, env_name)
            if not env:
                return False, f"Environment {env_name} not found."
            for name, want in (goal.get("require_version") or {}).items():
                obj = env["objects"].get(name)
                if not obj:
                    return False, (f"{name} has not been promoted to {env_name} yet — build a "
                                   "change package in Change Assistant and apply it.")
                if int(obj.get("version", 0)) < int(want):
                    return False, (f"{env_name} is still running {name} version "
                                   f"{obj.get('version')} (need {want}). Apply the change "
                                   "package to this environment.")
        for env_name, names in (goal.get("protect_customisation") or {}).items():
            env = _find_env(world, env_name)
            if not env:
                continue
            for name in names:
                if name not in env["objects"]:
                    return False, (f"The {env_name} customisation of {name} was destroyed by the "
                                   "promotion — resolve the conflict with keep_customisation "
                                   "instead of overwriting it.")
        return True, ("The change package is promoted through to PROD and the site "
                      "customisation survived — validation passed.")

    if kind == "package_rolled_back":
        pkg = _find_package(world, goal.get("target_package"))
        if not pkg:
            return False, f"Change package {goal.get('target_package')} not found."
        env_name = goal.get("target_environment") or "PROD"
        env = _find_env(world, env_name)
        if not env:
            return False, f"Environment {env_name} not found."
        if env_name in pkg.get("applied_to", []):
            return False, (f"{pkg['id']} is still applied to {env_name} — roll it back in "
                           "Change Assistant.")
        for name, want in (goal.get("restore_version") or {}).items():
            obj = env["objects"].get(name)
            if not obj:
                return False, f"{name} is missing from {env_name} after the rollback."
            if int(obj.get("version", 0)) != int(want):
                return False, (f"{env_name} is running {name} version {obj.get('version')} — "
                               f"the rollback must restore version {want}.")
        return True, (f"{pkg['id']} is rolled back and {env_name} is on the pre-patch "
                      "definition — validation passed.")

    return False, "No validation goal configured for this scenario"
