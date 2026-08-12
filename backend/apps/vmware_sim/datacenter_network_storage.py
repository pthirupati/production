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
    by_vendor = {
        "Arista": {"os": "EOS", "cli_style": "arista"},
        "Cisco": {"os": "NX-OS", "cli_style": "cisco"},
        "Juniper": {"os": "Junos", "cli_style": "juniper"},
        "NVIDIA": {"os": "Cumulus/Spectrum", "cli_style": "nvidia"},
        "Mellanox": {"os": "MLNX-OS", "cli_style": "nvidia"},
        "Dell": {"os": "OS10", "cli_style": "cisco"},
        "Extreme": {"os": "EXOS", "cli_style": "extreme"},
    }
    fallback = [
        {"vendor": "Arista", "os": "EOS", "cli_style": "arista", "mgmt_ip": "10.0.0.11"},
        {"vendor": "Cisco", "os": "NX-OS", "cli_style": "cisco", "mgmt_ip": "10.0.0.12"},
        {"vendor": "Juniper", "os": "Junos", "cli_style": "juniper", "mgmt_ip": "10.0.0.13"},
        {"vendor": "NVIDIA", "os": "Cumulus/Spectrum", "cli_style": "nvidia", "mgmt_ip": "10.0.0.14"},
    ]

    def _infer_vendor(model: str) -> str | None:
        m = (model or "").lower()
        if "arista" in m or "7050" in m or "7280" in m:
            return "Arista"
        if "cisco" in m or "nexus" in m or "catalyst" in m:
            return "Cisco"
        if "juniper" in m or "qfx" in m or "mx" in m:
            return "Juniper"
        if "spectrum" in m or "sn3700" in m or "sn5600" in m or "nvidia" in m:
            return "NVIDIA"
        if "mellanox" in m:
            return "Mellanox"
        if "dell" in m or "s5248" in m:
            return "Dell"
        if "extreme" in m:
            return "Extreme"
        return None

    for i, sw in enumerate(network.get("switches") or []):
        inferred = _infer_vendor(sw.get("model") or "")
        meta = by_vendor.get(inferred) if inferred else None
        fb = fallback[i % len(fallback)]
        vendor = inferred or sw.get("vendor") or fb["vendor"]
        info = meta or by_vendor.get(vendor) or fb
        sw.setdefault("vendor", vendor)
        sw.setdefault("os", info.get("os") or fb["os"])
        sw.setdefault("cli_style", info.get("cli_style") or fb["cli_style"])
        sw.setdefault("mgmt_ip", fb["mgmt_ip"])
        # Prefer inferred vendor over stale default when model is known
        if inferred:
            sw["vendor"] = inferred
            sw["os"] = info["os"]
            sw["cli_style"] = info["cli_style"]
        sw.setdefault("protocols", {
            "bgp": {"asn": 65001 + i, "peers": 2, "established": 2 if i == 0 else 1, "status": "up"},
            "ospf": {"area": "0.0.0.0", "neighbors": 1, "status": "full"},
            "stp": {"mode": "RSTP", "root": i == 0, "status": "forwarding"},
            "lacp": {"bundles": [{"id": "Po1", "members": [7, 8], "status": "up"}] if i == 0 else []},
            "vxlan": {
                "enabled": i == 0,
                "vnis": [10010, 10020] if i == 0 else [],
                "source_interface": "Loopback0",
            },
            "evpn": {
                "enabled": i == 0,
                "status": "established" if i == 0 else "disabled",
                "rd": f"65001:{100 + i}",
                "rt_import": ["65001:10010"] if i == 0 else [],
                "rt_export": ["65001:10010"] if i == 0 else [],
                "vteps": ["10.0.0.11", "10.0.0.12"] if i == 0 else [],
                "neighbors": ["10.0.0.1"] if i == 0 else [],
            },
            "mpls": {
                "enabled": False,
                "ldp_router_id": sw.get("mgmt_ip") or f"10.0.0.{11 + i}",
                "ldp_neighbors": [],
                "labels": [],
                "status": "disabled",
            },
            "vlan": {"ids": sorted({p.get("vlan") for p in sw.get("ports") or [] if p.get("vlan")})},
        })
        # Backfill richer keys on already-seeded protocol dicts
        mpls = sw["protocols"].setdefault("mpls", {"enabled": False})
        mpls.setdefault("ldp_router_id", sw.get("mgmt_ip") or "10.0.0.11")
        mpls.setdefault("ldp_neighbors", [])
        mpls.setdefault("labels", [])
        mpls.setdefault("status", "established" if mpls.get("enabled") else "disabled")
        evpn = sw["protocols"].setdefault("evpn", {})
        evpn.setdefault("rd", f"65001:{100 + i}")
        evpn.setdefault("rt_import", [])
        evpn.setdefault("rt_export", [])
        evpn.setdefault("vteps", [])
        evpn.setdefault("neighbors", [])
        vx = sw["protocols"].setdefault("vxlan", {})
        vx.setdefault("source_interface", "Loopback0")
        vx.setdefault("vnis", [])
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
    network["cable_topology"] = build_cable_topology(network)
    return network


