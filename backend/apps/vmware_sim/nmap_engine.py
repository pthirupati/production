"""
In-memory Nmap network-scanning simulator for training labs.

Models a realistic virtual /24 network so a learner can run nmap-style scans
from an in-app console and observe results that are *consistent* with the
underlying inventory and the flags they pass:

  - Host discovery (ping sweep) reveals which hosts are live; a host behind the
    firewall that drops ICMP/SYN probes only shows up with -Pn (treat-as-online)
    or a privileged SYN scan (-sS, needs sudo).
  - Port scans report open/closed/filtered states. A firewall can silently DROP
    SYN packets to protected ports, so they appear `filtered` unless the learner
    uses the right technique.
  - -sV performs service/version detection (banner grab) and reveals product +
    version strings that a plain port scan does not.
  - -O performs OS fingerprinting, which requires raw packets (sudo) to read.

The engine tracks everything the learner has *discovered* in session state, and
validate_nmap_lab grades the lab by checking the learner discovered the required
fact via an appropriate scan — never by inspecting the ground-truth inventory
directly. A fresh session always fails validation; only the intended scan
sequence flips it to pass.

Sessions live in the Django cache (Redis in production) for multi-worker safety,
mirroring the VMware / K8s / Docker / monitoring engines (SESSION_TTL=7200).
"""

from __future__ import annotations

import copy
import ipaddress
import json
import random
import re
import time
from typing import Any

from django.core.cache import cache

SESSION_TTL = 7200  # 2-hour TTL matching the other simulator engines

# Wall-clock delay (seconds) before a service state change a learner makes
# (stop/start a listener) is reflected by the network. Stopping a daemon does
# not instantly tear the socket down — connections drain and the kernel stops
# accepting new SYNs a moment later — so a port a learner "closes" keeps reading
# `open` on a scan run immediately after, then flips to `closed` on a re-scan
# once the transition has elapsed. Kept short so the effect is observable within
# a single lab sitting. This mirrors the baremetal/monitoring wall-clock pattern.
PORT_TRANSITION_SECONDS = 8


def _session_key(session_id: str) -> str:
    return f"nmap_session:{session_id}"


def _load_session(session_id: str) -> dict | None:
    data = cache.get(_session_key(str(session_id)))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def _save_session(session_id: str, entry: dict) -> None:
    cache.set(_session_key(str(session_id)), json.dumps(entry, default=str), SESSION_TTL)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now() -> float:
    return time.time()


# ---------------------------------------------------------------------------
# Ground-truth virtual network (the "real" topology the scanner probes).
# The learner never sees this directly — only what their scans reveal.
# ---------------------------------------------------------------------------

SUBNET = "10.10.10.0/24"
GATEWAY = "10.10.10.1"


def _port(number: int, state: str, service: str, version: str = "",
          product: str = "", proto: str = "tcp") -> dict:
    """A single ground-truth port on a host.

    state here is the *intrinsic* state (open|closed). Whether the learner sees
    it as open/closed/filtered is derived per-scan from the firewall + flags.
    """
    return {
        "port": number,
        "proto": proto,
        "state": state,            # intrinsic: open | closed
        "service": service,
        "product": product,
        "version": version,
        # banner/version only revealed by -sV; OS only revealed by -O+sudo.
    }


def _host(ip: str, hostname: str, mac: str, vendor: str, os_name: str,
          os_family: str, ports: list[dict], *,
          live: bool = True,
          icmp_blocked: bool = False,
          firewalled: bool = False) -> dict:
    """A ground-truth host.

    - live: the host actually exists / is powered on.
    - icmp_blocked: host drops ICMP echo (so a plain -sn ping sweep misses it;
      needs -Pn or a SYN probe to a known port).
    - firewalled: a stateful firewall in front of this host DROPs unsolicited
      SYN packets to its *protected* ports, so they read `filtered` on an
      unprivileged scan and only resolve with -sS (sudo) or after the learner
      treats the host as up with -Pn and probes specific ports.
    """
    return {
        "ip": ip,
        "hostname": hostname,
        "mac": mac,
        "vendor": vendor,
        "os": os_name,
        "os_family": os_family,
        "live": live,
        "icmp_blocked": icmp_blocked,
        "firewalled": firewalled,
        "ports": ports,
    }


def _base_inventory() -> dict:
    """The realistic /24 used by every scenario; presets tweak per-scenario flags."""
    return {
        "subnet": SUBNET,
        "gateway": GATEWAY,
        "scanner_ip": "10.10.10.250",
        # A network-edge firewall description shown in the UI topology panel.
        "firewall": {
            "name": "edge-fw-01",
            "ip": "10.10.10.254",
            "policy": "default-deny inbound; drops unsolicited SYN to protected hosts",
            "drops_icmp": True,
        },
        "hosts": [
            _host(
                "10.10.10.1", "gw.lab.local", "00:0c:29:3a:11:01", "Cisco Systems",
                "Cisco IOS 15.2", "ios",
                [
                    _port(22, "open", "ssh", "Cisco SSH 1.25", "Cisco SSH"),
                    _port(80, "open", "http", "Cisco IOS http config", "Cisco IOS httpd"),
                    _port(443, "closed", "https"),
                ],
            ),
            _host(
                "10.10.10.10", "web01.lab.local", "00:0c:29:3a:11:0a", "VMware, Inc.",
                "Ubuntu 22.04 (Linux 5.15)", "linux",
                [
                    _port(22, "open", "ssh", "OpenSSH 8.9p1 Ubuntu 3", "OpenSSH"),
                    _port(80, "open", "http", "nginx 1.18.0", "nginx"),
                    _port(443, "open", "https", "nginx 1.18.0", "nginx"),
                    _port(3306, "closed", "mysql"),
                ],
            ),
            _host(
                "10.10.10.20", "db01.lab.local", "00:0c:29:3a:11:14", "VMware, Inc.",
                "Debian 12 (Linux 6.1)", "linux",
                [
                    _port(22, "open", "ssh", "OpenSSH 9.2p1 Debian 2", "OpenSSH"),
                    # The DB port lives behind the firewall — filtered until -sS/sudo.
                    _port(5432, "open", "postgresql", "PostgreSQL 15.3", "PostgreSQL DB"),
                    _port(8080, "closed", "http-proxy"),
                ],
                firewalled=True,
            ),
            _host(
                "10.10.10.30", "win-app01.lab.local", "00:0c:29:3a:11:1e", "Microsoft Corp.",
                "Windows Server 2019", "windows",
                [
                    _port(135, "open", "msrpc", "Microsoft Windows RPC", "Microsoft Windows RPC"),
                    _port(139, "open", "netbios-ssn", "Microsoft Windows netbios-ssn"),
                    _port(445, "open", "microsoft-ds", "Windows Server 2019 microsoft-ds"),
                    _port(3389, "open", "ms-wbt-server", "Microsoft Terminal Services"),
                ],
            ),
            _host(
                # The "hidden" host: powered on but drops ICMP. A -sn ping sweep
                # misses it; needs -Pn (or a SYN probe) to be discovered.
                "10.10.10.40", "bastion.lab.local", "00:0c:29:3a:11:28", "VMware, Inc.",
                "Alpine Linux 3.18", "linux",
                [
                    _port(22, "open", "ssh", "OpenSSH 9.3 (Alpine)", "OpenSSH"),
                    _port(8443, "open", "https-alt", "HAProxy 2.8", "HAProxy"),
                ],
                icmp_blocked=True,
            ),
            _host(
                # A dead/unassigned address: never live, useful as a negative.
                "10.10.10.99", "", "", "", "", "unknown",
                [],
                live=False,
            ),
        ],
    }


