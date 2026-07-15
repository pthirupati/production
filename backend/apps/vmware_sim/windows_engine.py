"""
In-memory Windows Server GUI simulator for training labs.

Models a realistic Windows Server 2022 world the learner administers through a
GUI (Server Manager, Active Directory Users and Computers, Windows Update, and
the Services console) rather than a terminal. The engine tracks:

  - domain          : forest/domain name + the domain controllers in it, and
                      whether THIS member server has joined the domain yet.
  - roles/features  : Server Manager roles (AD DS, DNS, DHCP, IIS, File
                      Services ...) each either installed or available.
  - ad              : Active Directory objects — organizational units, security
                      groups, and users {name, enabled, locked, group, ...}.
  - updates         : Windows Update entries {kb, title, status pending|
                      installed|failed}.
  - services        : Windows services {name, status running|stopped, startup
                      automatic|manual|disabled}.

Each scenario preset puts the world into a clearly *broken* state (a locked AD
user, a user missing from a security group, a role not installed, a stuck/
failed update, a stopped critical service, an un-joined server, ...). The fix
is exposed purely through ``apply_action`` (install_role, unlock_ad_user,
add_user_to_group, retry_update, start_service, join_domain, ...). An unknown
action always returns ``{"ok": False, "error": ...}`` and never raises.

``validate_windows_lab`` grades the lab by checking the broken state was fixed
via the intended GUI action. A fresh session always fails; only the intended
remediation flips it to pass.

Sessions live in the Django cache (Redis in production) for multi-worker
safety, mirroring the VMware / K8s / Docker / monitoring / nmap / datascience
engines (SESSION_TTL=7200). Pure stdlib — no external dependencies.
"""

from __future__ import annotations

import copy
import json
import time
from typing import Any

from django.core.cache import cache

SESSION_TTL = 7200  # 2-hour TTL matching the other simulator engines

# Interactive-session idle timeout (seconds). A signed-in console/RDP session
# with no activity for this long auto-locks, exactly like a real "on resume,
# display logon screen" screen-saver / RDP idle-session-limit policy. Kept short
# so the effect is observable in a lab sitting. Advanced on wall-clock in
# get_state (mirrors the baremetal/nmap/monitoring wall-clock advance pattern).
SESSION_IDLE_LOCK_SECONDS = 900   # 15 min idle -> auto-lock
RDP_DISCONNECT_LOGOFF_SECONDS = 1800  # disconnected RDP session logs off after 30 min


def _session_key(session_id: str) -> str:
    return f"windows_session:{session_id}"


