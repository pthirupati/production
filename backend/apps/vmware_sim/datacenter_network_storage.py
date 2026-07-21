"""Phase 3: switch CLI, packet tools, cable catalog ops, storage facades.

Lab Environment networking and storage surfaces for the datacenter twin.
"""

from __future__ import annotations

import random
import time


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def enrich_network(network: dict) -> dict:
    """Attach vendor, CLI, protocols, and live counters to switches."""
    defaults = [
        {"vendor": "Arista", "os": "EOS", "cli_style": "arista", "mgmt_ip": "10.0.0.11"},
        {"vendor": "Cisco", "os": "NX-OS", "cli_style": "cisco", "mgmt_ip": "10.0.0.12"},
        {"vendor": "Juniper", "os": "Junos", "cli_style": "juniper", "mgmt_ip": "10.0.0.13"},
        {"vendor": "NVIDIA", "os": "Cumulus/Spectrum", "cli_style": "nvidia", "mgmt_ip": "10.0.0.14"},
    ]
    for i, sw in enumerate(network.get("switches") or []):
        meta = defaults[i % len(defaults)]
        sw.setdefault("vendor", meta["vendor"])
        sw.setdefault("os", meta["os"])
        sw.setdefault("cli_style", meta["cli_style"])
        sw.setdefault("mgmt_ip", meta["mgmt_ip"])
        sw.setdefault("protocols", {
            "bgp": {"asn": 65001 + i, "peers": 2, "established": 2 if i == 0 else 1, "status": "up"},
            "ospf": {"area": "0.0.0.0", "neighbors": 1, "status": "full"},
            "stp": {"mode": "RSTP", "root": i == 0, "status": "forwarding"},
            "lacp": {"bundles": [{"id": "Po1", "members": [7, 8], "status": "up"}] if i == 0 else []},
            "vxlan": {"enabled": i == 0, "vnis": [10010, 10020] if i == 0 else []},
            "evpn": {"enabled": i == 0, "status": "established" if i == 0 else "disabled"},
            "mpls": {"enabled": False},
            "vlan": {"ids": sorted({p.get("vlan") for p in sw.get("ports") or [] if p.get("vlan")})},
        })
        sw.setdefault("cli_history", [])
        sw.setdefault("cli_output", [])
        for p in sw.get("ports") or []:
            p.setdefault("rx_pps", random.randint(1200, 85000) if p.get("status") == "up" else 0)
            p.setdefault("tx_pps", random.randint(800, 72000) if p.get("status") == "up" else 0)
            p.setdefault("errors", 0)
            p.setdefault("drops", 0)
            p.setdefault("latency_us", random.randint(8, 45) if p.get("status") == "up" else None)
            p.setdefault("blink", p.get("status") == "up")
            p.setdefault("util_pct", min(99, int((p.get("rx_pps") or 0) / 1000)) if p.get("status") == "up" else 0)
    network.setdefault("tools", {"last_ping": None, "last_traceroute": None, "last_iperf": None})
    network.setdefault("faults", network.get("faults") or [])
    network.setdefault("routing", {
        "bgp_as": 65001,
        "default_gw": "10.0.0.1",
        "prefixes": ["10.10.0.0/16", "10.20.0.0/16", "10.30.0.0/24"],
    })
    return network