# ---------------------------------------------------------------------------
# Scan flag parsing
# ---------------------------------------------------------------------------

_FLAG_TOKENS = {
    "-sn": "ping_sweep",      # host discovery only, no port scan
    "-sP": "ping_sweep",      # legacy alias
    "-sS": "syn_scan",        # TCP SYN (half-open) scan — needs raw sockets (sudo)
    "-sT": "connect_scan",    # TCP connect() scan — works unprivileged
    "-sV": "version",         # service/version detection
    "-O": "os_detect",        # OS fingerprinting — needs raw sockets (sudo)
    "-A": "aggressive",       # enables -sV and -O (and more)
    "-Pn": "no_ping",         # treat all hosts as online (skip host discovery)
}


def _parse_flags(flags: Any) -> dict:
    """Normalise a flag list/string into a capabilities dict.

    Recognises -sn/-sS/-sT/-sV/-O/-A/-Pn and `-p <spec>` (also `-p<spec>`).
    Unknown tokens are ignored so realistic command lines still parse.
    """
    if isinstance(flags, (list, tuple)):
        tokens = [str(t) for t in flags]
    else:
        tokens = str(flags or "").split()

    caps = {
        "ping_sweep": False,
        "syn_scan": False,
        "connect_scan": False,
        "version": False,
        "os_detect": False,
        "aggressive": False,
        "no_ping": False,
        "ports": None,   # None => default top-ports; list[int] => explicit
        "fast": False,   # -F  fast (fewer ports) scan
        "all_ports": False,  # -p 1-65535 / -p-  (full 65535-port sweep)
        "timing": 3,     # -T<0-5> template; nmap default is T3 ("normal")
    }

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        # -p 22,80  OR  -p22,80  OR  -p1-100  OR  -p-  (all ports)
        if tok == "-p" and i + 1 < len(tokens):
            caps["ports"] = _parse_ports(tokens[i + 1])
            if _is_all_ports_spec(tokens[i + 1]):
                caps["all_ports"] = True
            i += 2
            continue
        if tok.startswith("-p") and len(tok) > 2:
            caps["ports"] = _parse_ports(tok[2:])
            if _is_all_ports_spec(tok[2:]):
                caps["all_ports"] = True
            i += 1
            continue
        if tok == "-F":
            caps["fast"] = True
            i += 1
            continue
        # -T0 .. -T5 (paranoid .. insane). Accept "-T4" and legacy word forms.
        tm = re.match(r"^-T([0-5])$", tok)
        if tm:
            caps["timing"] = int(tm.group(1))
            i += 1
            continue
        key = _FLAG_TOKENS.get(tok)
        if key:
            caps[key] = True
        i += 1

    if caps["aggressive"]:
        caps["version"] = True
        caps["os_detect"] = True
    return caps


def _parse_ports(spec: str) -> list[int]:
    out: list[int] = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        # bare "-" or "1-" / "-1024" => nmap "all/open-ended range" shorthand.
        if part == "-":
            continue
        m = re.match(r"^(\d+)-(\d+)$", part)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if hi - lo <= 2000:  # guard against silly ranges (keeps enum loop cheap)
                out.extend(range(lo, hi + 1))
        elif part.isdigit():
            out.append(int(part))
    return sorted(set(out))


def _is_all_ports_spec(spec: str) -> bool:
    """True when the port spec covers (essentially) the whole 65535-port range.

    Recognises `-p-`, `-p 1-65535`, and equivalent wide ranges so the timing
    model can charge the learner for a full-range sweep even though the enum
    loop itself only walks the known ground-truth ports.
    """
    s = str(spec or "").strip()
    if s in ("-", "0-", "1-"):
        return True
    m = re.match(r"^(\d+)-(\d+)$", s)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return (hi - lo) >= 60000
    return False


def _intended_port_count(caps: dict) -> int:
    """How many ports the scan *intends* to probe, for the timing estimate.

    - explicit -p list          -> its length
    - full-range (-p-/1-65535)  -> 65535
    - -F fast scan              -> ~100 (nmap's fast top-ports set)
    - default                   -> len(_DEFAULT_TOP_PORTS) mapped to nmap's ~1000
    """
    if caps.get("all_ports"):
        return 65535
    ports = caps.get("ports")
    if ports:
        return len(ports)
    if caps.get("fast"):
        return 100
    # Default nmap scans the top ~1000 ports; our engine walks a representative
    # subset, but the wall-clock feel should reflect the ~1000-port default.
    return 1000


