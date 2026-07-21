"""Liquid cooling plant loop + MAAS/PXE bare-metal provisioning facades.

Keeps facility/cooling depth and bare-metal lifecycle out of datacenter_engine.py
while staying inside FixitLab Lab Environment semantics.
"""

from __future__ import annotations

import time


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── Liquid cooling (CDU / DLC / manifolds) ─────────────────────────────────

def build_liquid_cooling(servers: list[dict] | None = None) -> dict:
    """Facility liquid loop: CDUs → rack manifolds → server QDs."""
    servers = servers or []
    gpu_racks = sorted({s.get("rack") for s in servers if s.get("role") == "gpu_node" and s.get("rack")})
    if not gpu_racks:
        gpu_racks = ["R03"]
    manifolds = []
    for rack_id in gpu_racks[:4]:
        manifolds.append({
            "id": f"MAN-{rack_id}",
            "rack": rack_id,
            "position": "rack_rear",
            "servers_connected": sum(1 for s in servers if s.get("rack") == rack_id),
            "supply_temp_c": 22.0,
            "return_temp_c": 38.5,
            "flow_lpm": 18.0,
            "pressure_kpa": 220,
            "qd_couplings": [
                {"id": f"QD-{rack_id}-S", "side": "supply", "color": "blue", "connected": True, "spill_safe": True},
                {"id": f"QD-{rack_id}-R", "side": "return", "color": "red", "connected": True, "spill_safe": True},
            ],
            "status": "online",
        })
    return {
        "fluid": "water-glycol 30%",
        "loop_status": "online",
        "leak_detected": False,
        "cdus": [
            {
                "id": "CDU-1",
                "model": "CoolIT CHx40",
                "status": "running",
                "capacity_kw": 80,
                "load_kw": 42,
                "supply_setpoint_c": 20.0,
                "supply_temp_c": 20.2,
                "return_temp_c": 36.0,
                "flow_lpm": 95,
                "pump_rpm": 2800,
                "primary_loop": "facility_chilled_water",
            },
            {
                "id": "CDU-2",
                "model": "CoolIT CHx40",
                "status": "standby",
                "capacity_kw": 80,
                "load_kw": 0,
                "supply_setpoint_c": 20.0,
                "supply_temp_c": 22.0,
                "return_temp_c": 22.0,
                "flow_lpm": 0,
                "pump_rpm": 0,
                "primary_loop": "facility_chilled_water",
            },
        ],
        "manifolds": manifolds,
        "dry_cooler_link": ["CT-1", "CT-2"],
        "events": [{"time": _now(), "message": "Liquid loop nominal · CDU-1 primary"}],
    }


