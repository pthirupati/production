"""Dell EMC suite V2 facades — PowerStore metro/vVols, Data Domain, VxRail LCM, iDRAC."""

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
        "powerstore_metro": [
            {"id": f"metro-{_hex()}", "name": "metro-vol-app", "local": "PST-A",
             "remote": "PST-B", "rpo": "0", "state": "Synchronized", "witness": "OK"},
        ],
        "vvols": [
            {"id": f"vvol-{_hex()}", "name": "vvol-ds-prod", "vasa": "Registered",
             "vms": 24, "policy": "Gold-Replication"},
        ],
        "dd_retention_locks": [
            {"id": f"ddrl-{_hex()}", "mtree": "/data/col1/backup",
             "mode": "Compliance", "min_days": 14, "locked_files": 8900},
        ],
        "ddboost_storage_units": [
            {"id": f"ddb-{_hex()}", "name": "SU-CommVault", "user": "ddboost",
             "used_tb": 42.5, "logical_tb": 310.2, "dsp": True},
        ],
        "vxrail_clusters": [
            {"id": f"vx-{_hex()}", "name": "vxrail-prod", "nodes": 4,
             "version": "8.0.300", "health": "Healthy",
             "lcm": {"bundle": "8.0.310", "status": "Idle", "checks_passed": 15, "checks_total": 15}},
        ],
        "idrac_blades": [
            {
                "id": f"idrac-{_hex()}", "service_tag": "ABC1234", "host": "esxi-01",
                "health": "OK", "power": "On", "cpu_temp_c": 48, "inlet_c": 19,
                "fans_rpm": [6000, 5820, 6100], "psu_w": 842,
                "sel": [
                    {"sev": "INFO", "msg": "System power on", "time": _now()},
                    {"sev": "WARNING", "msg": "Fan redundancy degraded", "time": _now()},
                ],
            },
        ],
    }


def ensure_v2(state: dict) -> None:
    for k, v in seed_v2().items():
        if k not in state or state.get(k) is None:
            state[k] = v


def apply_v2_action(state: dict, action: str, payload: dict) -> dict | None:
    if action == "enable_powerstore_metro":
        name = (payload.get("name") or f"metro-{_hex(4)}").strip()
        item = {
            "id": f"metro-{_hex()}", "name": name,
            "local": payload.get("local") or "PST-A",
            "remote": payload.get("remote") or "PST-B",
            "rpo": "0", "state": "Synchronized", "witness": "OK",
        }
        state.setdefault("powerstore_metro", []).append(item)
        return {"ok": True, "message": f"Enabled Metro Volume {name}", "metro": item}

    if action == "register_vvol":
        name = (payload.get("name") or f"vvol-ds-{_hex(4)}").strip()
        item = {
            "id": f"vvol-{_hex()}", "name": name,
            "vasa": payload.get("vasa") or "Registered",
            "vms": int(payload.get("vms") or 0),
            "policy": payload.get("policy") or "Gold-Replication",
        }
        state.setdefault("vvols", []).append(item)
        return {"ok": True, "message": f"Registered vVol datastore {name}", "vvol": item}

    if action == "enable_retention_lock":
        mtree = payload.get("mtree") or f"/data/col1/{_hex(4)}"
        item = {
            "id": f"ddrl-{_hex()}", "mtree": mtree,
            "mode": payload.get("mode") or "Governance",
            "min_days": int(payload.get("min_days") or 14),
            "locked_files": 0,
        }
        state.setdefault("dd_retention_locks", []).append(item)
        return {"ok": True, "message": f"Retention Lock enabled on {mtree}", "lock": item}

    if action == "run_vxrail_lcm":
        name = payload.get("name") or ""
        cluster = next((c for c in state.get("vxrail_clusters") or [] if c.get("name") == name), None)
        if not cluster and state.get("vxrail_clusters"):
            cluster = state["vxrail_clusters"][0]
        if not cluster:
            return {"ok": False, "error": "VxRail cluster not found"}
        lcm = cluster.setdefault("lcm", {})
        lcm["status"] = "Upgrading"
        lcm["checks_passed"] = int(lcm.get("checks_total") or 15)
        lcm["progress_pct"] = 35
        lcm["started"] = _now()
        return {"ok": True, "message": f"LCM upgrade started on {cluster['name']}", "cluster": cluster}

    if action == "idrac_power_cycle":
        tag = payload.get("service_tag") or payload.get("id") or ""
        blade = next(
            (b for b in state.get("idrac_blades") or []
             if b.get("service_tag") == tag or b.get("id") == tag or b.get("host") == tag),
            None,
        )
        if not blade and state.get("idrac_blades"):
            blade = state["idrac_blades"][0]
        if not blade:
            return {"ok": False, "error": "iDRAC host not found"}
        blade["power"] = "On"
        blade.setdefault("sel", []).insert(0, {
            "sev": "INFO", "msg": "Power cycle initiated via iDRAC", "time": _now(),
        })
        return {"ok": True, "message": f"Power cycle issued for {blade.get('host')}", "idrac": blade}

    if action == "create_ddboost_unit":
        name = (payload.get("name") or f"SU-{_hex(4)}").strip()
        item = {
            "id": f"ddb-{_hex()}", "name": name,
            "user": payload.get("user") or "ddboost",
            "used_tb": 0, "logical_tb": 0, "dsp": True,
        }
        state.setdefault("ddboost_storage_units", []).append(item)
        return {"ok": True, "message": f"Created DD Boost unit {name}", "unit": item}

    return None