# Default "top ports" nmap probes when -p is not given (a representative subset).
_DEFAULT_TOP_PORTS = [21, 22, 23, 25, 80, 110, 135, 139, 143, 443, 445,
                      993, 995, 1723, 3306, 3389, 5432, 5900, 8080, 8443]


# ---------------------------------------------------------------------------
# Target expansion
# ---------------------------------------------------------------------------

def _expand_targets(targets: Any, inv: dict) -> list[str]:
    """Resolve a target spec into a list of candidate IPs in our subnet.

    Accepts a single IP, a CIDR (10.10.10.0/24), a hyphen range
    (10.10.10.1-50), a hostname, or 'all'/'*'. Limited to our /24.
    """
    if isinstance(targets, (list, tuple)):
        out: list[str] = []
        for t in targets:
            out.extend(_expand_targets(t, inv))
        return sorted(set(out), key=_ip_sort_key)

    spec = str(targets or "").strip()
    net = ipaddress.ip_network(inv["subnet"], strict=False)
    all_ips = [str(ip) for ip in net.hosts()]

    if not spec or spec in ("all", "*", inv["subnet"]):
        return all_ips

    # hostname?
    for h in inv["hosts"]:
        if h.get("hostname") and h["hostname"] == spec:
            return [h["ip"]]

    # CIDR
    if "/" in spec:
        try:
            sub = ipaddress.ip_network(spec, strict=False)
            return [str(ip) for ip in sub.hosts() if ip in net]
        except ValueError:
            return []

    # last-octet range: 10.10.10.1-50  or  10.10.10.1-10.10.10.50
    m = re.match(r"^(\d+\.\d+\.\d+\.)(\d+)-(\d+)$", spec)
    if m:
        base, lo, hi = m.group(1), int(m.group(2)), int(m.group(3))
        return [f"{base}{n}" for n in range(lo, hi + 1) if 0 < n < 255]

    # single IP
    try:
        ip = ipaddress.ip_address(spec)
        return [str(ip)] if ip in net else []
    except ValueError:
        return []


def _ip_sort_key(ip: str):
    try:
        return int(ipaddress.ip_address(ip))
    except ValueError:
        return 0


def _find_host(inv: dict, ip: str) -> dict | None:
    for h in inv["hosts"]:
        if h["ip"] == ip:
            return h
    return None


def _find_port(host: dict, port: int) -> dict | None:
    for p in host.get("ports", []):
        if p["port"] == int(port):
            return p
    return None


# ---------------------------------------------------------------------------
# Wall-clock port-state transitions
#
# A learner who stops a service (or starts a new listener) changes the *intrinsic*
# state of a ground-truth port. Real networks don't flip instantly: a stopped
# daemon keeps its socket briefly before the kernel refuses new SYNs, and a newly
# started listener takes a beat to bind. We model this by stamping a pending
# transition on the port with a target state + effective-at wall-clock time.
#
# `_advance_ports` is called on every read / action / scan / validate, exactly
# like the baremetal `_tick`. Until the transition elapses the port keeps its
# previous intrinsic state, so a scan run right after the change still shows the
# old state; a re-scan after PORT_TRANSITION_SECONDS shows the new one.
#
# IMPORTANT: this only mutates ground-truth intrinsic `state` (open|closed) that
# *future* scans observe. It never touches the `discovered` knowledge base that
# validate_nmap_lab grades on, so grading is completely unaffected.
# ---------------------------------------------------------------------------

def _advance_ports(inv: dict, now: float | None = None) -> bool:
    """Apply any pending port transitions whose effective time has arrived.

    Returns True if anything changed (so callers can persist)."""
    now = _now() if now is None else now
    changed = False
    for host in inv.get("hosts", []):
        for port in host.get("ports", []):
            pending = port.get("pending_state")
            eff = port.get("transition_at")
            if not pending or eff is None:
                continue
            if now >= float(eff):
                port["state"] = pending
                port.pop("pending_state", None)
                port.pop("transition_at", None)
                changed = True
    return changed


def _schedule_port_transition(host: dict, port_num: int, target_state: str,
                              now: float | None = None,
                              service: str = "") -> tuple[bool, str]:
    """Queue a port to move to `target_state` (open|closed) after the delay.

    If the port isn't in the ground-truth inventory yet and we're opening it, add
    it (a newly started listener). Returns (ok, message)."""
    now = _now() if now is None else now
    target_state = "open" if str(target_state).lower() == "open" else "closed"
    port = _find_port(host, port_num)
    if port is None:
        if target_state == "closed":
            return False, f"port {port_num} is not listening on {host['ip']}"
        # New listener bound by the learner.
        port = _port(int(port_num), "closed", service or _guess_service(int(port_num)))
        host.setdefault("ports", []).append(port)
    # Cancel a no-op (already in / already heading to the requested state).
    if port.get("pending_state") == target_state:
        return True, f"port {port_num} already transitioning to {target_state}"
    if port["state"] == target_state and not port.get("pending_state"):
        return True, f"port {port_num} is already {target_state}"
    port["pending_state"] = target_state
    port["transition_at"] = now + PORT_TRANSITION_SECONDS
    verb = "starting" if target_state == "open" else "stopping"
    return True, (f"{verb} service on {host['ip']}:{port_num} — the port will read "
                  f"'{target_state}' on a re-scan in ~{PORT_TRANSITION_SECONDS}s")


# ---------------------------------------------------------------------------
# Timing model — an authoritative, deterministic estimate of how long a scan
# "takes", scaled by the -T template, the number of hosts, and the number of
# ports probed. The frontend uses this to pace its progressive output so the
# process *feels* like a real nmap run (SYN Stealth Scan Timing lines, ETC …).
# ---------------------------------------------------------------------------