def build_cable_topology(network: dict) -> list[dict]:
    """Derive real switch↔endpoint links from port ``connected_to`` (audit D14).

    Prefer this over geometry-synthesized cables: a down port or missing peer
    produces no link. Media is inferred from speed (fiber ≥25G, else copper).
    """
    links: list[dict] = []
    switches = network.get("switches") or []
    for sw in switches:
        sw_id = sw.get("id") or sw.get("hostname") or "switch"
        role = "spine" if "core" in str(sw_id).lower() else "leaf"
        for port in sw.get("ports") or []:
            peer = port.get("connected_to")
            if not peer or port.get("status") != "up":
                continue
            speed = str(port.get("speed") or "")
            media = "fiber" if any(x in speed.upper() for x in ("25G", "40G", "100G", "400G")) else "copper"
            peer_is_switch = any(
                peer == (o.get("id") or o.get("hostname")) for o in switches
            )
            links.append({
                "id": f"{sw_id}-p{port.get('port')}-{peer}",
                "from": sw_id,
                "from_port": port.get("port"),
                "to": peer,
                "to_port": None,
                "speed": speed or None,
                "media": media,
                "vlan": port.get("vlan"),
                "role": "spine-leaf" if peer_is_switch else "access",
                "from_role": role,
            })
    return links


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
            "  show lacp | show spanning-tree | show vxlan | show mpls | show evpn",
            "  show bgp l2vpn evpn summary | show mpls ldp neighbor | show mpls forwarding",
            "  conf t / configure | interface EthernetN | no shutdown | shutdown",
            "  switchport access vlan <id> | mpls ip | no mpls ip | mpls ldp router-id <ip>",
            "  nv overlay evpn | address-family l2vpn evpn | neighbor <ip> activate",
            "  vni <id> | route-target import/export <rt> | exit | end | clear counters",
        ]

    if lower.startswith("show version") or lower == "show ver" or lower == "show system information":
        lines = [
            f"{sw.get('vendor')} {sw.get('os')} — {sw.get('hostname')}",
            f"Hardware: {sw.get('model')}",
            f"Management IP: {sw.get('mgmt_ip')}",
            f"Uptime: 142 days, 3:11:08",
        ]
    elif ("interface" in lower and lower.startswith("show")) or lower in ("show interfaces terse", "show interface terse"):
        hdr = "Interface  Admin  Link  Proto  Speed  VLAN  RX  TX  Err" if style == "juniper" else (
            "Port  Status  Speed  VLAN  RX(pps)  TX(pps)  Err  Drop  Lat(us)  Util%"
        )
        lines = [hdr]
        for p in ports:
            if style == "juniper":
                lines.append(
                    f"et-{p.get('port')}/0/0  {'up' if p.get('status')=='up' else 'down':<5} "
                    f"{p.get('status'):<4} inet  {str(p.get('speed') or '-'):<6} "
                    f"{str(p.get('vlan') or '-'):<5} {p.get('rx_pps') or 0} {p.get('tx_pps') or 0} {p.get('errors') or 0}"
                )
            else:
                lines.append(
                    f"{p.get('port'):<5} {p.get('status'):<7} {str(p.get('speed') or '-'):<6} "
                    f"{str(p.get('vlan') or '-'):<5} {p.get('rx_pps') or 0:<8} {p.get('tx_pps') or 0:<8} "
                    f"{p.get('errors') or 0:<4} {p.get('drops') or 0:<5} {str(p.get('latency_us') or '-'):<8} "
                    f"{p.get('util_pct') or 0}"
                )
    elif "vlan" in lower and lower.startswith("show"):
        vlans = proto.get("vlan", {}).get("ids") or []
        lines = [f"VLAN  Name"] + [f"{v:<5} vlan{v}" for v in vlans] or ["No VLANs configured"]
    elif "mpls" in lower and lower.startswith("show"):
        m = proto.get("mpls") or {}
        if "ldp" in lower:
            neighbors = m.get("ldp_neighbors") or []
            lines = [
                f"LDP router-id {m.get('ldp_router_id')} status={m.get('status')}",
                "Peer            State",
            ] + ([f"{n:<15} Operational" for n in neighbors] or ["(no LDP neighbors)"])
        elif "forward" in lower:
            labels = m.get("labels") or []
            lines = ["In Label  Out Label  Prefix / FEC", "--------  ---------  -----------"]
            if labels:
                for lab in labels:
                    lines.append(
                        f"{lab.get('in', '-'):<9} {lab.get('out', '-'):<10} {lab.get('fec', '-')}"
                    )
            else:
                lines.append("(empty FIB — enable MPLS first)")
        else:
            lines = [
                f"MPLS enabled={m.get('enabled')} status={m.get('status')}",
                f"LDP router-id {m.get('ldp_router_id')}",
                f"LDP neighbors: {len(m.get('ldp_neighbors') or [])}",
                f"Labels in FIB: {len(m.get('labels') or [])}",
            ]
    elif "l2vpn evpn" in lower or "evpn" in lower and lower.startswith("show") or lower.startswith("show evpn"):
        ev = proto.get("evpn") or {}
        vx = proto.get("vxlan") or {}
        if "summary" in lower or "l2vpn" in lower:
            lines = [
                f"BGP L2VPN EVPN — enabled={ev.get('enabled')} status={ev.get('status')}",
                f"RD {ev.get('rd')}  RT import {ev.get('rt_import')}  RT export {ev.get('rt_export')}",
                "Neighbor        State",
            ]
            for n in (ev.get("neighbors") or []):
                lines.append(f"{n:<15} {'Established' if ev.get('enabled') else 'Idle'}")
            if not ev.get("neighbors"):
                lines.append("(no EVPN neighbors — activate under address-family)")
        else:
            lines = [
                f"EVPN enabled={ev.get('enabled')} status={ev.get('status')}",
                f"RD={ev.get('rd')} VTEPs={ev.get('vteps')}",
                f"VNIs={vx.get('vnis')} source={vx.get('source_interface')}",
            ]
    elif "vxlan" in lower and lower.startswith("show"):
        vx = proto.get("vxlan") or {}
        ev = proto.get("evpn") or {}
        lines = [
            f"VXLAN enabled={vx.get('enabled')} VNIs={vx.get('vnis')}",
            f"Source interface {vx.get('source_interface')}",
            f"EVPN enabled={ev.get('enabled')} status={ev.get('status')}",
        ]
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
    elif lower in ("mpls ip", "no mpls ip") or lower.startswith("mpls ldp router-id"):
        m = proto.setdefault("mpls", {})
        if lower == "no mpls ip":
            m["enabled"] = False
            m["status"] = "disabled"
            m["ldp_neighbors"] = []
            m["labels"] = []
            lines = ["MPLS disabled"]
        elif lower.startswith("mpls ldp router-id"):
            rid = cmd.split()[-1] if len(cmd.split()) >= 4 else (sw.get("mgmt_ip") or "10.0.0.11")
            m["ldp_router_id"] = rid
            lines = [f"LDP router-id set to {rid}"]
        else:
            m["enabled"] = True
            m["status"] = "established"
            m["ldp_neighbors"] = list({*(m.get("ldp_neighbors") or []), "10.0.0.1", "10.0.0.2"})
            m["labels"] = m.get("labels") or [
                {"in": 16001, "out": 3, "fec": "10.10.0.0/16"},
                {"in": 16002, "out": 3, "fec": "10.20.0.0/16"},
            ]
            lines = ["MPLS enabled; LDP neighbors discovered"]
    elif lower in ("nv overlay evpn", "no nv overlay evpn") or lower == "address-family l2vpn evpn":
        ev = proto.setdefault("evpn", {})
        vx = proto.setdefault("vxlan", {})
        if lower.startswith("no "):
            ev["enabled"] = False
            ev["status"] = "disabled"
            vx["enabled"] = False
            lines = ["EVPN overlay disabled"]
        else:
            ev["enabled"] = True
            ev["status"] = "established"
            vx["enabled"] = True
            if not vx.get("vnis"):
                vx["vnis"] = [10010, 10020]
            lines = ["EVPN overlay enabled (address-family l2vpn evpn)"]
    elif lower.startswith("neighbor ") and "activate" in lower:
        ev = proto.setdefault("evpn", {})
        parts = cmd.split()
        peer = parts[1] if len(parts) > 1 else "10.0.0.1"
        neighbors = ev.setdefault("neighbors", [])
        if peer not in neighbors:
            neighbors.append(peer)
        ev["enabled"] = True
        ev["status"] = "established"
        lines = [f"EVPN neighbor {peer} activated"]
    elif lower.startswith("vni ") or lower.startswith("member vni"):
        vx = proto.setdefault("vxlan", {})
        ev = proto.setdefault("evpn", {})
        tokens = [t for t in cmd.replace("/", " ").split() if t.isdigit()]
        vni = int(tokens[0]) if tokens else 10010
        vnis = vx.setdefault("vnis", [])
        if vni not in vnis:
            vnis.append(vni)
        vx["enabled"] = True
        ev["enabled"] = True
        ev["status"] = "established"
        lines = [f"VNI {vni} member added to NVE/VXLAN"]
    elif "route-target" in lower:
        ev = proto.setdefault("evpn", {})
        parts = cmd.split()
        rt = parts[-1] if parts else "65001:10010"
        if "import" in lower:
            rts = ev.setdefault("rt_import", [])
            if rt not in rts:
                rts.append(rt)
            lines = [f"route-target import {rt}"]
        else:
            rts = ev.setdefault("rt_export", [])
            if rt not in rts:
                rts.append(rt)
            lines = [f"route-target export {rt}"]
        ev["enabled"] = True
        ev["status"] = "established"
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