def run_switch_cli(sw: dict, command: str) -> list[str]:
    """Execute a small show/config command set against a switch facade."""
    cmd = (command or "").strip()
    style = sw.get("cli_style") or "cisco"
    ports = sw.get("ports") or []
    proto = sw.get("protocols") or {}
    lines: list[str] = []
    lower = cmd.lower()

    if not cmd:
        return ["% Incomplete command"]

    if lower in ("?", "help"):
        return [
            "Available: show version | show interfaces | show vlan | show ip bgp summary",
            "  show lacp | show spanning-tree | show vxlan | ping <host>",
            "  conf t / configure | interface EthernetN | no shutdown | shutdown",
            "  switchport access vlan <id> | exit | end | clear counters",
        ]

    if lower.startswith("show version") or lower == "show ver":
        lines = [
            f"{sw.get('vendor')} {sw.get('os')} — {sw.get('hostname')}",
            f"Hardware: {sw.get('model')}",
            f"Management IP: {sw.get('mgmt_ip')}",
            f"Uptime: 142 days, 3:11:08",
        ]
    elif "interface" in lower and lower.startswith("show"):
        lines = ["Port  Status  Speed  VLAN  RX(pps)  TX(pps)  Err  Drop  Lat(us)  Util%"]
        for p in ports:
            lines.append(
                f"{p.get('port'):<5} {p.get('status'):<7} {str(p.get('speed') or '-'):<6} "
                f"{str(p.get('vlan') or '-'):<5} {p.get('rx_pps') or 0:<8} {p.get('tx_pps') or 0:<8} "
                f"{p.get('errors') or 0:<4} {p.get('drops') or 0:<5} {str(p.get('latency_us') or '-'):<8} "
                f"{p.get('util_pct') or 0}"
            )
    elif "vlan" in lower and lower.startswith("show"):
        vlans = proto.get("vlan", {}).get("ids") or []
        lines = [f"VLAN  Name"] + [f"{v:<5} vlan{v}" for v in vlans] or ["No VLANs configured"]
    elif "bgp" in lower:
        bgp = proto.get("bgp") or {}
        lines = [
            f"BGP router ID {sw.get('mgmt_ip')} AS {bgp.get('asn')}",
            f"Peers {bgp.get('peers')} established {bgp.get('established')} status {bgp.get('status')}",
            "Neighbor        AS      State",
            f"10.0.0.1        65000   {bgp.get('status', 'Idle')}",
            f"10.0.0.2        65002   Established" if bgp.get("established", 0) > 1 else "10.0.0.2        65002   Idle",
        ]
    elif "ospf" in lower:
        o = proto.get("ospf") or {}
        lines = [f"OSPF area {o.get('area')} neighbors {o.get('neighbors')} state {o.get('status')}"]
    elif "lacp" in lower or "port-channel" in lower or "portchannel" in lower:
        bundles = (proto.get("lacp") or {}).get("bundles") or []
        if not bundles:
            lines = ["No LACP bundles"]
        else:
            for b in bundles:
                lines.append(f"{b['id']} members {b['members']} status {b['status']}")
    elif "spanning" in lower or "stp" in lower or "rstp" in lower:
        s = proto.get("stp") or {}
        lines = [f"Mode {s.get('mode')} root={'yes' if s.get('root') else 'no'} status {s.get('status')}"]
    elif "vxlan" in lower or "evpn" in lower:
        vx = proto.get("vxlan") or {}
        ev = proto.get("evpn") or {}
        lines = [
            f"VXLAN enabled={vx.get('enabled')} VNIs={vx.get('vnis')}",
            f"EVPN enabled={ev.get('enabled')} status={ev.get('status')}",
        ]
    elif lower.startswith("clear counter"):
        for p in ports:
            p["errors"] = 0
            p["drops"] = 0
        lines = ["Counters cleared"]
    elif lower in ("conf t", "configure", "configure terminal", "configure exclusive"):
        sw["config_mode"] = True
        lines = ["Entering configuration mode"]
    elif lower in ("end", "exit") and sw.get("config_mode"):
        if lower == "end":
            sw["config_mode"] = False
            lines = ["Exited configuration mode"]
        else:
            lines = ["(config)#"]
    elif "shutdown" in lower or "no shutdown" in lower:
        # interface EthernetN shutdown | no shutdown
        port_num = None
        for token in cmd.replace("/", " ").split():
            if token.isdigit():
                port_num = int(token)
                break
            if token.lower().startswith("ethernet") and token[8:].isdigit():
                port_num = int(token[8:])
                break
        target = next((p for p in ports if p.get("port") == port_num), None)
        if not target:
            lines = ["% Invalid interface"]
        elif "no shutdown" in lower:
            target["status"] = "up"
            target["blink"] = True
            target["rx_pps"] = random.randint(1000, 50000)
            target["tx_pps"] = random.randint(800, 40000)
            lines = [f"Interface Ethernet{port_num} enabled"]
        else:
            target["status"] = "down"
            target["blink"] = False
            target["rx_pps"] = target["tx_pps"] = 0
            lines = [f"Interface Ethernet{port_num} administratively down"]
    elif "switchport access vlan" in lower:
        parts = lower.split()
        try:
            vlan = int(parts[-1])
            port_num = None
            for token in cmd.split():
                if token.isdigit() and int(token) != vlan:
                    port_num = int(token)
            target = next((p for p in ports if p.get("port") == port_num), ports[0] if ports else None)
            if target:
                target["vlan"] = vlan
                lines = [f"Port {target['port']} access VLAN {vlan}"]
            else:
                lines = ["% No interface"]
        except (ValueError, IndexError):
            lines = ["% Incomplete command"]
    elif lower.startswith("ping"):
        host = cmd.split(maxsplit=1)[1] if " " in cmd else "10.0.0.1"
        lines = _ping_lines(host)
    else:
        prompt = f"({style})" if not sw.get("config_mode") else "(config)"
        lines = [f"% Invalid input detected at '^' marker: {cmd}", f"{prompt} Try 'help'"]

    hist = sw.setdefault("cli_history", [])
    hist.insert(0, {"time": _now(), "cmd": cmd})
    sw["cli_history"] = hist[:40]
    sw["cli_output"] = lines
    return lines