def liquid_cooling_op(loop: dict, op: str, **kwargs) -> tuple[bool, str, dict]:
    """Mutate liquid cooling plant. Returns (ok, message, loop)."""
    if op == "start_cdu":
        cdu_id = kwargs.get("cdu_id") or "CDU-2"
        cdu = next((c for c in loop.get("cdus") or [] if c.get("id") == cdu_id), None)
        if not cdu:
            return False, f"CDU {cdu_id} not found", loop
        cdu["status"] = "running"
        cdu["load_kw"] = 20
        cdu["flow_lpm"] = 60
        cdu["pump_rpm"] = 2400
        loop["loop_status"] = "online"
        loop.setdefault("events", []).insert(0, {"time": _now(), "message": f"{cdu_id} started"})
        return True, f"{cdu_id} running", loop

    if op == "stop_cdu":
        cdu_id = kwargs.get("cdu_id") or "CDU-1"
        cdu = next((c for c in loop.get("cdus") or [] if c.get("id") == cdu_id), None)
        if not cdu:
            return False, f"CDU {cdu_id} not found", loop
        cdu["status"] = "stopped"
        cdu["load_kw"] = 0
        cdu["flow_lpm"] = 0
        cdu["pump_rpm"] = 0
        running = any(c.get("status") == "running" for c in loop.get("cdus") or [])
        loop["loop_status"] = "online" if running else "degraded"
        loop.setdefault("events", []).insert(0, {"time": _now(), "message": f"{cdu_id} stopped"})
        return True, f"{cdu_id} stopped", loop

    if op == "set_setpoint":
        cdu_id = kwargs.get("cdu_id") or "CDU-1"
        temp = float(kwargs.get("temp_c") or 20)
        cdu = next((c for c in loop.get("cdus") or [] if c.get("id") == cdu_id), None)
        if not cdu:
            return False, f"CDU {cdu_id} not found", loop
        cdu["supply_setpoint_c"] = temp
        cdu["supply_temp_c"] = temp + 0.2
        return True, f"{cdu_id} setpoint {temp}°C", loop

    if op == "toggle_qd":
        qd_id = kwargs.get("qd_id") or ""
        for man in loop.get("manifolds") or []:
            for qd in man.get("qd_couplings") or []:
                if qd.get("id") == qd_id:
                    qd["connected"] = not qd.get("connected", True)
                    if not qd["connected"]:
                        man["flow_lpm"] = max(0, float(man.get("flow_lpm") or 0) - 6)
                        man["status"] = "partial"
                    else:
                        man["flow_lpm"] = float(man.get("flow_lpm") or 0) + 6
                        if all(q.get("connected") for q in man.get("qd_couplings") or []):
                            man["status"] = "online"
                    msg = f"{qd_id} {'connected' if qd['connected'] else 'disconnected'}"
                    loop.setdefault("events", []).insert(0, {"time": _now(), "message": msg})
                    return True, msg, loop
        return False, f"QD {qd_id} not found", loop

    if op == "inject_leak":
        loop["leak_detected"] = True
        loop["loop_status"] = "alarm"
        loop.setdefault("events", []).insert(0, {"time": _now(), "message": "Water leak detected under raised floor"})
        return True, "Leak injected", loop

    if op == "clear_leak":
        loop["leak_detected"] = False
        running = any(c.get("status") == "running" for c in loop.get("cdus") or [])
        loop["loop_status"] = "online" if running else "degraded"
        loop.setdefault("events", []).insert(0, {"time": _now(), "message": "Leak cleared · sensors dry"})
        return True, "Leak cleared", loop

    return False, f"Unknown liquid op: {op}", loop


# ── MAAS / PXE provisioning ────────────────────────────────────────────────

def build_pxe_maas(servers: list[dict] | None = None) -> dict:
    servers = servers or []
    machines = []
    for s in servers:
        machines.append({
            "id": s.get("id"),
            "hostname": s.get("hostname"),
            "system_id": f"node-{abs(hash(s.get('id') or '')) % 100000:05d}",
            "status": "deployed" if s.get("power_state") == "on" else "ready",
            "power_type": "ipmi" if (s.get("vendor") or "").upper() not in ("HPE", "HP") else "ilo",
            "architecture": "amd64/generic",
            "os": "ubuntu/22.04" if s.get("role") != "esxi_host" else "esxi/8.0",
            "pxe_mac": f"52:54:00:{abs(hash(s.get('id') or '')) % 0xFFFFFF:06x}"[0:17],
            "commissioning_results": "passed" if s.get("power_state") == "on" else None,
        })
    return {
        "region": {
            "id": "maas-region-1",
            "url": "https://maas.mgmt.corp.local:5240/MAAS",
            "version": "3.4.2",
            "dhcp": True,
            "tftp": True,
            "http_boot": True,
            "status": "healthy",
        },
        "rack_controllers": [
            {"id": "maas-rack-1", "vlan": 90, "subnet": "10.90.0.0/24", "status": "running"},
            {"id": "maas-rack-2", "vlan": 90, "subnet": "10.90.0.0/24", "status": "running"},
        ],
        "images": [
            {"name": "ubuntu/22.04", "arch": "amd64", "synced": True},
            {"name": "ubuntu/24.04", "arch": "amd64", "synced": True},
            {"name": "rhel/9.4", "arch": "amd64", "synced": True},
            {"name": "esxi/8.0", "arch": "amd64", "synced": True},
            {"name": "centos/stream9", "arch": "amd64", "synced": False},
        ],
        "pxe_menu": ["Local Disk", "MAAS Commission", "Ubuntu Live", "Rescue", "UEFI Shell"],
        "dhcp_leases": len(machines),
        "machines": machines,
        "events": [{"time": _now(), "message": "MAAS region healthy · DHCP/TFTP online"}],
    }