# Per-template speed multipliers (T0 paranoid … T5 insane). Larger => slower.
# T3 (normal) is the 1.0 baseline; T4 (aggressive) is the common lab default.
_TIMING_MULTIPLIER = {
    0: 12.0,   # paranoid  — serialized, huge inter-probe delays
    1: 6.0,    # sneaky
    2: 2.2,    # polite
    3: 1.0,    # normal (default)
    4: 0.55,   # aggressive
    5: 0.32,   # insane
}


def estimate_duration(caps: dict, host_count: int) -> float:
    """Authoritative scan duration (seconds), from timing/hosts/ports.

    Deterministic given (timing template, host count, intended port count and
    scan phases) so the backend — not the UI — owns the wall-clock feel. This
    is display/pacing only; it never influences what the scan *discovers*.
    """
    hosts = max(1, int(host_count or 1))
    timing = int(caps.get("timing", 3))
    mult = _TIMING_MULTIPLIER.get(timing, 1.0)

    if caps.get("ping_sweep") and not (caps.get("syn_scan") or caps.get("connect_scan")):
        # Host-discovery sweep: fast, dominated by per-host probe latency.
        base = 0.9 + 0.18 * hosts
        return round(base * mult, 2)

    ports = _intended_port_count(caps)
    # Fixed setup + per-host overhead + per host×port probing cost. The
    # per-probe cost is tiny but a full 65535×N sweep still adds up realistically.
    base = 1.4 + 0.35 * hosts + hosts * ports * 0.00028
    if caps.get("version"):
        base += 0.6 * hosts + ports * 0.0016   # banner grabbing is expensive
    if caps.get("os_detect"):
        base += 1.1 * hosts                     # OS fingerprinting probe set
    if caps.get("aggressive"):
        base += 0.8 * hosts                     # NSE default scripts + traceroute
    dur = base * mult
    # Clamp to a sane, watchable window (never instantaneous, never absurd).
    return round(max(1.2, min(dur, 240.0)), 2)


# ---------------------------------------------------------------------------
# The scan engine — derive observed results from ground truth + flags
# ---------------------------------------------------------------------------

def _host_is_discoverable(host: dict, caps: dict, sudo: bool) -> tuple[bool, str]:
    """Would this host show as 'up' for the given scan?

    Returns (up, reason). Mirrors nmap reality:
      - A live host that answers ICMP is always discovered.
      - A live host that blocks ICMP is missed by a plain ping sweep (-sn)
        UNLESS the learner passes -Pn (treat as online) or runs a SYN/connect
        port scan that elicits a response from an open port.
      - A non-live host is never up.
    """
    if not host.get("live"):
        return False, "no response"

    if caps["no_ping"]:
        return True, "skipped host discovery (-Pn)"

    if not host.get("icmp_blocked"):
        return True, "echo reply"

    # ICMP blocked: a pure ping sweep misses it; a port scan that touches an
    # open port still reveals it (SYN/connect probe gets SYN-ACK).
    if caps["ping_sweep"] and not (caps["syn_scan"] or caps["connect_scan"]):
        return False, "no ICMP reply (host filters ping)"

    if caps["syn_scan"] or caps["connect_scan"]:
        # A probe to any open & reachable port wakes it up.
        if any(p["state"] == "open" for p in host["ports"]):
            return True, "SYN-ACK from open port"
    return False, "no ICMP reply (use -Pn)"


def _observed_port_state(host: dict, port: dict, caps: dict, sudo: bool) -> str:
    """Derive open|closed|filtered for one port under this scan."""
    intrinsic = port["state"]  # open | closed
    if intrinsic == "closed":
        # A firewall that drops everything makes even closed ports look filtered.
        if host.get("firewalled") and not (caps["syn_scan"] and sudo):
            # closed ports behind the FW are dropped -> filtered
            return "filtered" if port["port"] not in (22,) else "closed"
        return "closed"

    # intrinsic open
    if host.get("firewalled"):
        # Stateful FW DROPs unsolicited SYN to protected ports. SSH (22) is the
        # one allow-listed mgmt port; everything else needs a privileged SYN scan.
        if port["port"] == 22:
            return "open"
        if caps["syn_scan"] and sudo:
            return "open"   # half-open SYN gets through the allow rule for the probe
        return "filtered"
    return "open"