def _ping_lines(host: str) -> list[str]:
    ok = not any(x in host.lower() for x in ("fail", "blackhole", "0.0.0.0"))
    if ok:
        rtt = [round(random.uniform(0.4, 2.8), 2) for _ in range(4)]
        return [
            f"PING {host} (56 data bytes)",
            *[f"64 bytes from {host}: icmp_seq={i+1} ttl=64 time={rtt[i]} ms" for i in range(4)],
            f"--- {host} ping statistics ---",
            f"4 packets transmitted, 4 received, 0% packet loss",
            f"rtt min/avg/max = {min(rtt)}/{sum(rtt)/4:.2f}/{max(rtt)} ms",
        ]
    return [
        f"PING {host}",
        "Request timeout for icmp_seq 1",
        "Request timeout for icmp_seq 2",
        "--- ping statistics ---",
        "4 packets transmitted, 0 received, 100% packet loss",
    ]


def run_traceroute(dest: str) -> dict:
    hops = [
        {"hop": 1, "host": "tor-gw.local", "ip": "10.10.0.1", "rtt_ms": 0.3},
        {"hop": 2, "host": "agg-sw-01", "ip": "10.0.0.12", "rtt_ms": 0.8},
        {"hop": 3, "host": "core-edge", "ip": "10.0.0.1", "rtt_ms": 1.4},
        {"hop": 4, "host": dest or "target", "ip": dest if dest.count(".") == 3 else "10.99.0.10", "rtt_ms": 2.1},
    ]
    return {"dest": dest, "hops": hops, "time": _now()}


def run_iperf(src: str, dst: str, seconds: int = 5) -> dict:
    gbps = round(random.uniform(8.2, 24.7), 2)
    return {
        "src": src,
        "dst": dst,
        "seconds": seconds,
        "throughput_gbps": gbps,
        "retransmits": random.randint(0, 12),
        "time": _now(),
    }


def tick_port_counters(network: dict) -> None:
    """Animate traffic counters slightly for live feel."""
    for sw in network.get("switches") or []:
        for p in sw.get("ports") or []:
            if p.get("status") != "up":
                p["blink"] = False
                continue
            p["blink"] = True
            p["rx_pps"] = max(0, (p.get("rx_pps") or 1000) + random.randint(-800, 1200))
            p["tx_pps"] = max(0, (p.get("tx_pps") or 800) + random.randint(-600, 1000))
            p["util_pct"] = min(99, int((p.get("rx_pps") or 0) / 1000))
            if random.random() < 0.05:
                p["errors"] = (p.get("errors") or 0) + 1
            if random.random() < 0.03:
                p["drops"] = (p.get("drops") or 0) + 1


# ── Cables ─────────────────────────────────────────────────────────────────

CABLE_CATALOG = [
    {"type": "Cat6A", "media": "copper", "connector": "RJ45", "max_m": 100},
    {"type": "Cat8", "media": "copper", "connector": "RJ45", "max_m": 30},
    {"type": "DAC", "media": "twinax", "connector": "QSFP", "max_m": 3},
    {"type": "AOC", "media": "fiber", "connector": "QSFP", "max_m": 100},
    {"type": "Fiber-LC", "media": "fiber", "connector": "LC", "max_m": 2000},
    {"type": "Fiber-SC", "media": "fiber", "connector": "SC", "max_m": 2000},
    {"type": "Fiber-ST", "media": "fiber", "connector": "ST", "max_m": 2000},
    {"type": "MPO", "media": "fiber", "connector": "MPO-24", "max_m": 300},
    {"type": "OSFP", "media": "fiber", "connector": "OSFP", "max_m": 100},
    {"type": "Power-C13", "media": "power", "connector": "C13", "max_m": 3},
    {"type": "Power-C19", "media": "power", "connector": "C19", "max_m": 3},
    {"type": "Ground", "media": "ground", "connector": "lug", "max_m": 5},
    {"type": "USB", "media": "copper", "connector": "USB-A", "max_m": 5},
    {"type": "Serial", "media": "copper", "connector": "DB9", "max_m": 15},
    {"type": "VGA", "media": "copper", "connector": "DE-15", "max_m": 15},
    {"type": "HDMI", "media": "copper", "connector": "HDMI", "max_m": 15},
    {"type": "DisplayPort", "media": "copper", "connector": "DP", "max_m": 15},
    {"type": "KVM", "media": "copper", "connector": "multi", "max_m": 10},
    {"type": "IPMI", "media": "copper", "connector": "RJ45", "max_m": 100},
    {"type": "Console", "media": "copper", "connector": "RJ45", "max_m": 15},
]