def pxe_maas_op(platform: dict, op: str, **kwargs) -> tuple[bool, str, dict]:
    machines = platform.setdefault("machines", [])
    mid = kwargs.get("machine_id") or kwargs.get("asset_id") or ""
    machine = next((m for m in machines if m.get("id") == mid or m.get("hostname") == mid), None)

    if op == "enlist":
        if not machine:
            return False, f"Machine {mid} not found", platform
        machine["status"] = "new"
        machine["commissioning_results"] = None
        platform.setdefault("events", []).insert(0, {"time": _now(), "message": f"Enlisted {machine['hostname']}"})
        return True, f"Enlisted {machine['hostname']}", platform

    if op == "commission":
        if not machine:
            return False, f"Machine {mid} not found", platform
        machine["status"] = "commissioning"
        machine["commissioning_results"] = "passed"
        machine["status"] = "ready"
        platform.setdefault("events", []).insert(0, {"time": _now(), "message": f"Commissioned {machine['hostname']}"})
        return True, f"Commissioned {machine['hostname']}", platform

    if op == "deploy":
        if not machine:
            return False, f"Machine {mid} not found", platform
        image = kwargs.get("image") or machine.get("os") or "ubuntu/22.04"
        machine["os"] = image
        machine["status"] = "deploying"
        machine["status"] = "deployed"
        platform.setdefault("events", []).insert(0, {"time": _now(), "message": f"Deployed {image} → {machine['hostname']}"})
        return True, f"Deployed {image}", platform

    if op == "release":
        if not machine:
            return False, f"Machine {mid} not found", platform
        machine["status"] = "ready"
        machine["os"] = None
        platform.setdefault("events", []).insert(0, {"time": _now(), "message": f"Released {machine['hostname']}"})
        return True, f"Released {machine['hostname']}", platform

    if op == "pxe_boot":
        if not machine:
            return False, f"Machine {mid} not found", platform
        machine["last_pxe"] = _now()
        machine["pxe_boot_ok"] = True
        platform.setdefault("events", []).insert(0, {"time": _now(), "message": f"PXE boot {machine['hostname']}"})
        return True, f"PXE boot {machine['hostname']}", platform

    if op == "sync_image":
        name = kwargs.get("image") or "centos/stream9"
        img = next((i for i in platform.get("images") or [] if i.get("name") == name), None)
        if not img:
            platform.setdefault("images", []).append({"name": name, "arch": "amd64", "synced": True})
        else:
            img["synced"] = True
        return True, f"Synced {name}", platform

    if op == "fix_dhcp":
        region = platform.setdefault("region", {})
        region["dhcp"] = True
        region["tftp"] = True
        region["status"] = "healthy"
        platform.setdefault("events", []).insert(0, {"time": _now(), "message": "DHCP/TFTP restored"})
        return True, "DHCP/TFTP restored", platform

    if op == "break_dhcp":
        region = platform.setdefault("region", {})
        region["dhcp"] = False
        region["status"] = "degraded"
        platform.setdefault("events", []).insert(0, {"time": _now(), "message": "DHCP disabled — PXE will fail"})
        return True, "DHCP broken", platform

    return False, f"Unknown PXE/MAAS op: {op}", platform


# ── Dense FRU label helpers ────────────────────────────────────────────────