def _run_scan(inv: dict, targets: Any, flags: Any, sudo: bool) -> dict:
    """Execute one nmap-style scan and return a structured result.

    Result shape:
      {
        "command": "...",
        "scan_type": "ping_sweep|port_scan",
        "hosts": [ {ip, hostname, mac, vendor, state(up/down),
                    reason, os(optional), os_accuracy(optional),
                    ports: [{port, proto, state, service, version?}]} ],
        "hosts_up": int, "summary": "..."
      }
    """
    caps = _parse_flags(flags)
    candidate_ips = _expand_targets(targets, inv)

    # Privileged scans without sudo are downgraded — exactly like nmap, which
    # warns and falls back to a connect scan when not root.
    privileged_warning = None
    effective_syn = caps["syn_scan"]
    effective_os = caps["os_detect"]
    if caps["syn_scan"] and not sudo:
        privileged_warning = "TCP SYN scan (-sS) requires root; falling back to connect scan. Re-run with sudo."
        effective_syn = False
        caps["connect_scan"] = True
    if caps["os_detect"] and not sudo:
        privileged_warning = (privileged_warning or "") + \
            " OS detection (-O) requires root privileges (raw sockets); skipped."

    # If no scan technique flag was given at all, default to a connect-style
    # port scan (nmap defaults to SYN as root, connect otherwise).
    if not (caps["ping_sweep"] or caps["syn_scan"] or caps["connect_scan"]):
        if sudo:
            effective_syn = True
            caps["syn_scan"] = True
        else:
            caps["connect_scan"] = True

    eff_caps = dict(caps)
    eff_caps["syn_scan"] = effective_syn
    eff_caps["os_detect"] = effective_os and sudo

    if caps.get("all_ports"):
        # A full-range sweep (`-p-` / `-p 1-65535`) probes every port, so it must
        # reveal ports outside the default top-ports set. We can't enumerate all
        # 65535 cheaply, so scan the default top-ports UNION every ground-truth
        # port present on any candidate host — the full sweep then surfaces open
        # ports (e.g. 8443 on the bastion) that the default scan would miss.
        gt_ports = {p["port"] for ip in candidate_ips
                    for p in (_find_host(inv, ip) or {}).get("ports", [])}
        ports_to_scan = sorted(set(_DEFAULT_TOP_PORTS) | gt_ports)
    elif caps["ports"] is not None:
        ports_to_scan = caps["ports"]
    else:
        ports_to_scan = _DEFAULT_TOP_PORTS

    result_hosts: list[dict] = []
    hosts_up = 0
    for ip in candidate_ips:
        host = _find_host(inv, ip)
        if host is None:
            # An address with no host behind it.
            up = bool(caps["no_ping"])  # -Pn marks every address "up" optimistically
            if up:
                result_hosts.append({
                    "ip": ip, "hostname": "", "mac": "", "vendor": "",
                    "state": "up", "reason": "user-set (-Pn)",
                    "ports": [], "note": "no ports responded",
                })
                hosts_up += 1
            continue

        up, reason = _host_is_discoverable(host, eff_caps, sudo)
        if not up:
            continue
        hosts_up += 1

        entry: dict = {
            "ip": ip,
            "hostname": host.get("hostname", ""),
            "mac": host.get("mac", ""),
            "vendor": host.get("vendor", ""),
            "state": "up",
            "reason": reason,
            "ports": [],
        }

        if caps["ping_sweep"] and not (caps["syn_scan"] or caps["connect_scan"]):
            # Host-discovery-only scan: report up/down, no ports.
            result_hosts.append(entry)
            continue

        # Real nmap collapses the mass of uninteresting ports into a single
        # "Not shown: N closed/filtered tcp ports" line and lists only the
        # interesting (open / open|filtered / filtered) ones — UNLESS the learner
        # asked for a specific, bounded port list (e.g. `-p 22,3306`), in which
        # case nmap prints the exact state of each requested port, closed included.
        explicit_small_list = (
            caps["ports"] is not None
            and not caps.get("all_ports")
            and len(caps["ports"]) <= 25
        )
        not_shown_closed = 0
        not_shown_filtered = 0
        for pnum in ports_to_scan:
            port = next((p for p in host["ports"] if p["port"] == pnum), None)
            if port is None:
                # Unlisted port: closed (or filtered behind a drop-all FW).
                if host.get("firewalled") and not (eff_caps["syn_scan"] and sudo):
                    state = "filtered"
                else:
                    state = "closed"
                if state == "filtered":
                    # A drop-all firewall's filtered ports are the teaching point;
                    # surface them (matches nmap listing many filtered ports).
                    entry["ports"].append({
                        "port": pnum, "proto": "tcp", "state": "filtered",
                        "service": _guess_service(pnum),
                    })
                elif explicit_small_list:
                    # Learner explicitly probed this port — show its closed state.
                    entry["ports"].append({
                        "port": pnum, "proto": "tcp", "state": "closed",
                        "service": _guess_service(pnum),
                    })
                else:
                    not_shown_closed += 1
                continue

            state = _observed_port_state(host, port, eff_caps, sudo)
            if state == "closed" and not explicit_small_list:
                # Collapse a known-closed port into the "Not shown" tally rather
                # than printing a CLOSED row (nmap default behaviour).
                not_shown_closed += 1
                continue
            pinfo: dict = {
                "port": pnum, "proto": port["proto"], "state": state,
                "service": port["service"],
            }
            if state == "open" and caps["version"]:
                pinfo["version"] = port.get("version", "")
                pinfo["product"] = port.get("product", "")
            entry["ports"].append(pinfo)

        # nmap prints e.g. "Not shown: 996 closed tcp ports (conn-refused)".
        # For the default / -F / full-range cases the engine only walks a
        # representative subset of ports, but the wire-feel should reflect the
        # true probe count (~1000 default, 65535 for -p-), so pad the not-shown
        # tally up to (intended ports − ports actually surfaced). An explicit
        # small -p list reports exactly what was requested, so no padding.
        if not explicit_small_list:
            surfaced = len(entry["ports"])
            intended = _intended_port_count(caps)
            padded_not_shown = max(not_shown_closed, intended - surfaced - not_shown_filtered)
            not_shown_closed = padded_not_shown
        if not_shown_closed or not_shown_filtered:
            entry["not_shown"] = {
                "closed": not_shown_closed,
                "filtered": not_shown_filtered,
            }

        # OS detection only with -O (or -A) AND sudo.
        if eff_caps["os_detect"] and any(p["state"] == "open" for p in host["ports"]):
            entry["os"] = host.get("os", "")
            entry["os_family"] = host.get("os_family", "")
            entry["os_accuracy"] = 96

        result_hosts.append(entry)

    scan_type = ("ping_sweep" if caps["ping_sweep"]
                 and not (caps["syn_scan"] or caps["connect_scan"]) else "port_scan")

    cmd = _format_command(targets, flags, sudo)
    # Authoritative, backend-owned wall-clock estimate. The UI paces its
    # progressive reveal to this value (it does NOT compute its own).
    duration = estimate_duration(eff_caps, len(candidate_ips))
    port_count = _intended_port_count(caps)
    summary = (f"Nmap done: {len(candidate_ips)} IP addresses "
               f"({hosts_up} hosts up) scanned in {duration:.2f} seconds")
    return {
        "command": cmd,
        "scan_type": scan_type,
        "hosts": result_hosts,
        "hosts_up": hosts_up,
        "addresses_scanned": len(candidate_ips),
        "warning": privileged_warning.strip() if privileged_warning else None,
        "summary": summary,
        "caps": {k: v for k, v in caps.items() if k != "ports"},
        "sudo": bool(sudo),
        "ports_spec": caps["ports"],
        # ── timing metadata for the UI's progress animation ──
        "duration": duration,
        "timing": int(caps.get("timing", 3)),
        "port_count": port_count,
        "host_count": len(candidate_ips),
    }


