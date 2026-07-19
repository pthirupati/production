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
    # Advance any queued/running self-service jobs on wall-clock, then persist
    # so the Process Monitor reflects the progression across polls/workers.
    if _advance_lifecycle(entry["state"]["world"]):
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

    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "inventory": world,
        "goal": goal,
        "events": world.get("events", []),
        "access": accessible,
        # Self-service record for the signed-in operator (Fluid pages read this).
        "ess_profile": ess_profile,
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

    return False, "No validation goal configured for this scenario"