def densify_rack_fru(fru: dict, rack_id: str) -> dict:
    """Add per-U labels, screw kits, more cage-nut samples, warranty/QR plates."""
    if fru.get("labels_dense"):
        return fru
    u_height = int(fru.get("u_height") or 42)
    fru["labels"] = [
        {
            "u": u,
            "text": f"{rack_id}-U{u:02d}",
            "qr": f"QR://fixitlab/{rack_id}/U{u}",
            "serial_plate": f"SP-{rack_id}-{u:02d}",
        }
        for u in range(1, min(u_height, 12) + 1)
    ]
    fru["screw_kit"] = {
        "m6_screws": fru.get("rails", {}).get("front", {}).get("screws", 84) * 2,
        "cage_nuts_bag": fru.get("cage_nuts_installed") or 168,
        "washers": fru.get("washers") or 168,
        "nylon_washers": 48,
        "torque_driver_nm": 1.5,
    }
    fru["warranty_stickers"] = [
        fru.get("warranty_sticker") or {"vendor": "Schneider", "expires": "2028-03-01", "visible": True},
        {"vendor": "FixitLab Asset", "expires": "2030-01-01", "visible": True, "type": "asset"},
    ]
    # Expose more cage nut positions for interactive install
    sample = fru.get("cage_nuts") or []
    if len(sample) < 16:
        existing_u = {c.get("u") for c in sample}
        for u in range(1, 17):
            if u not in existing_u:
                sample.append({
                    "u": u,
                    "front_left": u % 3 != 0,
                    "front_right": u % 3 != 0,
                    "rear_left": True,
                    "rear_right": True,
                })
        fru["cage_nuts"] = sample[:16]
    fru["airflow_baffles"] = fru.get("airflow_baffles") or [
        {"id": "BAF-TOP", "status": "installed"},
        {"id": "BAF-BOT", "status": "installed"},
    ]
    fru["labels_dense"] = True
    return fru


def densify_server_labels(server: dict) -> dict:
    """Per-chassis warranty / QR / port labels on inventory."""
    inv = server.setdefault("inventory", {})
    if inv.get("labels_dense"):
        return server
    tag = inv.get("serial") or server.get("service_tag") or server.get("id")
    inv["fru_labels"] = {
        "chassis_qr": f"QR://fixitlab/srv/{server.get('id')}",
        "warranty_sticker": (inv.get("warranty") or {}).get("type") or "ProSupport",
        "service_tag_visible": True,
        "port_labels": ["eth0", "eth1", "iDRAC", "VGA", "USB1", "USB2"],
        "psu_labels": ["PSU1-A", "PSU2-B"],
        "drive_bay_labels": [f"Bay{i}" for i in range(0, 4)],
        "asset_tag_plate": inv.get("asset_tag"),
        "serial_plate": tag,
    }
    inv["labels_dense"] = True
    return server


def rack_fru_op(fru: dict, op: str, **kwargs) -> tuple[bool, str, dict]:
    if op == "install_cage_nut":
        u = int(kwargs.get("u") or 1)
        side = kwargs.get("side") or "front_left"
        cn = next((c for c in fru.get("cage_nuts") or [] if c.get("u") == u), None)
        if not cn:
            cn = {"u": u, "front_left": False, "front_right": False, "rear_left": False, "rear_right": False}
            fru.setdefault("cage_nuts", []).append(cn)
        cn[side] = True
        fru["cage_nuts_installed"] = int(fru.get("cage_nuts_installed") or 0) + 1
        return True, f"Cage nut U{u} {side}", fru

    if op == "remove_cage_nut":
        u = int(kwargs.get("u") or 1)
        side = kwargs.get("side") or "front_left"
        cn = next((c for c in fru.get("cage_nuts") or [] if c.get("u") == u), None)
        if not cn or not cn.get(side):
            return False, f"No cage nut at U{u} {side}", fru
        cn[side] = False
        fru["cage_nuts_installed"] = max(0, int(fru.get("cage_nuts_installed") or 0) - 1)
        return True, f"Removed cage nut U{u} {side}", fru

    if op == "torque_ground":
        g = fru.setdefault("grounding_strap", {})
        g["torque_nm"] = float(kwargs.get("torque_nm") or 5.0)
        g["status"] = "ok"
        g["installed"] = True
        return True, f"Ground torque {g['torque_nm']} N·m", fru

    if op == "toggle_baffle":
        bid = kwargs.get("baffle_id") or "BAF-TOP"
        for b in fru.get("airflow_baffles") or []:
            if b.get("id") == bid:
                b["status"] = "removed" if b.get("status") == "installed" else "installed"
                return True, f"{bid} {b['status']}", fru
        return False, f"Baffle {bid} not found", fru

    if op == "scan_qr":
        code = kwargs.get("qr") or fru.get("qr_code")
        fru["last_qr_scan"] = {"code": code, "time": _now(), "match": True}
        return True, f"Scanned {code}", fru

    return False, f"Unknown FRU op: {op}", fru
