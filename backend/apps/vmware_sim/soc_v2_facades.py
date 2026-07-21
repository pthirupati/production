"""CyberOps SOC V2 facades — PAM, vulns, firewall, pcap, compliance (+ IoC/playbook ops)."""

from __future__ import annotations

import random
import time
from typing import Any

_HEX = "0123456789abcdef"


def _hex(n: int = 6) -> str:
    return "".join(random.choice(_HEX) for _ in range(n))


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def seed_v2() -> dict[str, Any]:
    return {
        "pam_sessions": [
            {
                "id": f"PSM-{_hex(4)}", "user": "jsmith", "target": "WIN-SRV-03",
                "protocol": "RDP", "status": "Active", "started": _now(),
                "duration_min": 4, "suspicious": 2,
            },
        ],
        "vulnerabilities": [
            {
                "id": f"VUL-{_hex(4)}", "cve": "CVE-2024-4577", "cvss": 9.8,
                "epss": 0.92, "asset": "WIN-WEB-01", "status": "Open",
                "title": "PHP CGI Argument Injection",
            },
            {
                "id": f"VUL-{_hex(4)}", "cve": "CVE-2024-3400", "cvss": 10.0,
                "epss": 0.97, "asset": "FW-EDGE-01", "status": "Open",
                "title": "PAN-OS Command Injection",
            },
        ],
        "firewall_policies": [
            {
                "id": f"FW-{_hex(4)}", "name": "Allow-Corp-Web", "action": "allow",
                "src_zone": "trust", "dst_zone": "untrust", "app": "ssl",
                "enabled": True, "priority": 100,
            },
            {
                "id": f"FW-{_hex(4)}", "name": "Block-Threats", "action": "reset-both",
                "src_zone": "any", "dst_zone": "any", "app": "any",
                "enabled": True, "priority": 10,
            },
        ],
        "packet_captures": [
            {
                "id": f"PCAP-{_hex(4)}", "iface": "ethernet1/1", "filter": "host 185.220.101.42",
                "status": "Completed", "packets": 4821, "bytes": 2_300_000,
            },
        ],
        "compliance_frameworks": [
            {"id": "cis", "name": "CIS Controls v8.0", "score_pct": 84, "passed": 43, "total": 51},
            {"id": "nist", "name": "NIST CSF 2.0", "score_pct": 76, "passed": 86, "total": 112},
            {"id": "pci", "name": "PCI DSS v4.0", "score_pct": 88, "passed": 247, "total": 282},
        ],
    }


def ensure_v2(state: dict) -> None:
    for k, v in seed_v2().items():
        if k not in state or state.get(k) is None:
            state[k] = v