def enrich_cables(cables: list) -> list:
    """Add catalog metadata, bend path, label, route for each cable."""
    by_type = {c["type"]: c for c in CABLE_CATALOG}
    # aliases
    by_type["fiber"] = by_type["Fiber-LC"]
    by_type["DAC"] = by_type["DAC"]
    out = []
    for i, c in enumerate(cables or []):
        ctype = c.get("type") or "Cat6A"
        meta = by_type.get(ctype) or by_type.get("Cat6A")
        enriched = dict(c)
        enriched.setdefault("catalog_type", meta["type"])
        enriched.setdefault("media", meta["media"])
        enriched.setdefault("connector", meta["connector"])
        enriched.setdefault("length_m", min(meta["max_m"], 2 + (i % 5)))
        enriched.setdefault("label", c.get("label") or f"{c.get('id', 'CBL')}-{ctype}")
        enriched.setdefault("route", c.get("route") or ["server-rear", "horizontal-manager", "vertical-manager", "tor"])
        enriched.setdefault("bend_radius_mm", 40 if meta["media"] == "fiber" else 25)
        enriched.setdefault("tension_n", 2.5 + i * 0.3)
        enriched.setdefault("damaged", c.get("status") == "damaged")
        enriched.setdefault("status", c.get("status") or "seated")
        out.append(enriched)
    return out


def cable_action(cables: list, cable_id: str, op: str, **kwargs) -> tuple[bool, str, dict | None]:
    target = next((c for c in cables if c.get("id") == cable_id), None)
    if not target and cables:
        target = cables[0]
    if not target:
        return False, "No cable", None
    if op == "damage":
        target["status"] = "damaged"
        target["damaged"] = True
        return True, f"{target['id']} damaged", target
    if op == "repair":
        target["status"] = "seated"
        target["damaged"] = False
        return True, f"{target['id']} repaired", target
    if op == "label":
        target["label"] = kwargs.get("label") or target.get("label")
        return True, f"Labeled {target['id']}", target
    if op == "route":
        path = kwargs.get("route") or target.get("route")
        if isinstance(path, str):
            path = [p.strip() for p in path.split(">") if p.strip()]
        target["route"] = path
        return True, f"Rerouted {target['id']}", target
    if op == "replace":
        ctype = kwargs.get("cable_type") or target.get("catalog_type") or target.get("type")
        meta = next((c for c in CABLE_CATALOG if c["type"] == ctype), CABLE_CATALOG[0])
        target["type"] = meta["type"]
        target["catalog_type"] = meta["type"]
        target["media"] = meta["media"]
        target["connector"] = meta["connector"]
        target["status"] = "seated"
        target["damaged"] = False
        return True, f"Replaced with {meta['type']}", target
    if op == "bend":
        target["bend_radius_mm"] = float(kwargs.get("bend_radius_mm") or target.get("bend_radius_mm") or 30)
        target["tension_n"] = float(kwargs.get("tension_n") or target.get("tension_n") or 3)
        return True, f"Bend updated on {target['id']}", target
    return False, f"Unknown cable op {op}", None


# ── Storage facades ────────────────────────────────────────────────────────

