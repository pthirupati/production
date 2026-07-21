"""Nmap V2 facades — NSE scripts, traceroute hops, scan compare.

Learner language: Lab Environment / Lab Server — never Simulation/Sandbox/Mock.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_NSE_CATALOG = [
    {"name": "http-title", "categories": ["default", "discovery", "safe"], "desc": "Grabs the title of the root HTML page"},
    {"name": "ssl-cert", "categories": ["default", "discovery", "safe", "version"], "desc": "Retrieves TLS certificate details"},
    {"name": "ssh-hostkey", "categories": ["default", "discovery", "safe"], "desc": "Shows SSH host keys"},
    {"name": "smb-os-discovery", "categories": ["default", "discovery", "safe"], "desc": "OS / domain via SMB"},
    {"name": "vuln", "categories": ["vuln", "intrusive"], "desc": "Category: known vulnerability checks"},
    {"name": "dns-brute", "categories": ["discovery", "intrusive"], "desc": "Brute-forces DNS hostnames"},
]


def seed_v2() -> dict[str, Any]:
    return {
        "nse_catalog": list(_NSE_CATALOG),
        "nse_results": [],
        "traceroute_cache": {},
        "compare_baseline": None,
        "compare_last": None,
    }


def ensure_v2(state: dict) -> None:
    for key, value in seed_v2().items():
        if key not in state or state.get(key) is None:
            state[key] = value if not isinstance(value, list) else list(value)


def _flag_list(flags) -> list[str]:
    if isinstance(flags, (list, tuple)):
        return [str(f) for f in flags]
    return str(flags or "").split()


def _has_flag(flags: list[str], name: str) -> bool:
    return any(f == name or f.startswith(f"{name}=") for f in flags)


def _script_args(flags: list[str]) -> list[str]:
    """Extract --script values (category or script names)."""
    out: list[str] = []
    i = 0
    while i < len(flags):
        f = flags[i]
        if f == "--script" and i + 1 < len(flags):
            out.extend(x.strip() for x in flags[i + 1].replace(",", " ").split() if x.strip())
            i += 2
            continue
        if f.startswith("--script="):
            out.extend(x.strip() for x in f.split("=", 1)[1].replace(",", " ").split() if x.strip())
        i += 1
    return out


def _hops_for(ip: str, gateway: str) -> list[dict]:
    return [
        {"ttl": 1, "rtt": "0.42ms", "address": gateway or "192.168.1.1", "hostname": "gw.lab"},
        {"ttl": 2, "rtt": "1.18ms", "address": ip, "hostname": ""},
    ]


def enrich_scan(state: dict, scan: dict, flags=None, inventory: dict | None = None) -> dict:
    """Attach traceroute / NSE results when the scan requested them."""
    ensure_v2(state)
    fl = _flag_list(flags if flags is not None else (scan.get("caps") or {}))
    # caps may be a dict of booleans — also check scan command string
    cmd = str(scan.get("command") or "")
    want_tr = _has_flag(fl, "--traceroute") or "--traceroute" in cmd
    scripts = _script_args(fl)
    if not scripts and ("--script" in cmd or " -A " in f" {cmd} " or cmd.endswith(" -A") or " -A" in cmd.split()):
        scripts = ["default"]
    if scan.get("caps", {}).get("aggressive"):
        scripts = scripts or ["default"]

    gateway = (inventory or {}).get("gateway") or "192.168.1.1"
    nse_rows = []
    for host in scan.get("hosts") or []:
        ip = host.get("ip")
        if not ip:
            continue
        if want_tr:
            hops = _hops_for(ip, gateway)
            host["traceroute"] = hops
            state.setdefault("traceroute_cache", {})[ip] = hops
        for script in scripts:
            # Resolve category → concrete script names from catalog
            names = [script]
            if script in ("default", "safe", "discovery", "vuln", "auth", "version"):
                names = [c["name"] for c in state.get("nse_catalog") or [] if script in (c.get("categories") or [])]
                if not names:
                    names = [script]
            for name in names[:4]:
                open_ports = [p for p in (host.get("ports") or []) if p.get("state") == "open"]
                sample = open_ports[0] if open_ports else None
                output = f"{name}: no open ports to probe"
                if sample:
                    svc = sample.get("service") or "unknown"
                    if name == "http-title" and sample.get("port") in (80, 443, 8080):
                        output = f"http-title: Lab Server — {host.get('hostname') or ip}"
                    elif name == "ssl-cert" and sample.get("port") in (443, 8443):
                        output = "ssl-cert: subject=CN=lab.local; issuer=Lab CA"
                    elif name == "ssh-hostkey" and sample.get("port") == 22:
                        output = "ssh-hostkey: 256 SHA256:labkey… (ED25519)"
                    elif name == "smb-os-discovery" and sample.get("port") in (139, 445):
                        output = f"smb-os-discovery: OS: Windows Server; Computer name: {host.get('hostname') or 'HOST'}"
                    else:
                        output = f"{name}: {svc} on {sample.get('port')}/{sample.get('proto') or 'tcp'} — OK"
                row = {
                    "id": f"nse-{len(state.get('nse_results') or []) + len(nse_rows) + 1}",
                    "host": ip,
                    "script": name,
                    "output": output,
                    "at": _now(),
                }
                nse_rows.append(row)
                host.setdefault("scripts", []).append({"id": name, "output": output})

    if nse_rows:
        state.setdefault("nse_results", []).extend(nse_rows)
        # Cap history
        state["nse_results"] = state["nse_results"][-80:]

    # Keep last scan summary for compare UI
    state["compare_last"] = {
        "at": _now(),
        "command": scan.get("command"),
        "hosts_up": scan.get("hosts_up"),
        "addresses_scanned": scan.get("addresses_scanned"),
        "open_ports": sum(
            1 for h in (scan.get("hosts") or [])
            for p in (h.get("ports") or [])
            if p.get("state") == "open"
        ),
        "host_ips": sorted(h.get("ip") for h in (scan.get("hosts") or []) if h.get("ip")),
    }
    return scan


def apply_v2_action(state: dict, action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    ensure_v2(state)
    inv = state.get("inventory") or {}

    if action == "traceroute":
        ip = (payload.get("ip") or payload.get("target") or "").strip()
        if not ip:
            return {"ok": False, "error": "target IP required"}
        hops = _hops_for(ip, inv.get("gateway") or "192.168.1.1")
        state.setdefault("traceroute_cache", {})[ip] = hops
        return {"ok": True, "message": f"Traceroute to {ip} complete", "traceroute": hops}

    if action == "run_nse":
        ip = (payload.get("ip") or payload.get("target") or "").strip()
        script = (payload.get("script") or payload.get("name") or "http-title").strip()
        if not ip:
            return {"ok": False, "error": "target IP required"}
        disc = state.get("discovered") or {}
        ports = disc.get("ports", {}).get(ip) or {}
        open_p = [pn for pn, pd in ports.items() if (pd or {}).get("state") == "open"]
        output = f"{script}: host {ip} — {'ports ' + ','.join(open_p[:5]) if open_p else 'no open ports in discovery yet'}"
        row = {"id": f"nse-{len(state.get('nse_results') or []) + 1}", "host": ip, "script": script, "output": output, "at": _now()}
        state.setdefault("nse_results", []).append(row)
        return {"ok": True, "message": f"NSE {script} on {ip}", "result": row}

    if action == "save_compare_baseline":
        last = state.get("compare_last")
        if not last:
            # Snapshot from discovered knowledge
            disc = state.get("discovered") or {}
            last = {
                "at": _now(),
                "command": "(discovery snapshot)",
                "hosts_up": len(disc.get("live_hosts") or {}),
                "open_ports": sum(
                    1 for ports in (disc.get("ports") or {}).values()
                    for pd in ports.values()
                    if (pd or {}).get("state") == "open"
                ),
                "host_ips": sorted((disc.get("live_hosts") or {}).keys()),
            }
        state["compare_baseline"] = dict(last)
        return {"ok": True, "message": "Compare baseline saved", "baseline": state["compare_baseline"]}

    if action == "compare_scans":
        base = state.get("compare_baseline") or {}
        cur = state.get("compare_last") or {}
        if not cur:
            disc = state.get("discovered") or {}
            cur = {
                "at": _now(),
                "hosts_up": len(disc.get("live_hosts") or {}),
                "open_ports": sum(
                    1 for ports in (disc.get("ports") or {}).values()
                    for pd in ports.values()
                    if (pd or {}).get("state") == "open"
                ),
                "host_ips": sorted((disc.get("live_hosts") or {}).keys()),
            }
        base_ips = set(base.get("host_ips") or [])
        cur_ips = set(cur.get("host_ips") or [])
        diff = {
            "new_hosts": sorted(cur_ips - base_ips),
            "missing_hosts": sorted(base_ips - cur_ips),
            "open_ports_delta": int(cur.get("open_ports") or 0) - int(base.get("open_ports") or 0),
            "baseline": base,
            "current": cur,
        }
        return {"ok": True, "message": "Scan compare ready", "compare": diff}

    return None


def v2_public(state: dict) -> dict:
    ensure_v2(state)
    return {
        "nse_catalog": state.get("nse_catalog") or [],
        "nse_results": (state.get("nse_results") or [])[-20:],
        "traceroute_cache": state.get("traceroute_cache") or {},
        "compare_baseline": state.get("compare_baseline"),
        "compare_last": state.get("compare_last"),
    }
