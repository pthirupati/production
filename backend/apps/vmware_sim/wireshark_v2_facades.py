"""Wireshark V2 facades — Expert Info, Endpoints, Flow Graph.

Learner language: Lab Environment / Lab Server — never Simulation/Sandbox/Mock.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed_v2() -> dict[str, Any]:
    return {
        "expert_info": [],
        "endpoints": [],
        "flow_graph": [],
        "analysis_at": None,
    }


def ensure_v2(state: dict) -> None:
    for key, value in seed_v2().items():
        if key not in state or state.get(key) is None:
            state[key] = value if not isinstance(value, list) else list(value)


def _packets(state: dict) -> list[dict]:
    """Prefer display-filtered view if available via common helpers; else all."""
    # Engines store all_packets; captured/filtered computed elsewhere.
    pkts = state.get("_v2_view_packets")
    if pkts is not None:
        return pkts
    return list(state.get("all_packets") or [])


def rebuild_analysis(state: dict, packets: list[dict] | None = None) -> dict:
    ensure_v2(state)
    pkts = packets if packets is not None else _packets(state)
    expert: list[dict] = []
    endpoints: dict[str, dict] = {}
    flows: list[dict] = []

    for p in pkts:
        proto = (p.get("protocol") or p.get("proto") or "").upper()
        src = p.get("src") or p.get("source") or ""
        dst = p.get("dst") or p.get("destination") or ""
        info = str(p.get("info") or "")
        length = int(p.get("length") or p.get("len") or 0)
        no = p.get("no") or p.get("number")

        for addr in (src, dst):
            if not addr:
                continue
            ep = endpoints.setdefault(addr, {
                "address": addr, "packets": 0, "bytes": 0, "tx_packets": 0, "rx_packets": 0,
            })
            ep["packets"] += 1
            ep["bytes"] += length
            if addr == src:
                ep["tx_packets"] += 1
            else:
                ep["rx_packets"] += 1

        # Expert heuristics
        low = info.lower()
        if "retransmission" in low or "retrans" in low:
            expert.append({"severity": "Note", "group": "Sequence", "protocol": proto, "summary": "TCP Retransmission", "packet": no})
        elif "reset" in low or "rst" in low.split():
            expert.append({"severity": "Warn", "group": "Sequence", "protocol": proto, "summary": "Connection reset (RST)", "packet": no})
        elif "malformed" in low:
            expert.append({"severity": "Error", "group": "Malformed", "protocol": proto, "summary": "Malformed packet", "packet": no})
        elif proto == "DNS" and ("servfail" in low or "nxdomain" in low):
            expert.append({"severity": "Warn", "group": "Protocol", "protocol": "DNS", "summary": info[:80], "packet": no})
        elif proto == "HTTP" and (" 4" in info or " 5" in info):
            expert.append({"severity": "Note", "group": "Protocol", "protocol": "HTTP", "summary": info[:80], "packet": no})

        if len(flows) < 60 and src and dst:
            flows.append({
                "no": no,
                "time": p.get("time") or p.get("timestamp") or "",
                "src": src,
                "dst": dst,
                "proto": proto,
                "label": info[:48] or proto,
            })

    # Seed a couple of notes if capture is quiet (still useful for UI demos)
    if not expert and pkts:
        expert.append({
            "severity": "Comment", "group": "Protocol", "protocol": "Frame",
            "summary": f"Capture contains {len(pkts)} packets — no severe expert events",
            "packet": pkts[0].get("no"),
        })

    state["expert_info"] = expert[:100]
    state["endpoints"] = sorted(endpoints.values(), key=lambda e: -e["packets"])
    state["flow_graph"] = flows
    state["analysis_at"] = _now()
    return {
        "expert_info": state["expert_info"],
        "endpoints": state["endpoints"],
        "flow_graph": state["flow_graph"],
        "analysis_at": state["analysis_at"],
    }


def apply_v2_action(state: dict, action: str, payload: dict | None = None) -> dict | None:
    payload = payload or {}
    ensure_v2(state)

    if action in ("refresh_analysis", "compute_expert", "compute_endpoints", "compute_flow_graph"):
        packets = payload.get("packets")  # optional client override — unused; engine passes view
        analysis = rebuild_analysis(state, packets)
        return {"ok": True, "message": "Analysis refreshed", **analysis}

    return None


def v2_public(state: dict) -> dict:
    ensure_v2(state)
    if not state.get("analysis_at"):
        rebuild_analysis(state)
    return {
        "expert_info": state.get("expert_info") or [],
        "endpoints": state.get("endpoints") or [],
        "flow_graph": state.get("flow_graph") or [],
        "analysis_at": state.get("analysis_at"),
    }