def _load_session(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save_session(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now() -> float:
    return time.time()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# Valid enumerations the engine understands (used to validate action payloads).
_SERVICE_STATUSES = ("running", "stopped")
_STARTUP_TYPES = ("automatic", "automatic-delayed", "manual", "disabled")
_UPDATE_STATES = ("pending", "downloading", "installed", "failed")


# ---------------------------------------------------------------------------
# Base Windows Server world (the "real" machine the learner administers).
# Presets clone this and break one thing.
# ---------------------------------------------------------------------------

DEFAULT_DOMAIN = "corp.fixitlab.local"
DEFAULT_DC = "DC01.corp.fixitlab.local"


def _role(role_id: str, name: str, installed: bool, *, category: str = "role",
          description: str = "") -> dict:
    return {
        "id": role_id,
        "name": name,
        "category": category,            # role | feature
        "installed": bool(installed),
        "description": description,
    }


def _user(name: str, *, display: str = "", enabled: bool = True,
          locked: bool = False, group: str = "Domain Users",
          groups: list[str] | None = None, ou: str = "Users",
          must_change_pw: bool = False) -> dict:
    return {
        "name": name,
        "display": display or name,
        "enabled": bool(enabled),
        "locked": bool(locked),
        # `group` is the user's primary group; `groups` is full membership.
        "group": group,
        "groups": list(groups) if groups is not None else [group],
        "ou": ou,
        "must_change_pw": bool(must_change_pw),
    }


def _service(name: str, display: str, status: str, startup: str) -> dict:
    return {
        "name": name,
        "display": display,
        "status": status if status in _SERVICE_STATUSES else "stopped",
        "startup": startup if startup in _STARTUP_TYPES else "manual",
    }


def _update(kb: str, title: str, status: str, *, severity: str = "Important",
            reboot: bool = False) -> dict:
    return {
        "kb": kb,
        "title": title,
        "status": status if status in _UPDATE_STATES else "pending",
        "severity": severity,
        "reboot_required": bool(reboot),
        "error_code": "",
    }


def _gpo_setting(key: str, value: str, *, enabled: bool = True, category: str = "Security Settings") -> dict:
    return {"key": key, "value": value, "enabled": bool(enabled), "category": category}


def _gpo(gid: str, name: str, *, settings: list[dict] | None = None,
         links: list[str] | None = None, status: str = "Enabled") -> dict:
    return {
        "id": gid,
        "name": name,
        "status": status if status in ("Enabled", "Disabled") else "Enabled",
        "settings": settings if settings is not None else [
            _gpo_setting("Enforce password history", "24 passwords remembered"),
            _gpo_setting("Maximum password age", "90 days"),
            _gpo_setting("Minimum password length", "14 characters"),
            _gpo_setting("Password must meet complexity requirements", "Enabled"),
        ],
        "links": list(links) if links is not None else [],
    }


def _find_gpo(world: dict, gpo_id: str) -> dict | None:
    target = (gpo_id or "").lower()
    for g in world.get("group_policy", {}).get("gpos", []):
        if g["id"].lower() == target or g["name"].lower() == target:
            return g
    return None


def _base_world() -> dict:
    """A healthy Windows Server 2022 member-server world. Presets break one thing."""
    return {
        "computer_name": "WIN-SRV-APP01",
        "os": "Windows Server 2022 Datacenter",
        "domain": {
            "joined": True,
            "name": DEFAULT_DOMAIN,
            "netbios": "CORP",
            "workgroup": "WORKGROUP",
            "dcs": [DEFAULT_DC, "DC02.corp.fixitlab.local"],
        },
        "roles": [
            _role("AD-Domain-Services", "Active Directory Domain Services", True,
                  description="Stores directory data and manages the domain."),
            _role("DNS", "DNS Server", True,
                  description="Resolves names to IP addresses for the domain."),
            _role("DHCP", "DHCP Server", False,
                  description="Leases IP addresses to clients on the network."),
            _role("Web-Server", "Web Server (IIS)", False,
                  description="Hosts web sites and applications over HTTP/HTTPS."),
            _role("FS-FileServer", "File Services", True,
                  description="Provides SMB file shares and storage management."),
            _role("NET-Framework-45", "NET Framework 4.5 Features", True,
                  category="feature",
                  description="Runtime libraries for .NET applications."),
            _role("Telnet-Client", "Telnet Client", False, category="feature",
                  description="Command-line client for the Telnet protocol."),
        ],
        "ad": {
            "ous": ["Users", "Computers", "Servers", "Service Accounts"],
            "groups": [
                {"name": "Domain Admins", "scope": "Global",
                 "description": "Full administrative control of the domain."},
                {"name": "Domain Users", "scope": "Global",
                 "description": "All domain user accounts."},
                {"name": "Remote Desktop Users", "scope": "DomainLocal",
                 "description": "Members may log on remotely via RDP."},
                {"name": "Backup Operators", "scope": "DomainLocal",
                 "description": "May back up and restore files regardless of permissions."},
                {"name": "Help Desk", "scope": "Global",
                 "description": "Tier-1 support staff."},
            ],
            "users": [
                _user("administrator", display="Administrator", group="Domain Admins",
                      groups=["Domain Admins", "Domain Users"], ou="Users"),
                _user("jsmith", display="John Smith", group="Domain Users",
                      groups=["Domain Users"], ou="Users"),
                _user("agarcia", display="Ana Garcia", group="Domain Users",
                      groups=["Domain Users", "Help Desk"], ou="Users"),
                _user("svc-backup", display="Backup Service",
                      group="Backup Operators",
                      groups=["Backup Operators", "Domain Users"],
                      ou="Service Accounts"),
            ],
        },
        "updates": [
            _update("KB5031356", "2024-09 Cumulative Update for Windows Server 2022",
                    "installed", severity="Critical", reboot=True),
            _update("KB5030216", "Servicing Stack Update for Windows Server 2022",
                    "installed", severity="Important"),
        ],
        "services": [
            _service("Netlogon", "Netlogon", "running", "automatic"),
            _service("DNS", "DNS Server", "running", "automatic"),
            _service("LanmanServer", "Server", "running", "automatic"),
            _service("W32Time", "Windows Time", "running", "automatic"),
            _service("Spooler", "Print Spooler", "running", "automatic"),
            _service("wuauserv", "Windows Update", "running", "manual"),
        ],
        # Interactive session state for the UI. NOT graded — the validators only
        # inspect roles/users/services/updates/domain — but modelled with a real
        # login/lock/logoff lifecycle + idle timeout instead of a static flag so
        # the lock screen behaves like a real console/RDP session.
        #   state: logged_off | active | idle | locked
        "session": {
            "logged_in": False,
            "locked": False,
            "current_user": "CORP\\Administrator",
            "state": "logged_off",
            "login_at": None,        # wall-clock epoch of sign-in
            "last_activity": None,   # wall-clock epoch of last interaction
            "logon_type": "Console",  # Console | RemoteInteractive (RDP)
        },
        # Terminal Services / RDP sessions visible in "quser" / Task Manager Users.
        # Session 0 is the always-present services session; interactive sessions
        # (console + any RDP) advance through Active -> Disconnected -> logged off.
        "rdp_sessions": [
            {"id": 0, "user": "SYSTEM", "state": "Services", "type": "Services",
             "client": "", "idle_seconds": 0, "logon_at": None},
        ],
        "group_policy": {
            "forest": DEFAULT_DOMAIN,
            "containers": [
                {"path": DEFAULT_DOMAIN, "type": "domain"},
                {"path": f"{DEFAULT_DOMAIN}/Policies", "type": "policies"},
            ],
            "gpos": [
                _gpo("default-domain-policy", "Default Domain Policy",
                     links=[DEFAULT_DOMAIN]),
                _gpo("rdp-lockdown", "RDP Lockdown GPO", settings=[
                    _gpo_setting("Allow log on through Remote Desktop Services",
                                 "Remote Desktop Users", category="User Rights Assignment"),
                    _gpo_setting("Deny log on through Remote Desktop Services",
                                 "Not configured", category="User Rights Assignment"),
                ], links=[]),
            ],
        },
        "storage": {
            "disks": [
                {"id": "disk0", "number": 0, "model": "VMware Virtual disk SCSI Disk Device",
                 "size_gb": 80, "partition_style": "GPT", "status": "Online", "bus": "SCSI"},
            ],
            "volumes": [
                {"letter": "C:", "label": "Windows", "fs": "NTFS", "size_gb": 78,
                 "free_gb": 42, "health": "Healthy", "disk_id": "disk0"},
            ],
        },
        "network": {
            "hostname": "WIN-SRV-APP01",
            "adapters": [
                {"id": "eth0", "name": "Ethernet0",
                 "desc": "Intel(R) 82574L Gigabit Network Connection",
                 "mac": "00:50:56:9a:12:34", "status": "Connected",
                 "ipv4": "10.0.1.15", "mask": "255.255.255.0", "gw": "10.0.1.1",
                 "dns": ["10.0.1.10", "10.0.1.11"], "dhcp": False},
                {"id": "eth1", "name": "Ethernet1",
                 "desc": "Intel(R) 82574L Gigabit Network Connection",
                 "mac": "00:50:56:9a:56:78", "status": "Disconnected",
                 "ipv4": "", "mask": "", "gw": "", "dns": [], "dhcp": True},
            ],
        },
        "devices": [
            {"id": "dev0", "name": "Microsoft Hyper-V Virtual Machine Bus Provider",
             "class": "System devices", "status": "OK", "driver": "vmbusr.sys"},
            {"id": "dev1", "name": "VMware VMXNET3 Ethernet Adapter",
             "class": "Network adapters", "status": "OK", "driver": "vmxnet3.sys"},
            {"id": "dev2", "name": "VMware Virtual disk SCSI Disk Device",
             "class": "Disk drives", "status": "OK", "driver": "disk.sys"},
        ],
        "explorer": {
            "drives": [
                {"path": "C:\\", "label": "Windows", "type": "Local Disk"},
            ],
            "folders": {
                "C:\\": ["Windows", "Users", "Program Files", "Program Files (x86)", "inetpub"],
                "C:\\Users": ["Administrator", "Public"],
                "C:\\Users\\Administrator": ["Desktop", "Documents", "Downloads"],
            },
        },
        "settings": {
            "edition": "Windows Server 2022 Datacenter",
            "build": "20348.2487",
            "activated": True,
            "time_zone": "UTC",
            "remote_desktop": True,
        },
    }


# ---------------------------------------------------------------------------
# Scenario presets — break exactly one thing + describe the goal.
# Validation reads `goal` against the live world. A fresh (broken) world fails;
# the intended action fixes it and flips validation to pass.
# ---------------------------------------------------------------------------

def _preset_unlock_user(world: dict) -> dict:
    """A locked + disabled AD user that cannot log in."""
    for u in world["ad"]["users"]:
        if u["name"] == "jsmith":
            u["locked"] = True
            u["enabled"] = False
    return {
        "kind": "ad_user_active",
        "title": "Restore John Smith's locked-out account",
        "target_user": "jsmith",
        "objective": (
            "John Smith (jsmith) cannot sign in: his Active Directory account is "
            "locked out and disabled. In Active Directory Users and Computers, "
            "unlock the account and re-enable it so he can log on again."
        ),
        "require": {"locked": False, "enabled": True},
    }


def _preset_add_to_group(world: dict) -> dict:
    """A user who needs to be added to the Remote Desktop Users group."""
    # jsmith is a plain Domain User; the task is to grant RDP access.
    return {
        "kind": "ad_group_member",
        "title": "Grant John Smith Remote Desktop access",
        "target_user": "jsmith",
        "target_group": "Remote Desktop Users",
        "objective": (
            "John Smith needs to connect to this server over RDP, but he is not a "
            "member of the Remote Desktop Users group. In Active Directory Users "
            "and Computers, add jsmith to the 'Remote Desktop Users' group."
        ),
        "require": {"group": "Remote Desktop Users", "member": True},
    }


def _preset_install_role(world: dict) -> dict:
    """The DHCP role is missing and must be installed via Server Manager."""
    for r in world["roles"]:
        if r["id"] == "DHCP":
            r["installed"] = False
    return {
        "kind": "role_installed",
        "title": "Install the DHCP Server role",
        "target_role": "DHCP",
        "objective": (
            "Clients on the LAN are no longer getting IP addresses because this "
            "server is supposed to be the DHCP server but the role was never "
            "installed. In Server Manager, use Add Roles and Features to install "
            "the 'DHCP Server' role."
        ),
        "require": {"role": "DHCP", "installed": True},
    }


def _preset_retry_update(world: dict) -> dict:
    """A Windows Update stuck in the failed state that must be retried."""
    world["updates"].append(_update(
        "KB5034123", "2025-01 Cumulative Update for Windows Server 2022",
        "failed", severity="Critical", reboot=True))
    # Annotate the failure with a realistic error code.
    for upd in world["updates"]:
        if upd["kb"] == "KB5034123":
            upd["error_code"] = "0x80073712"
    return {
        "kind": "update_installed",
        "title": "Recover the failed January cumulative update",
        "target_kb": "KB5034123",
        "objective": (
            "The January 2025 cumulative update (KB5034123) failed to install with "
            "error 0x80073712 and the server is missing critical security fixes. In "
            "Windows Update, retry the failed update so it installs successfully."
        ),
        "require": {"kb": "KB5034123", "status": "installed"},
    }


def _preset_start_service(world: dict) -> dict:
    """A critical service stopped and set to disabled — start it + set automatic."""
    for s in world["services"]:
        if s["name"] == "Spooler":
            s["status"] = "stopped"
            s["startup"] = "disabled"
    return {
        "kind": "service_running",
        "title": "Bring the Print Spooler service back online",
        "target_service": "Spooler",
        "objective": (
            "Users cannot print: the Print Spooler service is stopped and its "
            "startup type was set to Disabled, so it will not survive a reboot. In "
            "the Services console, set Print Spooler's startup type to Automatic "
            "and start the service."
        ),
        "require": {"service": "Spooler", "status": "running", "startup": "automatic"},
    }


def _preset_join_domain(world: dict) -> dict:
    """The server is in a workgroup and must be joined to the domain."""
    world["domain"]["joined"] = False
    world["domain"]["name"] = ""
    world["domain"]["netbios"] = ""
    world["computer_name"] = "WIN-SRV-NEW01"
    # An un-joined member server cannot reach the directory: Netlogon is idle.
    for s in world["services"]:
        if s["name"] == "Netlogon":
            s["status"] = "stopped"
    world["session"]["current_user"] = "WIN-SRV-NEW01\\Administrator"
    return {
        "kind": "domain_joined",
        "title": "Join the new server to the corp domain",
        "target_domain": DEFAULT_DOMAIN,
        "objective": (
            "This freshly imaged server is still in WORKGROUP and cannot use domain "
            "accounts or Group Policy. Using System Properties, join it to the "
            f"'{DEFAULT_DOMAIN}' Active Directory domain."
        ),
        "require": {"joined": True, "domain": DEFAULT_DOMAIN},
    }


# slug (without the leading "win-gui-") -> preset builder
_PRESETS = {
    "unlock-ad-user": _preset_unlock_user,
    "ad-group-membership": _preset_add_to_group,
    "install-dns-role": _preset_install_role,   # historical alias -> DHCP role install
    "install-server-role": _preset_install_role,
    "retry-windows-update": _preset_retry_update,
    "start-critical-service": _preset_start_service,
    "join-domain": _preset_join_domain,
}


def _apply_preset(world: dict, slug: str) -> dict:
    """Mutate `world` into the broken state for `slug` and return its goal.

    Matching is keyword-based (after stripping the win-gui- prefix) so small
    naming drift in scenario slugs still resolves to the right preset, mirroring
    the nmap engine's tolerant preset matcher.
    """
    s = (slug or "").lower()
    if s.startswith("win-gui-"):
        s = s[len("win-gui-"):]

    builder = _PRESETS.get(s)
    if builder is None:
        if "unlock" in s or ("user" in s and "group" not in s):
            builder = _preset_unlock_user
        elif "group" in s or "member" in s or "rdp" in s:
            builder = _preset_add_to_group
        elif "role" in s or "dhcp" in s or "dns" in s or "iis" in s:
            builder = _preset_install_role
        elif "update" in s or "wsus" in s or s.startswith("kb"):
            builder = _preset_retry_update
        elif "service" in s or "spooler" in s:
            builder = _preset_start_service
        elif "domain" in s or "join" in s:
            builder = _preset_join_domain
        else:
            # Unknown slug still presents a real, gradeable task.
            builder = _preset_unlock_user

    return builder(world)


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------

def _find_user(world: dict, name: str) -> dict | None:
    target = (name or "").lower()
    for u in world["ad"]["users"]:
        if u["name"].lower() == target:
            return u
    return None


def _find_role(world: dict, role_id: str) -> dict | None:
    target = (role_id or "").lower()
    for r in world["roles"]:
        if r["id"].lower() == target or r["name"].lower() == target:
            return r
    return None


def _find_service(world: dict, name: str) -> dict | None:
    target = (name or "").lower()
    for s in world["services"]:
        if s["name"].lower() == target or s["display"].lower() == target:
            return s
    return None


def _find_update(world: dict, kb: str) -> dict | None:
    target = (kb or "").lower()
    for u in world["updates"]:
        if u["kb"].lower() == target:
            return u
    return None


def _group_exists(world: dict, name: str) -> bool:
    target = (name or "").lower()
    return any(g["name"].lower() == target for g in world["ad"]["groups"])


# ---------------------------------------------------------------------------
# Session lifecycle (mirrors the other engines)
# ---------------------------------------------------------------------------

def _ensure_session(session_id: str, scenario_slug: str = "") -> dict:
    key = str(session_id)
    entry = _load_session(key)
    if entry is None:
        world = _base_world()
        goal = _apply_preset(world, scenario_slug)
        state = {
            "scenario_slug": scenario_slug,
            "world": world,
            "goal": goal,
            "events": [],
        }
        entry = {"session_id": key, "scenario_slug": scenario_slug, "state": state,
                 "created_at": _now_iso()}
        _save_session(key, entry)
    return entry


def _event(state: dict, message: str) -> None:
    state.setdefault("events", []).insert(0, {"time": _now_iso(), "message": message})
    state["events"] = state["events"][:60]


# ---------------------------------------------------------------------------
# Wall-clock RDP / logon session lifecycle
#
# A signed-in interactive session idles and then auto-locks after
# SESSION_IDLE_LOCK_SECONDS of no activity (mirrors the "on resume, display logon
# screen" GPO / RDP idle limit). A disconnected RDP session is logged off after
# RDP_DISCONNECT_LOGOFF_SECONDS. Advanced on read/action so the lock screen and
# quser view reflect real elapsed time. Purely session-lifecycle + display —
# validators never inspect the session block, so grading is unaffected.
# ---------------------------------------------------------------------------

def _touch_session(world: dict, now: float | None = None) -> None:
    """Record activity: an active/idle/locked session becomes active again."""
    now = _now() if now is None else now
    sess = world.get("session", {})
    if sess.get("logged_in"):
        sess["last_activity"] = now
        if not sess.get("locked"):
            sess["state"] = "active"
    for r in world.get("rdp_sessions", []):
        if r.get("type") != "Services" and r.get("state") in ("Active", "Idle"):
            r["idle_seconds"] = 0
            r["state"] = "Active"


def _advance_session(world: dict, now: float | None = None) -> bool:
    """Advance the interactive-session lifecycle by wall-clock. Returns True if
    anything changed."""
    now = _now() if now is None else now
    changed = False
    sess = world.get("session")
    if sess and sess.get("logged_in") and not sess.get("locked"):
        last = sess.get("last_activity")
        if last is not None:
            idle = max(0.0, now - float(last))
            if idle >= SESSION_IDLE_LOCK_SECONDS:
                sess["locked"] = True
                sess["state"] = "locked"
                changed = True
            elif idle >= SESSION_IDLE_LOCK_SECONDS / 2 and sess.get("state") != "idle":
                sess["state"] = "idle"
                changed = True

    for r in world.get("rdp_sessions", []):
        if r.get("type") == "Services":
            continue
        logon_at = r.get("logon_at")
        if logon_at is not None:
            r["idle_seconds"] = int(max(0, now - float(logon_at)))
        if r.get("state") == "Disconnected":
            disc_at = r.get("disconnected_at")
            if disc_at is not None and now - float(disc_at) >= RDP_DISCONNECT_LOGOFF_SECONDS:
                r["state"] = "LoggedOff"
                changed = True
    return changed


def _overlay_vmware_bridge(world: dict, session_id: str) -> None:
    """Merge VMware hot-added disks into Windows Disk Management (offline until rescan)."""
    try:
        from apps.labs.provisioner.simulation.vmware_bridge import _load

        data = _load(str(session_id))
        disks = world.setdefault("storage", {}).setdefault("disks", [])
        known = {d.get("bridge_dev") for d in disks if d.get("bridge_dev")}
        for disk in data.get("pending", []):
            dev = disk.get("dev", "")
            if not dev or dev in known:
                continue
            disks.append({
                "id": f"bridge-{len(disks)}",
                "number": len(disks),
                "model": "VMware Virtual disk SCSI Disk Device",
                "size_gb": int(disk.get("size_gb") or 50),
                "partition_style": "RAW",
                "status": "Offline",
                "bus": "SCSI",
                "bridge_dev": dev,
                "requires_reboot": bool(disk.get("requires_reboot")),
                "visible": True,
            })
            known.add(dev)
        for dev in data.get("revealed", []):
            if dev in known:
                continue
            disks.append({
                "id": f"bridge-{len(disks)}",
                "number": len(disks),
                "model": "VMware Virtual disk SCSI Disk Device",
                "size_gb": 50,
                "partition_style": "RAW",
                "status": "Online",
                "bus": "SCSI",
                "bridge_dev": dev,
                "visible": True,
            })
            known.add(dev)
    except Exception:
        pass


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure_session(session_id, scenario_slug)
    # Advance the interactive-session lifecycle (idle-lock / RDP logoff) on read
    # so the lock screen reflects wall-clock time even with no action taken.
    if _advance_session(entry["state"]["world"]):
        _save_session(str(session_id), entry)
    state = copy.deepcopy(entry["state"])
    world = state["world"]
    _overlay_vmware_bridge(world, session_id)
    goal = state.get("goal", {})

    installed_roles = sum(1 for r in world["roles"] if r["installed"])
    pending_updates = sum(1 for u in world["updates"] if u["status"] != "installed")
    stopped_services = sum(1 for s in world["services"] if s["status"] != "running")

    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "computer_name": world["computer_name"],
        "os": world["os"],
        "domain": world["domain"],
        "roles": world["roles"],
        "ad": world["ad"],
        "updates": world["updates"],
        "services": world["services"],
        "session": world["session"],
        "rdp_sessions": world.get("rdp_sessions", []),
        "group_policy": world.get("group_policy", {}),
        "storage": world.get("storage", {}),
        "network": world.get("network", {}),
        "devices": world.get("devices", []),
        "explorer": world.get("explorer", {}),
        "settings": world.get("settings", {}),
        # Human-readable goal (objective/title) — never leaks the answer beyond
        # what the objective already tells the learner.
        "goal": {
            "kind": goal.get("kind"),
            "title": goal.get("title"),
            "objective": goal.get("objective"),
        },
        "events": state.get("events", []),
        "summary": {
            "computer_name": world["computer_name"],
            "domain": world["domain"]["name"] if world["domain"]["joined"] else "WORKGROUP",
            "domain_joined": world["domain"]["joined"],
            "roles_installed": installed_roles,
            "roles_total": len(world["roles"]),
            "ad_users": len(world["ad"]["users"]),
            "ad_groups": len(world["ad"]["groups"]),
            "updates_pending": pending_updates,
            "services_stopped": stopped_services,
            "title": goal.get("title", ""),
            "objective": goal.get("objective", ""),
        },
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


# ---------------------------------------------------------------------------
# Actions — the GUI verbs the learner performs to fix the world.
# Every handler returns {"ok": bool, ...}. Unknown actions never raise.
# ---------------------------------------------------------------------------

def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    payload.setdefault("session_id", str(session_id))
    entry = _load_session(str(session_id))
    if not entry:
        return {"ok": False, "error": "Windows Server simulation session not found"}
    state = entry["state"]
    world = state["world"]

    try:
        result = _dispatch(world, state, action, payload)
    except Exception as exc:  # never 500 — surface as a friendly error
        return {"ok": False, "error": f"action failed: {exc}"}

    if result.get("ok"):
        # A successful GUI action counts as session activity, so an admin who is
        # actively working won't idle-lock mid-task (login/lock/logout manage
        # their own state above and are skipped).
        if action not in ("login", "sign_in", "lock", "logout", "sign_out",
                          "disconnect_rdp", "disconnect_session"):
            _touch_session(world)
        _save_session(str(session_id), entry)
    return result


def _dispatch(world: dict, state: dict, action: str, payload: dict) -> dict:
    act = (action or "").strip()

    # Advance the wall-clock session lifecycle before handling the action so a
    # session that idle-locked between requests is seen in its current state.
    _advance_session(world)

    # ---- Login / lock screen gate (session lifecycle; not graded) ----
    if act in ("login", "sign_in"):
        now = _now()
        sess = world["session"]
        logon_type = "RemoteInteractive" if payload.get("rdp") else (
            payload.get("logon_type") or "Console")
        sess["logged_in"] = True
        sess["locked"] = False
        sess["state"] = "active"
        sess["login_at"] = now
        sess["last_activity"] = now
        sess["logon_type"] = logon_type
        if payload.get("user"):
            sess["current_user"] = payload["user"]
        # Register / refresh the interactive RDP/console session for quser view.
        user = sess["current_user"]
        rdp = world.setdefault("rdp_sessions", [])
        existing = next((r for r in rdp if r.get("user") == user and r.get("type") != "Services"), None)
        entry_r = existing or {"id": len(rdp)}
        entry_r.update({
            "user": user,
            "state": "Active",
            "type": logon_type,
            "client": payload.get("client") or ("rdp-client" if logon_type == "RemoteInteractive" else "console"),
            "idle_seconds": 0,
            "logon_at": now,
        })
        entry_r.pop("disconnected_at", None)
        if existing is None:
            rdp.append(entry_r)
        _event(state, f"{user} signed in ({logon_type})")
        return {"ok": True, "message": "Signed in"}

    if act in ("lock",):
        world["session"]["locked"] = True
        world["session"]["state"] = "locked"
        _event(state, "Workstation locked")
        return {"ok": True, "message": "Workstation locked"}

    if act in ("unlock", "unlock_session"):
        world["session"]["locked"] = False
        world["session"]["logged_in"] = True
        world["session"]["state"] = "active"
        world["session"]["last_activity"] = _now()
        _touch_session(world)
        _event(state, "Workstation unlocked")
        return {"ok": True, "message": "Workstation unlocked"}

    if act in ("disconnect_rdp", "disconnect_session"):
        # RDP disconnect leaves the session running-but-disconnected; it logs off
        # after RDP_DISCONNECT_LOGOFF_SECONDS (see _advance_session).
        now = _now()
        target = payload.get("user") or world["session"].get("current_user")
        found = False
        for r in world.get("rdp_sessions", []):
            if r.get("type") != "Services" and r.get("user") == target and r.get("state") in ("Active", "Idle"):
                r["state"] = "Disconnected"
                r["disconnected_at"] = now
                found = True
        world["session"]["state"] = "disconnected"
        _event(state, f"RDP session for {target} disconnected")
        return {"ok": found, "message": "RDP session disconnected" if found
                else "No active RDP session to disconnect"}

    if act in ("logout", "sign_out"):
        sess = world["session"]
        user = sess.get("current_user")
        sess["logged_in"] = False
        sess["locked"] = False
        sess["state"] = "logged_off"
        sess["login_at"] = None
        sess["last_activity"] = None
        # Drop the interactive session (keeps the always-present Services row).
        world["rdp_sessions"] = [
            r for r in world.get("rdp_sessions", [])
            if r.get("type") == "Services" or r.get("user") != user
        ]
        _event(state, "Administrator signed out")
        return {"ok": True, "message": "Signed out"}

    # ---- Server Manager: roles & features ----
    if act in ("install_role", "install_feature", "add_role"):
        role_id = payload.get("role") or payload.get("role_id") or payload.get("name")
        role = _find_role(world, role_id)
        if not role:
            return {"ok": False, "error": f"Unknown role or feature '{role_id}'"}
        if role["installed"]:
            return {"ok": True, "message": f"{role['name']} is already installed"}
        role["installed"] = True
        _event(state, f"Installed role/feature: {role['name']}")
        return {"ok": True, "message": f"Installed {role['name']}"}

    if act in ("uninstall_role", "remove_role", "uninstall_feature"):
        role_id = payload.get("role") or payload.get("role_id") or payload.get("name")
        role = _find_role(world, role_id)
        if not role:
            return {"ok": False, "error": f"Unknown role or feature '{role_id}'"}
        if not role["installed"]:
            return {"ok": True, "message": f"{role['name']} is not installed"}
        role["installed"] = False
        _event(state, f"Removed role/feature: {role['name']}")
        return {"ok": True, "message": f"Removed {role['name']}"}

    if act in ("configure_dns", "configure_dhcp"):
        # Post-install configuration only succeeds if the role is present.
        role_id = "DNS" if act == "configure_dns" else "DHCP"
        role = _find_role(world, role_id)
        if not role or not role["installed"]:
            return {"ok": False,
                    "error": f"{role_id} role is not installed — install it first"}
        role.setdefault("configured", True)
        role["configured"] = True
        _event(state, f"Configured {role['name']}")
        return {"ok": True, "message": f"Configured {role['name']}"}

    # ---- Active Directory Users and Computers ----
    if act in ("create_ad_user", "new_ad_user"):
        name = (payload.get("name") or payload.get("user") or "").strip()
        if not name:
            return {"ok": False, "error": "A username is required"}
        if _find_user(world, name):
            return {"ok": False, "error": f"User '{name}' already exists"}
        groups_in = payload.get("groups")
        if isinstance(groups_in, list) and groups_in:
            groups = [str(g).strip() for g in groups_in if str(g).strip()]
        else:
            groups = []
        group = (payload.get("group") or (groups[0] if groups else "") or "Domain Users").strip()
        if group and group not in groups:
            groups = [group, *groups]
        if not groups:
            groups = [group]
        if "Domain Users" not in groups:
            groups.append("Domain Users")
        world["ad"]["users"].append(_user(
            name,
            display=payload.get("display") or name,
            enabled=bool(payload.get("enabled", True)),
            group=group,
            groups=groups,
            ou=payload.get("ou") or "Users",
            must_change_pw=bool(payload.get("must_change_pw", payload.get("mustChange", False))),
        ))
        _event(state, f"Created AD user: {name}")
        return {"ok": True, "message": f"Created user {name}"}

    if act in ("enable_ad_user", "enable_user"):
        user = _find_user(world, payload.get("user") or payload.get("name"))
        if not user:
            return {"ok": False, "error": "User not found"}
        user["enabled"] = True
        _event(state, f"Enabled account: {user['name']}")
        return {"ok": True, "message": f"Enabled {user['name']}"}

    if act in ("disable_ad_user", "disable_user"):
        user = _find_user(world, payload.get("user") or payload.get("name"))
        if not user:
            return {"ok": False, "error": "User not found"}
        user["enabled"] = False
        _event(state, f"Disabled account: {user['name']}")
        return {"ok": True, "message": f"Disabled {user['name']}"}

    if act in ("unlock_ad_user", "unlock_user", "unlock_account"):
        user = _find_user(world, payload.get("user") or payload.get("name"))
        if not user:
            return {"ok": False, "error": "User not found"}
        user["locked"] = False
        _event(state, f"Unlocked account: {user['name']}")
        return {"ok": True, "message": f"Unlocked {user['name']}"}

    if act in ("reset_password", "reset_ad_password"):
        user = _find_user(world, payload.get("user") or payload.get("name"))
        if not user:
            return {"ok": False, "error": "User not found"}
        user["must_change_pw"] = bool(payload.get("must_change_pw", True))
        # Resetting a password also clears a lockout, like the real ADUC dialog.
        user["locked"] = False
        _event(state, f"Reset password for {user['name']}")
        return {"ok": True, "message": f"Reset password for {user['name']}"}

    if act in ("add_user_to_group", "add_to_group"):
        user = _find_user(world, payload.get("user") or payload.get("name"))
        group = payload.get("group")
        if not user:
            return {"ok": False, "error": "User not found"}
        if not group or not _group_exists(world, group):
            return {"ok": False, "error": f"Unknown group '{group}'"}
        # Canonicalize to the stored group casing.
        canon = next(g["name"] for g in world["ad"]["groups"]
                     if g["name"].lower() == group.lower())
        if canon in user["groups"]:
            return {"ok": True, "message": f"{user['name']} is already in {canon}"}
        user["groups"].append(canon)
        _event(state, f"Added {user['name']} to {canon}")
        return {"ok": True, "message": f"Added {user['name']} to {canon}"}

    if act in ("remove_user_from_group", "remove_from_group"):
        user = _find_user(world, payload.get("user") or payload.get("name"))
        group = payload.get("group")
        if not user:
            return {"ok": False, "error": "User not found"}
        if not group:
            return {"ok": False, "error": "A group is required"}
        before = len(user["groups"])
        user["groups"] = [g for g in user["groups"] if g.lower() != group.lower()]
        if len(user["groups"]) == before:
            return {"ok": True, "message": f"{user['name']} was not in {group}"}
        _event(state, f"Removed {user['name']} from {group}")
        return {"ok": True, "message": f"Removed {user['name']} from {group}"}

    # ---- Windows Update ----
    if act in ("install_update", "retry_update", "install_updates"):
        kb = payload.get("kb") or payload.get("update")
        if kb:
            upd = _find_update(world, kb)
            if not upd:
                return {"ok": False, "error": f"Update '{kb}' not found"}
            targets = [upd]
        else:
            # No KB given -> install every pending/failed update (Install all).
            targets = [u for u in world["updates"] if u["status"] != "installed"]
            if not targets:
                return {"ok": True, "message": "No pending updates"}
        for upd in targets:
            upd["status"] = "installed"
            upd["error_code"] = ""
            _event(state, f"Installed update {upd['kb']}")
        names = ", ".join(u["kb"] for u in targets)
        return {"ok": True, "message": f"Installed {names}"}

    if act in ("check_updates", "scan_updates"):
        pending = [u["kb"] for u in world["updates"] if u["status"] != "installed"]
        _event(state, "Checked for updates")
        return {"ok": True, "message": "Checked for updates",
                "pending": pending}

    # ---- Services console ----
    if act in ("start_service",):
        svc = _find_service(world, payload.get("service") or payload.get("name"))
        if not svc:
            return {"ok": False, "error": "Service not found"}
        if svc["startup"] == "disabled":
            return {"ok": False,
                    "error": (f"Cannot start {svc['display']}: its startup type is "
                              "Disabled. Set startup to Automatic or Manual first.")}
        svc["status"] = "running"
        _event(state, f"Started service: {svc['display']}")
        return {"ok": True, "message": f"Started {svc['display']}"}

    if act in ("stop_service",):
        svc = _find_service(world, payload.get("service") or payload.get("name"))
        if not svc:
            return {"ok": False, "error": "Service not found"}
        svc["status"] = "stopped"
        _event(state, f"Stopped service: {svc['display']}")
        return {"ok": True, "message": f"Stopped {svc['display']}"}

    if act in ("restart_service",):
        svc = _find_service(world, payload.get("service") or payload.get("name"))
        if not svc:
            return {"ok": False, "error": "Service not found"}
        if svc["startup"] == "disabled":
            return {"ok": False,
                    "error": f"Cannot start {svc['display']}: startup type is Disabled."}
        svc["status"] = "running"
        _event(state, f"Restarted service: {svc['display']}")
        return {"ok": True, "message": f"Restarted {svc['display']}"}

    if act in ("set_startup", "set_service_startup"):
        svc = _find_service(world, payload.get("service") or payload.get("name"))
        startup = (payload.get("startup") or payload.get("startup_type") or "").lower()
        if not svc:
            return {"ok": False, "error": "Service not found"}
        if startup not in _STARTUP_TYPES:
            return {"ok": False,
                    "error": f"Startup type must be one of {', '.join(_STARTUP_TYPES)}"}
        svc["startup"] = startup
        _event(state, f"Set {svc['display']} startup to {startup}")
        return {"ok": True, "message": f"Set {svc['display']} startup to {startup}"}

    # ---- System Properties: domain join ----
    if act in ("join_domain",):
        domain = (payload.get("domain") or DEFAULT_DOMAIN).strip()
        if not domain:
            return {"ok": False, "error": "A domain name is required"}
        world["domain"]["joined"] = True
        world["domain"]["name"] = domain
        world["domain"]["netbios"] = (domain.split(".")[0] or "CORP").upper()
        world["domain"].setdefault("dcs", [DEFAULT_DC])
        # Joining the domain brings Netlogon online.
        net = _find_service(world, "Netlogon")
        if net:
            net["status"] = "running"
        _event(state, f"Joined domain {domain}")
        return {"ok": True,
                "message": f"Joined {domain}. A restart is required to complete the join."}

    if act in ("leave_domain", "unjoin_domain"):
        world["domain"]["joined"] = False
        world["domain"]["name"] = ""
        world["domain"]["netbios"] = ""
        _event(state, "Left the domain (joined WORKGROUP)")
        return {"ok": True, "message": "Left the domain"}

    if act in ("rename_computer",):
        new_name = (payload.get("name") or payload.get("computer_name") or "").strip()
        if not new_name:
            return {"ok": False, "error": "A computer name is required"}
        world["computer_name"] = new_name
        _event(state, f"Renamed computer to {new_name}")
        return {"ok": True, "message": f"Renamed to {new_name}"}

    # ---- Group Policy Management ----
    if act in ("create_gpo", "new_gpo"):
        gp = world.setdefault("group_policy", {"forest": DEFAULT_DOMAIN, "gpos": [], "containers": []})
        name = (payload.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "A GPO name is required"}
        if _find_gpo(world, name):
            return {"ok": False, "error": f"GPO '{name}' already exists"}
        gid = (payload.get("id") or name.lower().replace(" ", "-"))[:48]
        gp["gpos"].append(_gpo(gid, name, links=[]))
        _event(state, f"Created GPO: {name}")
        return {"ok": True, "message": f"Created GPO {name}", "gpo_id": gid}

    if act in ("delete_gpo", "remove_gpo"):
        gpo = _find_gpo(world, payload.get("gpo") or payload.get("id") or payload.get("name"))
        if not gpo:
            return {"ok": False, "error": "GPO not found"}
        if gpo["id"] == "default-domain-policy":
            return {"ok": False, "error": "Cannot delete the Default Domain Policy"}
        gp = world.get("group_policy", {})
        gp["gpos"] = [g for g in gp.get("gpos", []) if g["id"] != gpo["id"]]
        _event(state, f"Deleted GPO: {gpo['name']}")
        return {"ok": True, "message": f"Deleted GPO {gpo['name']}"}

    if act in ("update_gpo_setting", "edit_gpo_setting"):
        gpo = _find_gpo(world, payload.get("gpo") or payload.get("id"))
        if not gpo:
            return {"ok": False, "error": "GPO not found"}
        key = (payload.get("key") or "").strip()
        if not key:
            return {"ok": False, "error": "A setting key is required"}
        for s in gpo["settings"]:
            if s["key"].lower() == key.lower():
                if "value" in payload:
                    s["value"] = str(payload["value"])
                if "enabled" in payload:
                    s["enabled"] = bool(payload["enabled"])
                _event(state, f"Updated GPO setting '{key}' on {gpo['name']}")
                return {"ok": True, "message": f"Updated {key}"}
        gpo["settings"].append(_gpo_setting(
            key, str(payload.get("value") or ""), enabled=bool(payload.get("enabled", True)),
            category=str(payload.get("category") or "Custom"),
        ))
        _event(state, f"Added GPO setting '{key}' to {gpo['name']}")
        return {"ok": True, "message": f"Added setting {key}"}

    if act in ("link_gpo", "link_gpo_ou"):
        gpo = _find_gpo(world, payload.get("gpo") or payload.get("id"))
        ou = (payload.get("ou") or payload.get("path") or DEFAULT_DOMAIN).strip()
        if not gpo:
            return {"ok": False, "error": "GPO not found"}
        if ou not in gpo["links"]:
            gpo["links"].append(ou)
        _event(state, f"Linked GPO {gpo['name']} to {ou}")
        return {"ok": True, "message": f"Linked {gpo['name']} to {ou}"}

    if act in ("unlink_gpo", "unlink_gpo_ou"):
        gpo = _find_gpo(world, payload.get("gpo") or payload.get("id"))
        ou = (payload.get("ou") or payload.get("path") or "").strip()
        if not gpo:
            return {"ok": False, "error": "GPO not found"}
        gpo["links"] = [l for l in gpo.get("links", []) if l.lower() != ou.lower()]
        _event(state, f"Unlinked GPO {gpo['name']} from {ou}")
        return {"ok": True, "message": f"Unlinked {gpo['name']}"}

    if act in ("toggle_gpo", "enable_gpo", "disable_gpo"):
        gpo = _find_gpo(world, payload.get("gpo") or payload.get("id"))
        if not gpo:
            return {"ok": False, "error": "GPO not found"}
        if act == "enable_gpo":
            gpo["status"] = "Enabled"
        elif act == "disable_gpo":
            gpo["status"] = "Disabled"
        else:
            gpo["status"] = "Disabled" if gpo.get("status") == "Enabled" else "Enabled"
        _event(state, f"Set GPO {gpo['name']} to {gpo['status']}")
        return {"ok": True, "message": f"GPO {gpo['name']} is now {gpo['status']}"}

    if act in ("rescan_disks", "rescan_storage"):
        try:
            from apps.labs.provisioner.simulation.vmware_bridge import consume_revealed_disks

            revealed = consume_revealed_disks(str(payload.get("session_id") or ""))
        except Exception:
            revealed = []
        disks = world.setdefault("storage", {}).setdefault("disks", [])
        for disk in disks:
            if disk.get("bridge_dev") and not disk.get("visible"):
                if not disk.get("requires_reboot") or payload.get("after_reboot"):
                    disk["visible"] = True
                    disk["status"] = "Online"
        for rd in revealed:
            dev = rd.get("dev")
            if not any(d.get("bridge_dev") == dev for d in disks):
                disks.append({
                    "id": f"bridge-{len(disks)}",
                    "number": len(disks),
                    "model": "VMware Virtual disk SCSI Disk Device",
                    "size_gb": int(rd.get("size_gb") or 50),
                    "partition_style": "RAW",
                    "status": "Online",
                    "bus": "SCSI",
                    "bridge_dev": dev,
                    "visible": True,
                })
        _event(state, "Rescanned disks — new volumes may appear in Disk Management")
        return {"ok": True, "message": "Disk rescan complete", "revealed": len(revealed)}

    if act in ("initialize_disk",):
        disk_id = payload.get("disk_id") or payload.get("id")
        disk = next((d for d in world.get("storage", {}).get("disks", []) if d.get("id") == disk_id), None)
        if not disk:
            return {"ok": False, "error": "Disk not found"}
        if disk.get("partition_style") not in ("RAW", ""):
            return {"ok": True, "message": f"Disk {disk_id} is already initialized"}
        disk["partition_style"] = payload.get("style") or "GPT"
        disk["status"] = "Online"
        _event(state, f"Initialized disk {disk.get('number', disk_id)} as {disk['partition_style']}")
        return {"ok": True, "message": "Disk initialized", "disk": disk}

    if act in ("create_volume", "new_volume"):
        letter = (payload.get("letter") or "D:").strip().upper()
        if not letter.endswith(":"):
            letter = f"{letter}:"
        label = (payload.get("label") or "New Volume").strip()
        size_gb = int(payload.get("size_gb") or 50)
        disk_id = payload.get("disk_id")
        volumes = world.setdefault("storage", {}).setdefault("volumes", [])
        if any(v.get("letter", "").upper() == letter for v in volumes):
            return {"ok": False, "error": f"Drive letter {letter} is already in use"}
        vol = {
            "letter": letter,
            "label": label,
            "fs": payload.get("fs") or "NTFS",
            "size_gb": size_gb,
            "free_gb": size_gb,
            "health": "Healthy",
            "disk_id": disk_id,
        }
        volumes.append(vol)
        explorer = world.setdefault("explorer", {})
        drives = explorer.setdefault("drives", [])
        path = f"{letter}\\"
        if not any(d.get("path") == path for d in drives):
            drives.append({"path": path, "label": label, "type": "Local Disk"})
        _event(state, f"Created volume {letter} ({label})")
        return {"ok": True, "message": f"Volume {letter} created", "volume": vol}

    if act in ("set_adapter_ip", "configure_adapter"):
        adapter_id = payload.get("adapter_id") or payload.get("id")
        adapters = world.get("network", {}).get("adapters", [])
        adapter = next((a for a in adapters if a.get("id") == adapter_id), None)
        if not adapter:
            return {"ok": False, "error": "Network adapter not found"}
        if payload.get("dhcp"):
            adapter["dhcp"] = True
            adapter["ipv4"] = ""
            adapter["mask"] = ""
            adapter["gw"] = ""
        else:
            adapter["dhcp"] = False
            adapter["ipv4"] = (payload.get("ipv4") or adapter.get("ipv4") or "").strip()
            adapter["mask"] = (payload.get("mask") or adapter.get("mask") or "255.255.255.0").strip()
            adapter["gw"] = (payload.get("gw") or adapter.get("gw") or "").strip()
            if payload.get("dns"):
                adapter["dns"] = payload["dns"]
        adapter["status"] = "Connected" if adapter.get("ipv4") or adapter.get("dhcp") else adapter.get("status")
        _event(state, f"Updated network settings for {adapter.get('name')}")
        return {"ok": True, "message": "Network adapter updated", "adapter": adapter}

    if act in ("scan_devices", "refresh_devices"):
        _event(state, "Refreshed Device Manager")
        return {"ok": True, "message": "Device scan complete", "devices": world.get("devices", [])}

    if act in ("reset",):
        # Re-break the world from the preset (a fresh start for the learner).
        slug = state.get("scenario_slug", "")
        new_world = _base_world()
        state["goal"] = _apply_preset(new_world, slug)
        state["world"] = new_world
        state["events"] = []
        _event(state, "Lab reset to its initial state")
        # _save handled by caller because ok is True.
        # Replace the live reference so the caller persists the reset world.
        world.clear()
        world.update(new_world)
        return {"ok": True, "message": "Lab reset"}

    return {"ok": False, "error": f"unknown action: {action}"}


# ---------------------------------------------------------------------------
# Validation — grade purely on the live world vs the scenario goal.
# A fresh (broken) session fails; the intended fix flips it to pass.
# ---------------------------------------------------------------------------

def validate_windows_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load_session(str(session_id)) or _ensure_session(session_id, scenario_slug)
    state = entry["state"]
    world = state["world"]
    goal = state.get("goal") or {}
    kind = goal.get("kind")
    req = goal.get("require", {})

    if kind == "ad_user_active":
        user = _find_user(world, goal.get("target_user"))
        if not user:
            return False, f"User {goal.get('target_user')} not found"
        if user["locked"] != req.get("locked", False):
            return False, (f"{user['name']} is still locked out — unlock the account "
                           "in Active Directory Users and Computers.")
        if user["enabled"] != req.get("enabled", True):
            return False, (f"{user['name']} is still disabled — enable the account "
                           "in Active Directory Users and Computers.")
        return True, (f"{user['name']} is unlocked and enabled — the account can sign "
                      "in again. Validation passed.")

    if kind == "ad_group_member":
        user = _find_user(world, goal.get("target_user"))
        group = goal.get("target_group")
        if not user:
            return False, f"User {goal.get('target_user')} not found"
        members = [g.lower() for g in user.get("groups", [])]
        if (group or "").lower() not in members:
            return False, (f"{user['name']} is not yet a member of '{group}'. Add the "
                           "user to that group in Active Directory Users and Computers.")
        return True, (f"{user['name']} is now a member of '{group}' — validation passed.")

    if kind == "role_installed":
        role = _find_role(world, goal.get("target_role"))
        if not role:
            return False, f"Role {goal.get('target_role')} not found"
        if not role["installed"]:
            return False, (f"The {role['name']} role is not installed yet — use Add "
                           "Roles and Features in Server Manager to install it.")
        return True, (f"The {role['name']} role is installed — validation passed.")

    if kind == "update_installed":
        upd = _find_update(world, goal.get("target_kb"))
        if not upd:
            return False, f"Update {goal.get('target_kb')} not found"
        if upd["status"] != "installed":
            return False, (f"{upd['kb']} is still '{upd['status']}' — retry the failed "
                           "update in Windows Update so it installs.")
        return True, (f"{upd['kb']} installed successfully — validation passed.")

    if kind == "service_running":
        svc = _find_service(world, goal.get("target_service"))
        if not svc:
            return False, f"Service {goal.get('target_service')} not found"
        if svc["status"] != req.get("status", "running"):
            return False, (f"The {svc['display']} service is still {svc['status']} — "
                           "start it in the Services console.")
        if req.get("startup") and svc["startup"] != req["startup"]:
            return False, (f"Set {svc['display']}'s startup type to "
                           f"{req['startup'].title()} so it starts after a reboot.")
        return True, (f"The {svc['display']} service is running and set to "
                      f"{svc['startup'].title()} — validation passed.")

    if kind == "domain_joined":
        dom = world["domain"]
        if not dom.get("joined"):
            return False, ("The server is still in WORKGROUP — join it to the "
                           f"'{goal.get('target_domain')}' domain in System Properties.")
        want = (goal.get("target_domain") or "").lower()
        if want and (dom.get("name") or "").lower() != want:
            return False, (f"The server joined '{dom.get('name')}' but the goal domain "
                           f"is '{goal.get('target_domain')}'.")
        return True, (f"The server is joined to {dom.get('name')} — validation passed.")

    return False, "No validation goal configured for this scenario"
