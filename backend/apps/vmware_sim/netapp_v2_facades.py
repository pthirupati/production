"""NetApp ONTAP System Manager V2 facades — FlexGroup, SnapLock, SVM-DR, S3, ARP, MAV."""

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
        "flexgroups": [
            {"id": f"fg-{_hex()}", "name": "fg_media", "svm": "svm-nas",
             "size_tb": 40, "constituents": 8, "used_pct": 62, "health": "healthy"},
        ],
        "snaplock_volumes": [
            {"id": f"sl-{_hex()}", "name": "vol_compliance", "svm": "svm-nas",
             "type": "Compliance", "retention_days": 2555, "worm_files": 1204},
        ],
        "svm_dr": [
            {"id": f"svdr-{_hex()}", "source_svm": "svm-nas", "dest_svm": "svm-dr",
             "state": "snapmirrored", "lag_sec": 42, "last_transfer": _now()},
        ],
        "flexcaches": [
            {"id": f"fc-{_hex()}", "name": "cache_edge", "origin": "vol_data",
             "svm": "svm-edge", "size_gb": 500, "hit_ratio_pct": 87},
        ],
        "s3_buckets": [
            {"id": f"s3-{_hex()}", "name": "backup-objects", "svm": "svm-nas",
             "capacity_gb": 2048, "objects": 15820, "versioning": True},
        ],
        "arp_events": [
            {"id": f"arp-{_hex()}", "volume": "vol_data", "mode": "active",
             "severity": "Medium", "detail": "High-entropy write burst detected", "time": _now()},
        ],
        "mav_approvals": [
            {"id": f"mav-{_hex()}", "operation": "volume delete", "target": "vol_temp",
             "requested_by": "admin", "status": "Pending", "approvals": "0/2"},
        ],
    }


def ensure_v2(state: dict) -> None:
    for k, v in seed_v2().items():
        if k not in state or state.get(k) is None:
            state[k] = v


def apply_v2_action(state: dict, action: str, payload: dict) -> dict | None:
    if action == "create_flexgroup":
        name = (payload.get("name") or f"fg_{_hex(4)}").strip()
        item = {
            "id": f"fg-{_hex()}", "name": name,
            "svm": payload.get("svm") or "svm-nas",
            "size_tb": float(payload.get("size_tb") or 10),
            "constituents": int(payload.get("constituents") or 4),
            "used_pct": 0, "health": "healthy",
        }
        state.setdefault("flexgroups", []).append(item)
        return {"ok": True, "message": f"Created FlexGroup {name}", "flexgroup": item}

    if action == "enable_snaplock":
        name = (payload.get("name") or f"vol_worm_{_hex(3)}").strip()
        item = {
            "id": f"sl-{_hex()}", "name": name,
            "svm": payload.get("svm") or "svm-nas",
            "type": payload.get("type") or "Enterprise",
            "retention_days": int(payload.get("retention_days") or 365),
            "worm_files": 0,
        }
        state.setdefault("snaplock_volumes", []).append(item)
        return {"ok": True, "message": f"Enabled SnapLock on {name}", "volume": item}

    if action == "svm_dr_failover":
        rid = payload.get("id") or ""
        rel = next((r for r in state.get("svm_dr") or [] if r.get("id") == rid or r.get("source_svm") == rid), None)
        if not rel and state.get("svm_dr"):
            rel = state["svm_dr"][0]
        if not rel:
            return {"ok": False, "error": "SVM-DR relationship not found"}
        rel["state"] = "broken-off"
        rel["last_transfer"] = _now()
        return {"ok": True, "message": f"Failover completed for {rel['source_svm']} → {rel['dest_svm']}", "svm_dr": rel}

    if action == "create_s3_bucket":
        name = (payload.get("name") or f"bucket-{_hex(4)}").strip()
        item = {
            "id": f"s3-{_hex()}", "name": name,
            "svm": payload.get("svm") or "svm-nas",
            "capacity_gb": int(payload.get("capacity_gb") or 1024),
            "objects": 0, "versioning": bool(payload.get("versioning", True)),
        }
        state.setdefault("s3_buckets", []).append(item)
        return {"ok": True, "message": f"Created S3 bucket {name}", "bucket": item}

    if action == "mav_approve":
        mid = payload.get("id") or ""
        item = next((m for m in state.get("mav_approvals") or [] if m.get("id") == mid), None)
        if not item and state.get("mav_approvals"):
            item = state["mav_approvals"][0]
        if not item:
            return {"ok": False, "error": "MAV request not found"}
        item["status"] = "Approved"
        item["approvals"] = "2/2"
        return {"ok": True, "message": f"Approved MAV for {item['operation']}", "mav": item}

    if action == "create_flexcache":
        name = (payload.get("name") or f"cache_{_hex(4)}").strip()
        item = {
            "id": f"fc-{_hex()}", "name": name,
            "origin": payload.get("origin") or "vol_data",
            "svm": payload.get("svm") or "svm-edge",
            "size_gb": int(payload.get("size_gb") or 500),
            "hit_ratio_pct": int(payload.get("hit_ratio_pct") or 0),
        }
        state.setdefault("flexcaches", []).append(item)
        return {"ok": True, "message": f"Created FlexCache {name}", "flexcache": item}

    if action == "arp_set_mode":
        mode = payload.get("mode") or "active"
        events = state.setdefault("arp_events", [])
        events.insert(0, {
            "id": f"arp-{_hex()}", "volume": payload.get("volume") or "vol_data",
            "mode": mode, "severity": "Info",
            "detail": f"ARP mode set to {mode}", "time": _now(),
        })
        return {"ok": True, "message": f"ARP mode → {mode}", "arp_events": events[:20]}

    return None
