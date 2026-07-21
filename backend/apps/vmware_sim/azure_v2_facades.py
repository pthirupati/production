"""Azure Portal V2 service facades (VMSS, App Service, Functions, Container Apps, etc.).

Seed + action handlers for Lab Environment expansions inside FixitLab.
Learner language: Lab Environment / Lab Server — never Simulation/Sandbox/Mock.
"""

from __future__ import annotations

import random
import time
from typing import Any

_HEX = "0123456789abcdef"


def _hex(n: int = 8) -> str:
    return "".join(random.choice(_HEX) for _ in range(n))


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def seed_v2(rg: str = "rg-fixitlab-prod") -> dict[str, Any]:
    return {
        "vmss": [
            {
                "id": f"vmss-{_hex()}", "name": "vmss-web", "resource_group": rg,
                "location": "eastus", "sku": "Standard_B2s", "capacity": 2,
                "orchestration": "Flexible", "upgrade_policy": "Automatic",
                "instances": [
                    {"name": "vmss-web_0", "power_state": "running", "private_ip": "10.10.1.20"},
                    {"name": "vmss-web_1", "power_state": "running", "private_ip": "10.10.1.21"},
                ],
                "autoscale": {"min": 1, "max": 6, "default": 2, "cpu_out": 70, "cpu_in": 30},
            },
        ],
        "app_service_plans": [
            {
                "id": f"asp-{_hex()}", "name": "asp-prod", "resource_group": rg,
                "location": "eastus", "sku": "P1v3", "os": "Linux", "apps": 1,
            },
        ],
        "web_apps": [
            {
                "id": f"app-{_hex()}", "name": "app-fixitlab-api", "resource_group": rg,
                "location": "eastus", "plan": "asp-prod", "runtime": "NODE|20-lts",
                "state": "Running", "url": "https://app-fixitlab-api.azurewebsites.net",
                "https_only": True, "always_on": True, "slots": [
                    {"name": "production", "traffic_pct": 100},
                    {"name": "staging", "traffic_pct": 0},
                ],
                "app_settings": [
                    {"name": "WEBSITE_NODE_DEFAULT_VERSION", "value": "~20"},
                    {"name": "APPINSIGHTS_INSTRUMENTATIONKEY", "value": "••••••••"},
                ],
            },
        ],
        "function_apps": [
            {
                "id": f"func-{_hex()}", "name": "func-orders", "resource_group": rg,
                "location": "eastus", "runtime": "python", "version": "3.11",
                "plan": "Consumption", "state": "Running",
                "url": "https://func-orders.azurewebsites.net",
                "functions": [
                    {"name": "HttpTrigger1", "trigger": "http", "auth_level": "function", "invocations_24h": 128},
                    {"name": "QueueProcessor", "trigger": "queue", "auth_level": "function", "invocations_24h": 45},
                ],
            },
        ],
        "container_apps_envs": [
            {
                "id": f"cae-{_hex()}", "name": "cae-prod", "resource_group": rg,
                "location": "eastus", "plan": "Consumption", "log_analytics": "law-fixitlab",
            },
        ],
        "container_apps": [
            {
                "id": f"ca-{_hex()}", "name": "ca-api", "resource_group": rg,
                "environment": "cae-prod", "image": "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest",
                "replicas": 1, "cpu": 0.5, "memory": "1Gi", "ingress": "external",
                "url": "https://ca-api.delightfuldesert-1234.eastus.azurecontainerapps.io",
                "revisions": [{"name": "ca-api--0000001", "active": True, "traffic_pct": 100}],
            },
        ],
        "vpn_gateways": [
            {
                "id": f"vpngw-{_hex()}", "name": "vpngw-hub", "resource_group": rg,
                "location": "eastus", "sku": "VpnGw1AZ", "generation": "Generation2",
                "bgp_asn": 65515, "active_active": False,
                "connections": [
                    {"name": "s2s-onprem", "type": "IPsec", "status": "Connected", "local_network": "lng-hq"},
                ],
            },
        ],
        "firewalls": [
            {
                "id": f"afw-{_hex()}", "name": "afw-hub", "resource_group": rg,
                "location": "eastus", "sku": "Standard", "threat_intel": "Alert",
                "public_ip": "20.50.1.10",
                "network_rules": [
                    {"name": "allow-dns", "source": "10.10.0.0/16", "dest": "*", "ports": "53", "action": "Allow"},
                ],
                "app_rules": [
                    {"name": "allow-microsoft", "source": "10.10.0.0/16", "fqdns": "*.microsoft.com", "action": "Allow"},
                ],
            },
        ],
        "cosmos_accounts": [
            {
                "id": f"cosmos-{_hex()}", "name": "cosmos-fixitlab", "resource_group": rg,
                "location": "eastus", "api": "NoSQL", "consistency": "Session",
                "multi_region_writes": False,
                "databases": [
                    {
                        "name": "ordersdb",
                        "containers": [
                            {"name": "orders", "partition_key": "/customerId", "throughput": 400, "items": 12},
                        ],
                    },
                ],
            },
        ],
        "sentinel": {
            "workspace": "law-fixitlab",
            "incidents": [
                {
                    "id": "INC-1001", "title": "Suspicious sign-in from unusual location",
                    "severity": "Medium", "status": "New", "tactics": ["Initial Access"],
                    "created": _now(),
                },
            ],
            "analytics_rules": [
                {"name": "Brute force detection", "kind": "Scheduled", "enabled": True, "firings_30d": 3},
                {"name": "Impossible travel", "kind": "Scheduled", "enabled": True, "firings_30d": 1},
            ],
            "connectors": [
                {"name": "Microsoft Entra ID", "status": "Connected"},
                {"name": "Azure Activity", "status": "Connected"},
            ],
        },
        "entra": {
            "tenant": "fixitlab.onmicrosoft.com",
            "tenant_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "users": [
                {"upn": "admin@fixitlab.onmicrosoft.com", "display": "Lab Admin", "type": "Member", "mfa": True},
                {"upn": "ops@fixitlab.onmicrosoft.com", "display": "Ops Engineer", "type": "Member", "mfa": True},
                {"upn": "guest@contoso.com", "display": "Contoso Guest", "type": "Guest", "mfa": False},
            ],
            "groups": [
                {"name": "Cloud Operators", "type": "Security", "members": 2},
                {"name": "Readers", "type": "Security", "members": 1},
            ],
            "app_registrations": [
                {"name": "fixitlab-api", "app_id": f"{_hex(8)}-{_hex(4)}-{_hex(4)}-{_hex(4)}-{_hex(12)}", "secrets": 1},
            ],
            "conditional_access": [
                {"name": "Require MFA for admins", "state": "enabled", "users": "All admins", "grant": "MFA"},
            ],
        },
    }