def apply_v2_action(state: dict, action: str, payload: dict) -> dict | None:
    if action == "start_pam_session":
        item = {
            "id": f"PSM-{_hex(4)}",
            "user": payload.get("user") or "analyst1",
            "target": payload.get("target") or "LINUX-DB-01",
            "protocol": payload.get("protocol") or "SSH",
            "status": "Active", "started": _now(), "duration_min": 0, "suspicious": 0,
        }
        state.setdefault("pam_sessions", []).insert(0, item)
        return {"ok": True, "message": f"PAM session {item['id']} started", "session": item}

    if action == "end_pam_session":
        sid = payload.get("id") or ""
        sess = next((s for s in state.get("pam_sessions") or [] if s.get("id") == sid), None)
        if not sess and state.get("pam_sessions"):
            sess = state["pam_sessions"][0]
        if not sess:
            return {"ok": False, "error": "PAM session not found"}
        sess["status"] = "Ended"
        return {"ok": True, "message": f"Terminated {sess['id']}", "session": sess}

    if action == "mark_vuln_fixed":
        vid = payload.get("id") or payload.get("cve") or ""
        vuln = next(
            (v for v in state.get("vulnerabilities") or []
             if v.get("id") == vid or v.get("cve") == vid),
            None,
        )
        if not vuln:
            return {"ok": False, "error": "Vulnerability not found"}
        vuln["status"] = "Fixed"
        return {"ok": True, "message": f"Marked {vuln['cve']} fixed", "vuln": vuln}

    if action == "scan_asset":
        asset = payload.get("asset") or "WIN-WEB-01"
        item = {
            "id": f"VUL-{_hex(4)}",
            "cve": f"CVE-2024-{random.randint(1000, 9999)}",
            "cvss": round(random.uniform(4.0, 9.8), 1),
            "epss": round(random.uniform(0.1, 0.9), 2),
            "asset": asset, "status": "Open",
            "title": "Newly discovered vulnerability",
        }
        state.setdefault("vulnerabilities", []).insert(0, item)
        return {"ok": True, "message": f"Scan complete on {asset}", "vuln": item}

    if action == "create_fw_rule":
        name = (payload.get("name") or f"Rule-{_hex(3)}").strip()
        item = {
            "id": f"FW-{_hex(4)}", "name": name,
            "action": payload.get("action") or "deny",
            "src_zone": payload.get("src_zone") or "untrust",
            "dst_zone": payload.get("dst_zone") or "trust",
            "app": payload.get("app") or "any",
            "enabled": True, "priority": int(payload.get("priority") or 50),
        }
        state.setdefault("firewall_policies", []).insert(0, item)
        return {"ok": True, "message": f"Created firewall rule {name}", "rule": item}

    if action == "toggle_fw_rule":
        rid = payload.get("id") or payload.get("name") or ""
        rule = next(
            (r for r in state.get("firewall_policies") or []
             if r.get("id") == rid or r.get("name") == rid),
            None,
        )
        if not rule:
            return {"ok": False, "error": "Firewall rule not found"}
        rule["enabled"] = not bool(rule.get("enabled"))
        return {"ok": True, "message": f"{rule['name']} → {'enabled' if rule['enabled'] else 'disabled'}", "rule": rule}

    if action == "start_pcap":
        item = {
            "id": f"PCAP-{_hex(4)}",
            "iface": payload.get("iface") or "ethernet1/1",
            "filter": payload.get("filter") or "tcp port 443",
            "status": "Capturing", "packets": 0, "bytes": 0,
        }
        state.setdefault("packet_captures", []).insert(0, item)
        return {"ok": True, "message": f"Capture {item['id']} started", "pcap": item}

    if action == "stop_pcap":
        pid = payload.get("id") or ""
        cap = next((c for c in state.get("packet_captures") or [] if c.get("id") == pid), None)
        if not cap and state.get("packet_captures"):
            cap = next((c for c in state["packet_captures"] if c.get("status") == "Capturing"), state["packet_captures"][0])
        if not cap:
            return {"ok": False, "error": "Capture not found"}
        cap["status"] = "Completed"
        cap["packets"] = random.randint(500, 8000)
        cap["bytes"] = cap["packets"] * random.randint(200, 900)
        return {"ok": True, "message": f"Capture {cap['id']} stopped", "pcap": cap}

    if action == "run_compliance_check":
        frameworks = state.setdefault("compliance_frameworks", seed_v2()["compliance_frameworks"])
        for fw in frameworks:
            delta = random.randint(-2, 3)
            fw["score_pct"] = max(50, min(100, int(fw.get("score_pct") or 70) + delta))
            fw["passed"] = min(int(fw.get("total") or 100), int(fw.get("passed") or 0) + max(0, delta))
            fw["last_check"] = _now()
        return {"ok": True, "message": "Compliance assessment refreshed", "frameworks": frameworks}

    if action == "add_ioc":
        ioc = {
            "id": f"IOC-{_hex(4)}",
            "type": payload.get("type") or "ip",
            "value": payload.get("value") or "185.220.101.42",
            "tlp": payload.get("tlp") or "AMBER",
            "source": payload.get("source") or "Manual",
            "sightings": 1, "created": _now(),
        }
        state.setdefault("iocs", []).insert(0, ioc)
        return {"ok": True, "message": f"Added IoC {ioc['value']}", "ioc": ioc}

    return None