_COMMON_SERVICES = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "domain", 80: "http",
    110: "pop3", 135: "msrpc", 139: "netbios-ssn", 143: "imap", 443: "https",
    445: "microsoft-ds", 993: "imaps", 995: "pop3s", 1723: "pptp", 3306: "mysql",
    3389: "ms-wbt-server", 5432: "postgresql", 5900: "vnc", 8080: "http-proxy",
    8443: "https-alt",
}


def _guess_service(port: int) -> str:
    return _COMMON_SERVICES.get(port, "unknown")


def _format_command(targets: Any, flags: Any, sudo: bool) -> str:
    if isinstance(flags, (list, tuple)):
        flag_str = " ".join(str(f) for f in flags)
    else:
        flag_str = str(flags or "")
    tgt = targets if isinstance(targets, str) else " ".join(str(t) for t in (targets or []))
    parts = []
    if sudo:
        parts.append("sudo")
    parts.append("nmap")
    if flag_str:
        parts.append(flag_str)
    parts.append(tgt)
    return " ".join(p for p in parts if p).strip()


# ---------------------------------------------------------------------------
# Discovery tracking — what the learner has actually learned this session
# ---------------------------------------------------------------------------

def _record_discovery(state: dict, scan: dict) -> None:
    """Fold a scan's findings into the cumulative `discovered` knowledge base.

    discovered = {
      "live_hosts": {ip: {"via": scan_type, "hostname": ...}},
      "ports": {ip: {port: {"state": ..., "via_version": bool}}},
      "versions": {ip: {port: "product version"}},
      "os": {ip: "os string"},
      "scans": [ {command, scan_type, ...} ]  # recent scan log
    }
    """
    disc = state.setdefault("discovered", {
        "live_hosts": {}, "ports": {}, "versions": {}, "os": {}, "scans": [],
    })
    for h in scan.get("hosts", []):
        if h.get("state") != "up":
            continue
        ip = h["ip"]
        disc["live_hosts"][ip] = {
            "hostname": h.get("hostname", ""),
            "via": scan.get("scan_type"),
            "mac": h.get("mac", ""),
        }
        if h.get("os"):
            disc["os"][ip] = h["os"]
        host_ports = disc["ports"].setdefault(ip, {})
        host_versions = disc["versions"].setdefault(ip, {})
        for p in h.get("ports", []):
            pn = str(p["port"])
            host_ports[pn] = {"state": p["state"], "service": p.get("service", "")}
            if p.get("version"):
                ver = p["version"].strip()
                product = (p.get("product") or "").strip()
                # The ground-truth version string usually already embeds the
                # product name (e.g. "nginx 1.18.0"); only prefix the product
                # when it is not already present so we don't get "nginx nginx".
                if product and product.lower() not in ver.lower():
                    host_versions[pn] = f"{product} {ver}".strip()
                else:
                    host_versions[pn] = ver

    disc["scans"] = ([{
        "command": scan.get("command"),
        "scan_type": scan.get("scan_type"),
        "hosts_up": scan.get("hosts_up"),
        "time": _now_iso(),
    }] + disc.get("scans", []))[:25]


# ---------------------------------------------------------------------------
# Scenario presets — set a goal + (optionally) tweak the topology per scenario
# ---------------------------------------------------------------------------

def _apply_preset(state: dict, slug: str) -> None:
    """Attach a per-scenario `goal` describing what fact must be discovered
    and how. Validation reads only `goal` + `discovered` (never ground truth)."""
    s = (slug or "").lower()
    inv = state["inventory"]

    if "live-hosts" in s or "host-discovery" in s or "discover" in s:
        state["goal"] = {
            "kind": "live_hosts",
            "title": "Map the live hosts on 10.10.10.0/24",
            "require_live_ips": ["10.10.10.1", "10.10.10.10", "10.10.10.20",
                                 "10.10.10.30"],
            "objective": "Run a host-discovery scan and find every responsive host on the subnet.",
        }

    elif "open-ports" in s or "enumerate-ports" in s or "port-enum" in s:
        state["goal"] = {
            "kind": "open_ports",
            "title": "Enumerate open ports on web01 (10.10.10.10)",
            "target_ip": "10.10.10.10",
            "require_open_ports": [22, 80, 443],
            "objective": "Scan web01 and identify its open TCP ports (22, 80, 443).",
        }

    elif "service-version" in s or "version-detect" in s or "sv-" in s or "banner" in s:
        state["goal"] = {
            "kind": "service_version",
            "title": "Fingerprint the web server software on web01",
            "target_ip": "10.10.10.10",
            "target_port": 80,
            "require_version_contains": "nginx",
            "objective": "Use service/version detection to learn what HTTP server web01 runs on port 80.",
        }

    elif "blocked-syn" in s or "filtered" in s or "firewall" in s or "blocked-scan" in s:
        state["goal"] = {
            "kind": "unblock_filtered",
            "title": "Get past the firewall to confirm the database port is open",
            "target_ip": "10.10.10.20",
            "target_port": 5432,
            "objective": ("A default scan reports db01:5432 as filtered (the firewall drops "
                          "unsolicited SYNs). Use a privileged SYN scan (sudo nmap -sS) to "
                          "confirm the PostgreSQL port is actually open."),
            "require_state": "open",
        }

    elif "os-fingerprint" in s or "os-detect" in s or "fingerprint" in s:
        state["goal"] = {
            "kind": "os_fingerprint",
            "title": "Fingerprint the operating system of win-app01 (10.10.10.30)",
            "target_ip": "10.10.10.30",
            "require_os_family": "windows",
            "objective": "Use OS detection (sudo nmap -O) to identify what OS win-app01 runs.",
        }

    else:
        # Default goal so an unrecognised slug still presents a real task.
        state["goal"] = {
            "kind": "live_hosts",
            "title": "Discover the live hosts on the network",
            "require_live_ips": ["10.10.10.10"],
            "objective": "Run a scan to discover at least one live host on 10.10.10.0/24.",
        }


# ---------------------------------------------------------------------------
# Session lifecycle (mirrors the other engines)
# ---------------------------------------------------------------------------