def ensure_v2(state: dict) -> None:
    """Idempotently attach V2 collections for sessions created before this module."""
    seed = seed_v2((state.get("resource_groups") or [{}])[0].get("name") or "rg-fixitlab-prod")
    for key, value in seed.items():
        if key not in state or state.get(key) is None:
            state[key] = value


def apply_v2_action(state: dict, action: str, payload: dict) -> dict | None:
    """Return action result dict, or None if action is not a V2 facade action."""
    rg = (payload.get("resource_group")
          or (state.get("resource_groups") or [{}])[0].get("name")
          or "rg-fixitlab-prod")

    if action == "create_vmss":
        name = (payload.get("name") or f"vmss-{_hex(4)}").strip()
        if any(v.get("name") == name for v in state.get("vmss") or []):
            return {"ok": False, "error": f"Scale set '{name}' already exists"}
        capacity = int(payload.get("capacity") or 2)
        sku = payload.get("sku") or "Standard_B2s"
        instances = [
            {"name": f"{name}_{i}", "power_state": "running",
             "private_ip": f"10.10.1.{30 + i}"}
            for i in range(capacity)
        ]
        item = {
            "id": f"vmss-{_hex()}", "name": name, "resource_group": rg,
            "location": payload.get("location") or "eastus", "sku": sku,
            "capacity": capacity, "orchestration": payload.get("orchestration") or "Flexible",
            "upgrade_policy": payload.get("upgrade_policy") or "Automatic",
            "instances": instances,
            "autoscale": {
                "min": int(payload.get("min") or 1),
                "max": int(payload.get("max") or max(capacity, 4)),
                "default": capacity,
                "cpu_out": 70, "cpu_in": 30,
            },
        }
        state.setdefault("vmss", []).append(item)
        return {"ok": True, "message": f"Created scale set {name}", "vmss": item}

    if action == "scale_vmss":
        name = payload.get("name") or ""
        ss = next((v for v in state.get("vmss") or [] if v.get("name") == name), None)
        if not ss:
            return {"ok": False, "error": "Scale set not found"}
        capacity = max(0, int(payload.get("capacity") or ss.get("capacity") or 1))
        ss["capacity"] = capacity
        instances = ss.setdefault("instances", [])
        while len(instances) < capacity:
            i = len(instances)
            instances.append({
                "name": f"{ss['name']}_{i}", "power_state": "running",
                "private_ip": f"10.10.1.{40 + i}",
            })
        ss["instances"] = instances[:capacity]
        return {"ok": True, "message": f"Scaled {name} to {capacity}", "vmss": ss}

    if action == "create_web_app":
        name = (payload.get("name") or f"app-{_hex(4)}").strip()
        if any(a.get("name") == name for a in state.get("web_apps") or []):
            return {"ok": False, "error": f"Web app '{name}' already exists"}
        plan = payload.get("plan") or ((state.get("app_service_plans") or [{}])[0].get("name") or "asp-prod")
        item = {
            "id": f"app-{_hex()}", "name": name, "resource_group": rg,
            "location": payload.get("location") or "eastus", "plan": plan,
            "runtime": payload.get("runtime") or "NODE|20-lts",
            "state": "Running", "url": f"https://{name}.azurewebsites.net",
            "https_only": True, "always_on": True,
            "slots": [{"name": "production", "traffic_pct": 100}],
            "app_settings": [],
        }
        state.setdefault("web_apps", []).append(item)
        for p in state.get("app_service_plans") or []:
            if p.get("name") == plan:
                p["apps"] = int(p.get("apps") or 0) + 1
        return {"ok": True, "message": f"Created web app {name}", "web_app": item}

    if action == "swap_web_slots":
        name = payload.get("name") or ""
        app = next((a for a in state.get("web_apps") or [] if a.get("name") == name), None)
        if not app:
            return {"ok": False, "error": "Web app not found"}
        slots = app.setdefault("slots", [])
        if len(slots) < 2:
            slots.append({"name": "staging", "traffic_pct": 0})
        # Swap production <-> staging traffic labels
        for s in slots:
            if s.get("name") == "production":
                s["traffic_pct"] = 0
            elif s.get("name") == "staging":
                s["traffic_pct"] = 100
        # flip names conceptually: mark swap event
        app["last_swap"] = _now()
        return {"ok": True, "message": f"Swapped slots on {name}", "web_app": app}

    if action == "create_function_app":
        name = (payload.get("name") or f"func-{_hex(4)}").strip()
        if any(f.get("name") == name for f in state.get("function_apps") or []):
            return {"ok": False, "error": f"Function app '{name}' already exists"}
        item = {
            "id": f"func-{_hex()}", "name": name, "resource_group": rg,
            "location": payload.get("location") or "eastus",
            "runtime": payload.get("runtime") or "node",
            "version": payload.get("version") or "20",
            "plan": payload.get("plan") or "Consumption",
            "state": "Running", "url": f"https://{name}.azurewebsites.net",
            "functions": [],
        }
        state.setdefault("function_apps", []).append(item)
        return {"ok": True, "message": f"Created function app {name}", "function_app": item}

    if action == "create_function":
        app_name = payload.get("app") or payload.get("name") or ""
        app = next((f for f in state.get("function_apps") or [] if f.get("name") == app_name), None)
        if not app:
            return {"ok": False, "error": "Function app not found"}
        fname = (payload.get("function_name") or "HttpTrigger").strip()
        fn = {
            "name": fname,
            "trigger": payload.get("trigger") or "http",
            "auth_level": payload.get("auth_level") or "function",
            "invocations_24h": 0,
        }
        app.setdefault("functions", []).append(fn)
        return {"ok": True, "message": f"Created function {fname}", "function_app": app}

    if action == "create_container_app":
        name = (payload.get("name") or f"ca-{_hex(4)}").strip()
        if any(c.get("name") == name for c in state.get("container_apps") or []):
            return {"ok": False, "error": f"Container app '{name}' already exists"}
        env = payload.get("environment") or ((state.get("container_apps_envs") or [{}])[0].get("name") or "cae-prod")
        item = {
            "id": f"ca-{_hex()}", "name": name, "resource_group": rg,
            "environment": env,
            "image": payload.get("image") or "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest",
            "replicas": int(payload.get("replicas") or 1),
            "cpu": float(payload.get("cpu") or 0.5),
            "memory": payload.get("memory") or "1Gi",
            "ingress": payload.get("ingress") or "external",
            "url": f"https://{name}.delightfuldesert-1234.eastus.azurecontainerapps.io",
            "revisions": [{"name": f"{name}--0000001", "active": True, "traffic_pct": 100}],
        }
        state.setdefault("container_apps", []).append(item)
        return {"ok": True, "message": f"Created container app {name}", "container_app": item}

    if action == "create_firewall_rule":
        fw_name = payload.get("firewall") or ""
        fw = next((f for f in state.get("firewalls") or [] if f.get("name") == fw_name), None)
        if not fw:
            return {"ok": False, "error": "Firewall not found"}
        kind = payload.get("kind") or "network"
        rule = {
            "name": (payload.get("rule_name") or f"rule-{_hex(4)}").strip(),
            "source": payload.get("source") or "*",
            "action": payload.get("action") or "Allow",
        }
        if kind == "app":
            rule["fqdns"] = payload.get("fqdns") or "*"
            fw.setdefault("app_rules", []).append(rule)
        else:
            rule["dest"] = payload.get("dest") or "*"
            rule["ports"] = payload.get("ports") or "*"
            fw.setdefault("network_rules", []).append(rule)
        return {"ok": True, "message": f"Added {kind} rule on {fw_name}", "firewall": fw}

    if action == "create_cosmos_item":
        account = payload.get("account") or ""
        acct = next((c for c in state.get("cosmos_accounts") or [] if c.get("name") == account), None)
        if not acct:
            return {"ok": False, "error": "Cosmos account not found"}
        db_name = payload.get("database") or "ordersdb"
        container_name = payload.get("container") or "orders"
        db = next((d for d in acct.get("databases") or [] if d.get("name") == db_name), None)
        if not db:
            return {"ok": False, "error": "Database not found"}
        ctr = next((c for c in db.get("containers") or [] if c.get("name") == container_name), None)
        if not ctr:
            return {"ok": False, "error": "Container not found"}
        ctr["items"] = int(ctr.get("items") or 0) + 1
        return {"ok": True, "message": f"Inserted item into {container_name}", "cosmos": acct}

    if action == "sentinel_update_incident":
        iid = payload.get("incident_id") or ""
        status = payload.get("status") or "Active"
        inc = next((i for i in (state.get("sentinel") or {}).get("incidents") or [] if i.get("id") == iid), None)
        if not inc:
            return {"ok": False, "error": "Incident not found"}
        inc["status"] = status
        return {"ok": True, "message": f"Incident {iid} → {status}", "incident": inc}

    if action == "entra_invite_user":
        upn = (payload.get("upn") or "").strip()
        if not upn:
            return {"ok": False, "error": "UPN required"}
        entra = state.setdefault("entra", seed_v2(rg)["entra"])
        if any(u.get("upn") == upn for u in entra.get("users") or []):
            return {"ok": False, "error": "User already exists"}
        user = {
            "upn": upn,
            "display": payload.get("display") or upn.split("@")[0],
            "type": payload.get("type") or "Guest",
            "mfa": bool(payload.get("mfa")),
        }
        entra.setdefault("users", []).append(user)
        return {"ok": True, "message": f"Invited {upn}", "user": user}

    return None