def build_storage_stack(role: str | None = None) -> dict:
    """SAN/NAS/Ceph/ZFS + local NVMe/SATA/SAS bay model."""
    is_storage = role == "storage"
    return {
        "local_bays": [
            {"id": "BAY0", "form": "U.2", "bus": "NVMe", "model": "Samsung PM9A3", "size_gb": 1920, "status": "online", "smart": "OK", "temp_c": 38, "wear_pct": 4},
            {"id": "BAY1", "form": "U.3", "bus": "NVMe", "model": "Samsung PM9A3", "size_gb": 1920, "status": "online", "smart": "OK", "temp_c": 39, "wear_pct": 5},
            {"id": "BAY2", "form": "E3.S", "bus": "NVMe", "model": "Solidigm D7-P5810", "size_gb": 3200, "status": "online", "smart": "OK", "temp_c": 41, "wear_pct": 2},
            {"id": "BAY3", "form": "E1.S", "bus": "NVMe", "model": "Micron 7450", "size_gb": 3840, "status": "empty", "smart": None, "temp_c": None, "wear_pct": None},
            {"id": "BAY4", "form": "2.5\"", "bus": "SATA", "model": "Samsung 870", "size_gb": 960, "status": "online", "smart": "OK", "temp_c": 32, "wear_pct": 11},
            {"id": "BAY5", "form": "3.5\"", "bus": "SAS", "model": "Seagate Exos", "size_gb": 12000, "status": "online", "smart": "OK", "temp_c": 29, "wear_pct": 18},
        ],
        "jbod": {
            "id": "JBOD-1",
            "shelves": 1,
            "drives": 12 if is_storage else 0,
            "status": "online" if is_storage else "not_attached",
        },
        "san": {
            "fabric": "FC-32G",
            "wwpns": ["20:00:00:11:22:33:44:55", "20:00:00:11:22:33:44:56"],
            "luns": [
                {"id": "LUN10", "size_gb": 2048, "mapped": True, "path": "multipath"},
                {"id": "LUN20", "size_gb": 4096, "mapped": is_storage, "path": "multipath"},
            ] if is_storage or True else [],
            "status": "online",
        },
        "nas": {
            "protocol": ["NFS", "SMB"],
            "exports": [
                {"path": "/vol/vmware", "clients": "10.10.0.0/16", "status": "exported"},
                {"path": "/vol/backups", "clients": "10.20.0.0/16", "status": "exported"},
            ],
            "status": "online" if is_storage else "client",
        },
        "zfs": {
            "pools": [
                {"name": "rpool", "raid": "mirror", "size_tb": 1.8, "health": "ONLINE", "scrub": "idle"},
                {"name": "tank", "raid": "raidz2", "size_tb": 48 if is_storage else 0, "health": "ONLINE" if is_storage else "N/A", "scrub": "idle"},
            ],
        },
        "ceph": {
            "cluster": "ceph-fixitlab",
            "mons": 3 if is_storage else 0,
            "osds": 12 if is_storage else 0,
            "health": "HEALTH_OK" if is_storage else "N/A",
            "pools": ["vms", "images", "backups"] if is_storage else [],
            "pg_states": {"active+clean": 1024} if is_storage else {},
        },
        "mode": "jbod_ok",  # jbod | raid | san | nas
    }


def storage_action(stack: dict, op: str, **kwargs) -> tuple[bool, str]:
    if op == "fail_bay":
        bay_id = kwargs.get("bay_id")
        bay = next((b for b in stack.get("local_bays") or [] if b.get("id") == bay_id), None)
        if not bay:
            return False, "Bay not found"
        bay["status"] = "failed"
        bay["smart"] = "FAILING"
        return True, f"{bay_id} failed"
    if op == "replace_bay":
        bay_id = kwargs.get("bay_id")
        bay = next((b for b in stack.get("local_bays") or [] if b.get("id") == bay_id), None)
        if not bay:
            return False, "Bay not found"
        bay["status"] = "online"
        bay["smart"] = "OK"
        bay["wear_pct"] = 0
        return True, f"{bay_id} replaced"
    if op == "zfs_scrub":
        for p in stack.get("zfs", {}).get("pools") or []:
            if p.get("health") == "ONLINE":
                p["scrub"] = "completed"
        return True, "ZFS scrub completed"
    if op == "ceph_status":
        return True, stack.get("ceph", {}).get("health") or "N/A"
    if op == "map_lun":
        lun_id = kwargs.get("lun_id") or "LUN20"
        for lun in stack.get("san", {}).get("luns") or []:
            if lun.get("id") == lun_id:
                lun["mapped"] = True
                return True, f"{lun_id} mapped"
        return False, "LUN not found"
    if op == "export_nfs":
        path = kwargs.get("path") or "/vol/new"
        stack.setdefault("nas", {}).setdefault("exports", []).append(
            {"path": path, "clients": kwargs.get("clients") or "10.10.0.0/16", "status": "exported"},
        )
        return True, f"Exported {path}"
    if op == "set_mode":
        mode = kwargs.get("mode") or "raid"
        stack["mode"] = mode
        return True, f"Storage mode {mode}"
    return False, f"Unknown storage op {op}"