def _ensure_session(session_id: str, scenario_slug: str = "") -> dict:
    key = str(session_id)
    entry = _load_session(key)
    if entry is None:
        state = {"inventory": _base_inventory()}
        _apply_preset(state, scenario_slug)
        state.setdefault("discovered", {
            "live_hosts": {}, "ports": {}, "versions": {}, "os": {}, "scans": [],
        })
        entry = {"session_id": key, "scenario_slug": scenario_slug, "state": state,
                 "created_at": _now_iso()}
        _save_session(key, entry)
    return entry


def get_state(session_id: str, scenario_slug: str = "") -> dict:
    entry = _ensure_session(session_id, scenario_slug)
    # Advance any pending wall-clock port transitions on read so the topology
    # reflects real time even when no scan/action has happened since the change.
    if _advance_ports(entry["state"]["inventory"]):
        _save_session(str(session_id), entry)
    state = copy.deepcopy(entry["state"])
    inv = state["inventory"]
    disc = state.get("discovered", {})
    goal = state.get("goal", {})

    # The client UI sees the *topology shell* (subnet, gateway, firewall, the
    # scanner) and whatever it has discovered — never the ground-truth ports of
    # undiscovered hosts. This keeps the lab honest: you must scan to learn.
    return {
        "session_id": str(session_id),
        "scenario_slug": entry.get("scenario_slug") or scenario_slug,
        "inventory": {
            "subnet": inv["subnet"],
            "gateway": inv["gateway"],
            "scanner_ip": inv["scanner_ip"],
            "firewall": inv["firewall"],
            # Total host count is known (DHCP leases etc.) but details are hidden.
            "hosts_total": sum(1 for h in inv["hosts"] if h.get("live")),
            "discovered_hosts": [
                {
                    "ip": ip,
                    "hostname": meta.get("hostname", ""),
                    "mac": meta.get("mac", ""),
                    "os": disc.get("os", {}).get(ip, ""),
                    "ports": [
                        {"port": int(pn), **pd,
                         "version": disc.get("versions", {}).get(ip, {}).get(pn, "")}
                        for pn, pd in sorted(
                            disc.get("ports", {}).get(ip, {}).items(),
                            key=lambda kv: int(kv[0]))
                    ],
                }
                for ip, meta in sorted(disc.get("live_hosts", {}).items(),
                                       key=lambda kv: _ip_sort_key(kv[0]))
            ],
        },
        "goal": goal,
        # In-flight service transitions the learner kicked off (stop/start a
        # listener). Display-only: lets the UI show "web01:80 stopping…" and hint
        # that a re-scan is needed. Does not leak undiscovered ground truth — only
        # ports the learner is actively changing appear here.
        "pending_transitions": [
            {"ip": h["ip"], "port": p["port"],
             "to": p.get("pending_state"), "service": p.get("service", "")}
            for h in inv["hosts"]
            for p in h.get("ports", [])
            if p.get("pending_state")
        ],
        "scan_log": disc.get("scans", []),
        # `events` is the contract-named field (mirrors the VMware engine shape
        # {session_id, scenario_slug, inventory, summary, events}); it aliases
        # the scan log so the simulator surfaces an activity feed.
        "events": disc.get("scans", []),
        "summary": {
            "hosts_discovered": len(disc.get("live_hosts", {})),
            "hosts_total": sum(1 for h in inv["hosts"] if h.get("live")),
            "open_ports_found": sum(
                1 for ports in disc.get("ports", {}).values()
                for pd in ports.values() if pd.get("state") == "open"),
            "versions_found": sum(len(v) for v in disc.get("versions", {}).values()),
            "os_identified": len(disc.get("os", {})),
            "scans_run": len(disc.get("scans", [])),
            "goal_title": goal.get("title", ""),
            "objective": goal.get("objective", ""),
        },
    }


def drop_session(session_id: str) -> None:
    cache.delete(_session_key(str(session_id)))


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def apply_action(session_id: str, action: str, payload: dict | None = None) -> dict:
    """Interactive actions. The headline action is `scan` (an nmap run).

    scan payload: {targets, flags, sudo}
      targets: ip / cidr / range / hostname / "all"
      flags:   list or string, e.g. ["-sS","-sV","-p","22,80,443"] or "-sn"
      sudo:    bool — required for -sS raw SYN and -O OS detection

    Other actions: reset (clear discoveries). Validation reads `discovered`.
    """
    payload = payload or {}
    entry = _load_session(str(session_id))
    if not entry:
        return {"ok": False, "error": "Nmap simulation session not found"}
    state = entry["state"]
    inv = state["inventory"]
    # Advance any pending wall-clock port transitions before handling the action
    # so a scan sees the up-to-date topology (a service the learner stopped long
    # enough ago now reads closed; one stopped moments ago still reads open).
    _advance_ports(inv)

    if action == "scan":
        targets = payload.get("targets") or payload.get("target") or "all"
        flags = payload.get("flags", payload.get("args", ""))
        sudo = bool(payload.get("sudo", False))
        # The UI may carry the -p spec in a dedicated `ports` field (in addition
        # to inlining it in flags); fold it into the flag list as `-p <spec>`
        # unless -p is already present. This keeps the port spec authoritative
        # for enumeration AND the timing model regardless of which channel the
        # caller used. Backward-compatible: callers that inline -p or omit ports
        # entirely are unaffected, and the raw-command path below is untouched.
        ports_spec = payload.get("ports")
        if ports_spec not in (None, "") and not payload.get("command"):
            flag_list = (list(flags) if isinstance(flags, (list, tuple))
                         else str(flags or "").split())
            has_p = any(str(f) == "-p" or str(f).startswith("-p")
                        for f in flag_list)
            if not has_p:
                flag_list.extend(["-p", str(ports_spec)])
                flags = flag_list
        # Convenience: allow a full raw command string in `command`.
        raw = payload.get("command")
        if raw and not payload.get("targets") and not payload.get("flags"):
            parsed = _parse_command_string(raw, inv)
            targets, flags, sudo = parsed["targets"], parsed["flags"], parsed["sudo"]

        scan = _run_scan(inv, targets, flags, sudo)
        _record_discovery(state, scan)
        _save_session(str(session_id), entry)
        return {"ok": True, "message": scan["summary"], "scan": scan}

    # ── Service lifecycle: stop/start a listener on a host ──────────────────
    # These let a learner change the network they're scanning (e.g. "stop the
    # exposed telnet service") and then confirm the change with a follow-up scan.
    # The change takes PORT_TRANSITION_SECONDS of wall-clock to take effect, so
    # an immediate re-scan still shows the old state — modelling real socket
    # teardown/bind latency. Grading is untouched (it reads `discovered`).
    if action in ("stop_service", "close_port"):
        ip = payload.get("ip") or payload.get("target")
        host = _find_host(inv, ip) if ip else None
        if not host:
            return {"ok": False, "error": f"host {ip} not found on {inv['subnet']}"}
        port_num = payload.get("port")
        if port_num in (None, ""):
            return {"ok": False, "error": "a port is required"}
        ok, msg = _schedule_port_transition(host, int(port_num), "closed")
        _save_session(str(session_id), entry)
        return {"ok": ok, "message": msg}

    if action in ("start_service", "open_port"):
        ip = payload.get("ip") or payload.get("target")
        host = _find_host(inv, ip) if ip else None
        if not host:
            return {"ok": False, "error": f"host {ip} not found on {inv['subnet']}"}
        port_num = payload.get("port")
        if port_num in (None, ""):
            return {"ok": False, "error": "a port is required"}
        ok, msg = _schedule_port_transition(
            host, int(port_num), "open", service=payload.get("service", ""))
        _save_session(str(session_id), entry)
        return {"ok": ok, "message": msg}

    if action == "reset":
        state["discovered"] = {
            "live_hosts": {}, "ports": {}, "versions": {}, "os": {}, "scans": [],
        }
        _save_session(str(session_id), entry)
        return {"ok": True, "message": "Discovery state reset"}

    return {"ok": False, "error": f"unknown action: {action}"}


def _parse_command_string(raw: str, inv: dict) -> dict:
    """Parse a raw 'nmap ...' / 'sudo nmap ...' command line."""
    toks = str(raw or "").split()
    sudo = False
    if toks and toks[0] == "sudo":
        sudo = True
        toks = toks[1:]
    if toks and toks[0] == "nmap":
        toks = toks[1:]
    flags: list[str] = []
    targets: list[str] = []
    i = 0
    while i < len(toks):
        tok = toks[i]
        if tok == "-p" and i + 1 < len(toks):
            flags.extend([tok, toks[i + 1]])
            i += 2
            continue
        if tok.startswith("-"):
            flags.append(tok)
        else:
            targets.append(tok)
        i += 1
    return {"targets": targets or "all", "flags": flags, "sudo": sudo}


# ---------------------------------------------------------------------------
# Validation — grade purely on what the learner DISCOVERED via scans
# ---------------------------------------------------------------------------

def validate_nmap_lab(session_id: str, scenario_slug: str = "") -> tuple[bool, str]:
    entry = _load_session(str(session_id)) or _ensure_session(session_id, scenario_slug)
    state = entry["state"]
    goal = state.get("goal") or {}
    disc = state.get("discovered", {})
    kind = goal.get("kind")

    if kind == "live_hosts":
        required = goal.get("require_live_ips", [])
        found = set(disc.get("live_hosts", {}).keys())
        missing = [ip for ip in required if ip not in found]
        if missing:
            return False, ("Host discovery incomplete — still need to find: "
                           + ", ".join(missing))
        return True, f"All {len(required)} live hosts discovered — validation passed"

    if kind == "open_ports":
        ip = goal.get("target_ip")
        required = goal.get("require_open_ports", [])
        host_ports = disc.get("ports", {}).get(ip, {})
        open_found = {int(pn) for pn, pd in host_ports.items() if pd.get("state") == "open"}
        missing = [p for p in required if p not in open_found]
        if missing:
            return False, (f"Open-port enumeration incomplete on {ip} — still need: "
                           + ", ".join(str(p) for p in missing))
        return True, f"All required open ports on {ip} discovered — validation passed"

    if kind == "service_version":
        ip = goal.get("target_ip")
        port = str(goal.get("target_port"))
        want = (goal.get("require_version_contains") or "").lower()
        ver = disc.get("versions", {}).get(ip, {}).get(port, "")
        if not ver:
            return False, (f"No service/version recorded for {ip}:{port} — "
                           "run a version-detection scan (nmap -sV).")
        if want and want not in ver.lower():
            return False, f"Version for {ip}:{port} does not match the expected service yet"
        return True, f"Service version on {ip}:{port} identified ({ver}) — validation passed"

    if kind == "unblock_filtered":
        ip = goal.get("target_ip")
        port = str(goal.get("target_port"))
        want_state = goal.get("require_state", "open")
        pd = disc.get("ports", {}).get(ip, {}).get(port)
        if not pd:
            return False, (f"{ip}:{port} not probed yet — scan that specific port.")
        if pd.get("state") != want_state:
            return False, (f"{ip}:{port} still reads '{pd.get('state')}'. The firewall drops "
                           "unsolicited SYNs — re-run with a privileged SYN scan (sudo nmap -sS).")
        return True, f"{ip}:{port} confirmed {want_state} through the firewall — validation passed"

    if kind == "os_fingerprint":
        ip = goal.get("target_ip")
        want_family = (goal.get("require_os_family") or "").lower()
        os_str = (disc.get("os", {}).get(ip) or "").lower()
        if not os_str:
            return False, (f"No OS fingerprint recorded for {ip} — run OS detection "
                           "with privileges (sudo nmap -O).")
        if want_family and want_family not in os_str:
            return False, f"OS fingerprint for {ip} does not match the expected family yet"
        return True, f"OS of {ip} fingerprinted ({os_str}) — validation passed"

    # Unknown goal — fail closed.
    return False, "No validation goal configured for this scenario"
