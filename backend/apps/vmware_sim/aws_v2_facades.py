"""AWS Console V2 facades — Lambda/RDS/DynamoDB/EKS/ECS/ELB/ASG for lab grading.

Shapes align with frontend awsStore.js genericResources + loadBalancers/ASG.
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


def _row(rid: str, name: str, extra: dict | None = None) -> dict:
    base = {
        "id": rid, "region": "us-east-1", "name": name,
        "created": _now(), "tags": {"Environment": "lab", "Project": "fixitlab"},
    }
    if extra:
        base.update(extra)
    return base


def seed_v2() -> dict[str, Any]:
    return {
        "genericResources": {
            "lambda": {
                "functions": [_row("fn-lab001", "my-lab-function", {
                    "runtime": "Python 3.12", "memory": 128, "timeout": 30,
                    "status": "Active", "handler": "lambda_function.lambda_handler",
                    "invocations_24h": 42,
                })],
            },
            "rds": {
                "databases": [_row("db-lab001", "my-lab-db", {
                    "engine": "PostgreSQL 15.4", "class": "db.t3.micro", "storage": 20,
                    "status": "available",
                    "endpoint": "my-lab-db.c9akciq32xze.us-east-1.rds.amazonaws.com:5432",
                })],
            },
            "dynamodb": {
                "tables": [_row("table-demo001", "Orders", {
                    "partitionKey": "pk (String)", "sortKey": "sk (String)",
                    "billingMode": "On-demand", "status": "Active", "items": 3,
                })],
            },
            "eks": {
                "clusters": [_row("cluster-lab001", "lab-eks-cluster", {
                    "version": "1.30", "nodes": 3, "status": "Active",
                })],
            },
            "ecs": {
                "clusters": [_row("ecscluster-lab001", "default", {
                    "services": 1, "tasks": 2, "status": "Active",
                })],
                "services": [_row("ecsservice-demo001", "web-service", {
                    "desired": 2, "running": 2, "status": "Active",
                })],
            },
        },
        "loadBalancers": [
            {
                "id": f"arn:aws:elasticloadbalancing:us-east-1:000000000000:loadbalancer/app/lab-alb/{_hex(8)}",
                "name": "lab-alb", "type": "application", "scheme": "internet-facing",
                "state": "active", "dnsName": "lab-alb-1234567890.us-east-1.elb.amazonaws.com",
                "vpcId": "vpc-0a1b2c3d4e5f67890", "region": "us-east-1",
                "targetGroups": ["tg-lab001"],
            },
        ],
        "targetGroups": [
            {
                "id": "tg-lab001", "name": "lab-tg", "protocol": "HTTP", "port": 80,
                "vpcId": "vpc-0a1b2c3d4e5f67890", "healthCheckPath": "/health",
                "targets": ["i-0abc123def4567890"], "region": "us-east-1",
            },
        ],
        "autoScalingGroups": [
            {
                "id": "asg-0demoweb00000001", "region": "us-east-1", "name": "web-asg",
                "min": 1, "max": 4, "desired": 2, "instanceIds": [],
                "launchTemplate": "web-lt", "vpcId": "vpc-0a1b2c3d4e5f67890",
                "status": "active", "created": "2024-02-01T09:00:00Z",
            },
        ],
    }


def ensure_v2(state: dict) -> None:
    seed = seed_v2()
    # Top-level collections
    for key in ("loadBalancers", "targetGroups", "autoScalingGroups", "cwAlarms", "cwDashboards",
                "networkAcls", "natGateways"):
        if key not in state or state.get(key) is None:
            if key in seed:
                state[key] = seed[key]
            elif key == "cwAlarms":
                state[key] = []
            elif key == "cwDashboards":
                state[key] = []
            elif key == "networkAcls":
                state[key] = [
                    {
                        "id": "acl-0a1b2c3d4e5f67893", "region": "us-east-1",
                        "vpcId": "vpc-0a1b2c3d4e5f67890", "default": True,
                        "associations": [
                            "subnet-0a1b2c3d4e5f10001",
                            "subnet-0a1b2c3d4e5f10002",
                            "subnet-0a1b2c3d4e5f10003",
                        ],
                        "inbound": [
                            {"rule": 100, "protocol": "-1", "action": "allow", "cidr": "0.0.0.0/0", "from": 0, "to": 65535},
                            {"rule": 32767, "protocol": "-1", "action": "deny", "cidr": "0.0.0.0/0", "from": 0, "to": 65535},
                        ],
                        "outbound": [
                            {"rule": 100, "protocol": "-1", "action": "allow", "cidr": "0.0.0.0/0", "from": 0, "to": 65535},
                            {"rule": 32767, "protocol": "-1", "action": "deny", "cidr": "0.0.0.0/0", "from": 0, "to": 65535},
                        ],
                    },
                ]
            elif key == "natGateways":
                state[key] = []
    # Merge genericResources per service
    gr = state.setdefault("genericResources", {})
    for svc, resources in (seed.get("genericResources") or {}).items():
        bucket = gr.setdefault(svc, {})
        for res_name, rows in resources.items():
            if res_name not in bucket or bucket.get(res_name) is None:
                bucket[res_name] = rows


def apply_v2_action(state: dict, action: str, payload: dict) -> dict | None:
    gr = state.setdefault("genericResources", {})

    if action in ("create_lambda", "create_generic_resource") and (
        action == "create_lambda" or payload.get("service") == "lambda"
    ):
        name = (payload.get("name") or f"fn-{_hex(4)}").strip()
        fn = _row(f"fn-{_hex()}", name, {
            "runtime": payload.get("runtime") or "Python 3.12",
            "memory": int(payload.get("memory") or 128),
            "timeout": int(payload.get("timeout") or 30),
            "status": "Active",
            "handler": payload.get("handler") or "lambda_function.lambda_handler",
            "invocations_24h": 0,
        })
        gr.setdefault("lambda", {}).setdefault("functions", []).append(fn)
        return {"ok": True, "message": f"Created function {name}", "function": fn}

    if action == "invoke_lambda":
        name = payload.get("name") or payload.get("id") or ""
        funcs = (gr.get("lambda") or {}).get("functions") or []
        fn = next((f for f in funcs if f.get("name") == name or f.get("id") == name), None)
        if not fn and funcs:
            fn = funcs[0]
        if not fn:
            return {"ok": False, "error": "Function not found"}
        fn["invocations_24h"] = int(fn.get("invocations_24h") or 0) + 1
        fn["last_invoke"] = _now()
        return {"ok": True, "message": f"Invoked {fn['name']}", "result": {"statusCode": 200, "body": "ok"}}

    if action == "update_lambda_code":
        name = payload.get("name") or payload.get("id") or ""
        funcs = (gr.get("lambda") or {}).get("functions") or []
        fn = next((f for f in funcs if f.get("name") == name or f.get("id") == name), None)
        if not fn and funcs:
            fn = funcs[0]
        if not fn:
            return {"ok": False, "error": "Function not found"}
        if "code" in payload:
            fn["code"] = payload["code"]
        fn["last_modified"] = _now()
        fn["code_size"] = len(str(payload.get("code") or fn.get("code") or ""))
        return {"ok": True, "message": f"Updated code for {fn['name']}", "function": fn}

    if action == "update_lambda_env":
        name = payload.get("name") or payload.get("id") or ""
        funcs = (gr.get("lambda") or {}).get("functions") or []
        fn = next((f for f in funcs if f.get("name") == name or f.get("id") == name), None)
        if not fn and funcs:
            fn = funcs[0]
        if not fn:
            return {"ok": False, "error": "Function not found"}
        fn["env"] = payload.get("env") if isinstance(payload.get("env"), dict) else (fn.get("env") or {})
        fn["last_modified"] = _now()
        return {"ok": True, "message": f"Updated env for {fn['name']}", "function": fn}

    if action == "create_rds":
        name = (payload.get("name") or f"db-{_hex(4)}").strip()
        db = _row(f"db-{_hex()}", name, {
            "engine": payload.get("engine") or "PostgreSQL 15.4",
            "class": payload.get("class") or "db.t3.micro",
            "storage": int(payload.get("storage") or 20),
            "status": "available",
            "endpoint": f"{name}.c9akciq32xze.us-east-1.rds.amazonaws.com:5432",
        })
        gr.setdefault("rds", {}).setdefault("databases", []).append(db)
        return {"ok": True, "message": f"Created DB instance {name}", "database": db}

    if action == "reboot_rds":
        name = payload.get("name") or payload.get("id") or ""
        dbs = (gr.get("rds") or {}).get("databases") or []
        db = next((d for d in dbs if d.get("name") == name or d.get("id") == name), None)
        if not db:
            return {"ok": False, "error": "DB instance not found"}
        db["status"] = "available"
        db["last_reboot"] = _now()
        return {"ok": True, "message": f"Rebooted {db['name']}", "database": db}

    if action == "modify_rds":
        name = payload.get("name") or payload.get("id") or ""
        dbs = gr.setdefault("rds", {}).setdefault("databases", [])
        db = next((d for d in dbs if d.get("name") == name or d.get("id") == name), None)
        if not db and dbs:
            db = dbs[0]
        if not db:
            return {"ok": False, "error": "DB instance not found"}
        patch = payload.get("patch") if isinstance(payload.get("patch"), dict) else {
            k: v for k, v in payload.items() if k not in ("name", "id", "patch")
        }
        for key, val in (patch or {}).items():
            if key in ("id", "name"):
                continue
            db[key] = val
        db["status"] = db.get("status") or "available"
        db["last_modified"] = _now()
        return {"ok": True, "message": f"Modified {db.get('name')}", "database": db}

    if action == "create_dynamodb_table":
        name = (payload.get("name") or f"table-{_hex(4)}").strip()
        table = _row(f"table-{_hex()}", name, {
            "partitionKey": payload.get("partitionKey") or "pk (String)",
            "sortKey": payload.get("sortKey") or "",
            "billingMode": payload.get("billingMode") or "On-demand",
            "status": "Active", "items": 0, "records": [],
        })
        gr.setdefault("dynamodb", {}).setdefault("tables", []).append(table)
        return {"ok": True, "message": f"Created table {name}", "table": table}

    if action == "put_dynamodb_item":
        tables = gr.setdefault("dynamodb", {}).setdefault("tables", [])
        table = next((t for t in tables if t.get("id") == payload.get("id") or t.get("name") == payload.get("name")), None)
        if not table and tables:
            table = tables[0]
        if not table:
            table = _row(payload.get("id") or f"table-{_hex()}", payload.get("name") or "Orders", {
                "partitionKey": "pk (String)", "status": "Active", "records": [], "items": 0,
            })
            tables.append(table)
        item = payload.get("item") or {}
        records = table.setdefault("records", [])
        pk = (table.get("partitionKey") or "pk").split()[0]
        sk = (table.get("sortKey") or "").split()[0] if table.get("sortKey") else ""
        idx = next((i for i, r in enumerate(records)
                    if r.get(pk) == item.get(pk) and (not sk or r.get(sk) == item.get(sk))), None)
        if idx is not None:
            records[idx] = {**records[idx], **item}
        else:
            records.append(item)
        table["items"] = len(records)
        return {"ok": True, "message": f"Put item in {table.get('name')}", "table": table}

    if action == "delete_dynamodb_item":
        tables = gr.setdefault("dynamodb", {}).setdefault("tables", [])
        table = next((t for t in tables if t.get("id") == payload.get("id") or t.get("name") == payload.get("name")), None)
        if not table and tables:
            table = tables[0]
        if not table:
            return {"ok": False, "error": "Table not found"}
        key = payload.get("key") or {}
        pk = (table.get("partitionKey") or "pk").split()[0]
        sk = (table.get("sortKey") or "").split()[0] if table.get("sortKey") else ""
        records = table.get("records") or []
        table["records"] = [r for r in records
                            if not (r.get(pk) == key.get(pk) and (not sk or r.get(sk) == key.get(sk)))]
        table["items"] = len(table["records"])
        return {"ok": True, "message": f"Deleted item from {table.get('name')}", "table": table}

    if action in ("query_dynamodb", "scan_dynamodb", "get_dynamodb_item"):
        tables = gr.setdefault("dynamodb", {}).setdefault("tables", [])
        table = next((t for t in tables if t.get("id") == payload.get("id") or t.get("name") == payload.get("name")), None)
        if not table and tables:
            table = tables[0]
        if not table:
            return {"ok": False, "error": "Table not found"}
        records = list(table.get("records") or [])
        pk = (table.get("partitionKey") or "pk").split()[0]
        sk = (table.get("sortKey") or "").split()[0] if table.get("sortKey") else ""
        key = payload.get("key") or {}
        if action == "scan_dynamodb":
            items = records
        elif action == "get_dynamodb_item":
            items = [r for r in records
                     if r.get(pk) == key.get(pk) and (not sk or r.get(sk) == key.get(sk))]
            items = items[:1]
        else:
            items = [r for r in records if r.get(pk) == key.get(pk)]
        ops = table.setdefault("ops", [])
        ops.append({"op": action, "at": _now(), "count": len(items)})
        table["last_query"] = {"op": action, "count": len(items), "at": _now()}
        return {
            "ok": True,
            "message": f"{action} on {table.get('name')} returned {len(items)} item(s)",
            "items": items,
            "count": len(items),
            "table": table.get("name"),
        }

    if action == "assume_role":
        role = (payload.get("role") or payload.get("role_name") or payload.get("name") or "").strip()
        if not role:
            return {"ok": False, "error": "Role name required"}
        session = payload.get("session_name") or "fixitlab-session"
        state.setdefault("sts", {})["assumed_role"] = {
            "role": role,
            "session_name": session,
            "arn": payload.get("arn") or f"arn:aws:sts::123456789012:assumed-role/{role}/{session}",
            "assumed_at": _now(),
        }
        return {"ok": True, "message": f"Assumed role {role}", "sts": state["sts"]["assumed_role"]}

    if action == "transition_generic_resource":
        service = payload.get("service") or ""
        resource = payload.get("resource") or ""
        rid = payload.get("id") or payload.get("name") or ""
        op = payload.get("action") or payload.get("op") or "update"
        patch = payload.get("patch") if isinstance(payload.get("patch"), dict) else {}
        bucket = gr.setdefault(service, {}).setdefault(resource, [])
        row = next((r for r in bucket if r.get("id") == rid or r.get("name") == rid), None)
        if not row and bucket:
            row = bucket[0]
        if not row:
            row = _row(rid or f"{service}-{_hex()}", rid or f"{service}-resource", {"status": "available"})
            bucket.append(row)
        for key, val in patch.items():
            if key not in ("id",):
                row[key] = val
        row["last_action"] = op
        row["last_action_at"] = _now()
        return {"ok": True, "message": f"{op} on {service}/{resource}", "resource": row}

    if action == "create_eks_cluster":
        name = (payload.get("name") or f"eks-{_hex(4)}").strip()
        cluster = _row(f"cluster-{_hex()}", name, {
            "version": payload.get("version") or "1.30",
            "nodes": int(payload.get("nodes") or 3),
            "status": "Active",
        })
        gr.setdefault("eks", {}).setdefault("clusters", []).append(cluster)
        return {"ok": True, "message": f"Created EKS cluster {name}", "cluster": cluster}

    if action == "scale_eks":
        clusters = gr.setdefault("eks", {}).setdefault("clusters", [])
        node_groups = gr.setdefault("eks", {}).setdefault("node-groups", [])
        target = next((c for c in clusters if c.get("id") == payload.get("id") or c.get("name") == payload.get("name")), None)
        if not target:
            target = next((n for n in node_groups if n.get("id") == payload.get("id") or n.get("name") == payload.get("name")), None)
        if not target and clusters:
            target = clusters[0]
        if not target:
            name = payload.get("name") or "lab-eks-cluster"
            target = _row(payload.get("id") or f"cluster-{_hex()}", name, {
                "version": "1.30", "nodes": int(payload.get("nodes") or payload.get("desired") or 3), "status": "Active",
            })
            clusters.append(target)
        if "nodes" in payload:
            target["nodes"] = max(0, int(payload["nodes"]))
        if "desired" in payload:
            target["desired"] = max(0, int(payload["desired"]))
            if "nodes" not in target or payload.get("nodes") is None:
                target["nodes"] = target["desired"]
        return {"ok": True, "message": f"Scaled {target.get('name')}", "resource": target}

    if action == "create_ecs_service":
        name = (payload.get("name") or f"svc-{_hex(4)}").strip()
        desired = int(payload.get("desired") or 1)
        svc = _row(f"ecsservice-{_hex()}", name, {
            "desired": desired,
            "running": desired,
            "status": "Active",
        })
        gr.setdefault("ecs", {}).setdefault("services", []).append(svc)
        return {"ok": True, "message": f"Created ECS service {name}", "service": svc}

    if action == "scale_ecs":
        services = gr.setdefault("ecs", {}).setdefault("services", [])
        svc = next((s for s in services if s.get("id") == payload.get("id") or s.get("name") == payload.get("name")), None)
        if not svc and services:
            svc = services[0]
        if not svc:
            name = payload.get("name") or "web-service"
            desired = max(0, int(payload.get("desired") if payload.get("desired") is not None else 1))
            svc = _row(payload.get("id") or f"ecsservice-{_hex()}", name, {
                "desired": desired, "running": desired, "status": "Active",
            })
            services.append(svc)
            return {"ok": True, "message": f"Scaled {svc.get('name')} desired={desired}", "service": svc}
        desired = max(0, int(payload.get("desired") if payload.get("desired") is not None else svc.get("desired") or 1))
        svc["desired"] = desired
        svc["running"] = desired
        return {"ok": True, "message": f"Scaled {svc.get('name')} desired={desired}", "service": svc}

    if action == "create_cfn_stack":
        name = (payload.get("name") or f"stack-{_hex(4)}").strip()
        stacks = gr.setdefault("cloudformation", {}).setdefault("stacks", [])
        if any(s.get("name") == name for s in stacks):
            return {"ok": False, "error": f"Stack '{name}' already exists"}
        stack = _row(payload.get("id") or f"stack-{_hex()}", name, {
            "status": payload.get("status") or "CREATE_COMPLETE",
            "resources": int(payload.get("resources") or 0),
            "template": payload.get("template") or "",
        })
        stacks.append(stack)
        return {"ok": True, "message": f"Created stack {name}", "stack": stack}

    if action == "create_load_balancer":
        name = (payload.get("name") or f"alb-{_hex(4)}").strip()
        lb = {
            "id": f"arn:aws:elasticloadbalancing:us-east-1:000000000000:loadbalancer/app/{name}/{_hex(8)}",
            "name": name, "type": payload.get("type") or "application",
            "scheme": payload.get("scheme") or "internet-facing",
            "state": "active",
            "dnsName": f"{name}-{random.randint(100000, 999999)}.us-east-1.elb.amazonaws.com",
            "vpcId": payload.get("vpcId") or "vpc-0a1b2c3d4e5f67890",
            "region": "us-east-1", "targetGroups": [],
        }
        state.setdefault("loadBalancers", []).append(lb)
        return {"ok": True, "message": f"Created load balancer {name}", "loadBalancer": lb}

    if action == "scale_asg":
        name = payload.get("name") or payload.get("id") or ""
        asgs = state.setdefault("autoScalingGroups", [])
        asg = next((a for a in asgs if a.get("name") == name or a.get("id") == name), None)
        if not asg and asgs:
            asg = asgs[0]
        if not asg:
            return {"ok": False, "error": "Auto Scaling group not found"}
        if "desired" in payload:
            asg["desired"] = max(int(asg.get("min") or 0), int(payload["desired"]))
        if "min" in payload:
            asg["min"] = int(payload["min"])
        if "max" in payload:
            asg["max"] = int(payload["max"])
        return {"ok": True, "message": f"Scaled {asg['name']} desired={asg['desired']}", "asg": asg}

    if action == "create_asg":
        name = (payload.get("name") or f"asg-{_hex(4)}").strip()
        asg = {
            "id": f"asg-0{_hex(16)}", "region": "us-east-1", "name": name,
            "min": int(payload.get("min") or 1),
            "max": int(payload.get("max") or 4),
            "desired": int(payload.get("desired") or 2),
            "instanceIds": [], "launchTemplate": payload.get("launchTemplate") or "default-lt",
            "vpcId": payload.get("vpcId") or "vpc-0a1b2c3d4e5f67890",
            "status": "active", "created": _now(),
        }
        state.setdefault("autoScalingGroups", []).append(asg)
        return {"ok": True, "message": f"Created ASG {name}", "asg": asg}

    if action == "delete_asg":
        ident = payload.get("id") or payload.get("name") or ""
        before = len(state.get("autoScalingGroups") or [])
        state["autoScalingGroups"] = [
            a for a in (state.get("autoScalingGroups") or [])
            if a.get("id") != ident and a.get("name") != ident
        ]
        if len(state.get("autoScalingGroups") or []) == before:
            return {"ok": False, "error": "Auto Scaling group not found"}
        return {"ok": True, "message": f"Deleted ASG {ident}"}

    if action == "delete_load_balancer":
        ident = payload.get("id") or payload.get("name") or ""
        before = len(state.get("loadBalancers") or [])
        state["loadBalancers"] = [
            lb for lb in (state.get("loadBalancers") or [])
            if lb.get("id") != ident and lb.get("name") != ident
        ]
        if len(state.get("loadBalancers") or []) == before:
            return {"ok": False, "error": "Load balancer not found"}
        return {"ok": True, "message": f"Deleted load balancer {ident}"}

    if action == "create_target_group":
        name = (payload.get("name") or f"tg-{_hex(4)}").strip()
        tg = {
            "id": payload.get("id") or f"tg-0{_hex(16)}",
            "region": "us-east-1",
            "name": name,
            "protocol": payload.get("protocol") or "HTTP",
            "port": int(payload.get("port") or 80),
            "vpcId": payload.get("vpcId") or "vpc-0a1b2c3d4e5f67890",
            "targetType": payload.get("targetType") or "instance",
            "targets": [],
            "created": _now(),
        }
        state.setdefault("targetGroups", []).append(tg)
        return {"ok": True, "message": f"Created target group {name}", "targetGroup": tg}

    if action == "delete_target_group":
        ident = payload.get("id") or payload.get("name") or ""
        before = len(state.get("targetGroups") or [])
        state["targetGroups"] = [
            tg for tg in (state.get("targetGroups") or [])
            if tg.get("id") != ident and tg.get("name") != ident
        ]
        if len(state.get("targetGroups") or []) == before:
            return {"ok": False, "error": "Target group not found"}
        return {"ok": True, "message": f"Deleted target group {ident}"}

    if action == "register_target":
        tg_id = payload.get("target_group_id") or payload.get("id") or ""
        tg = next((t for t in state.get("targetGroups") or [] if t.get("id") == tg_id or t.get("name") == tg_id), None)
        if not tg and state.get("targetGroups"):
            tg = state["targetGroups"][0]
        if not tg:
            return {"ok": False, "error": "Target group not found"}
        inst_id = payload.get("instance_id") or ""
        port = int(payload.get("port") or tg.get("port") or 80)
        targets = [t for t in (tg.get("targets") or []) if t.get("id") != inst_id]
        targets.append({"id": inst_id, "port": port, "health": "initial"})
        tg["targets"] = targets
        return {"ok": True, "message": f"Registered {inst_id} on {tg['name']}", "targetGroup": tg}

    if action == "deregister_target":
        tg_id = payload.get("target_group_id") or payload.get("id") or ""
        tg = next((t for t in state.get("targetGroups") or [] if t.get("id") == tg_id or t.get("name") == tg_id), None)
        if not tg:
            return {"ok": False, "error": "Target group not found"}
        inst_id = payload.get("instance_id") or ""
        tg["targets"] = [t for t in (tg.get("targets") or []) if t.get("id") != inst_id]
        return {"ok": True, "message": f"Deregistered {inst_id} from {tg['name']}", "targetGroup": tg}

    # Generic create from frontend sync
    if action == "create_generic_resource":
        service = payload.get("service") or ""
        resource = payload.get("resource") or ""
        name = (payload.get("name") or f"{service}-{_hex(4)}").strip()
        if not service or not resource:
            return {"ok": False, "error": "service and resource required"}
        row = _row(f"{service[:3]}-{_hex()}", name, {"status": payload.get("status") or "Active", **{
            k: v for k, v in payload.items() if k not in ("service", "resource", "name", "status")
        }})
        gr.setdefault(service, {}).setdefault(resource, []).append(row)
        return {"ok": True, "message": f"Created {service}/{resource} {name}", "resource": row}

    if action == "delete_generic_resource":
        service = payload.get("service") or ""
        resource = payload.get("resource") or ""
        ident = payload.get("id") or payload.get("name") or ""
        rows = gr.setdefault(service, {}).setdefault(resource, [])
        before = len(rows)
        gr[service][resource] = [r for r in rows if r.get("id") != ident and r.get("name") != ident]
        if len(gr[service][resource]) == before:
            return {"ok": False, "error": f"{service}/{resource} '{ident}' not found"}
        return {"ok": True, "message": f"Deleted {service}/{resource} {ident}"}

    if action == "update_generic_resource":
        service = payload.get("service") or ""
        resource = payload.get("resource") or ""
        ident = payload.get("id") or payload.get("name") or ""
        rows = gr.setdefault(service, {}).setdefault(resource, [])
        row = next((r for r in rows if r.get("id") == ident or r.get("name") == ident), None)
        if not row:
            return {"ok": False, "error": f"{service}/{resource} '{ident}' not found"}
        patch = payload.get("patch") or {}
        for k, v in patch.items():
            if k not in ("id",):
                row[k] = v
        return {"ok": True, "message": f"Updated {service}/{resource} {ident}", "resource": row}

    if action == "publish_sns":
        topic = payload.get("name") or payload.get("topic") or "lab-topic"
        topics = gr.setdefault("sns", {}).setdefault("topics", [])
        row = next((t for t in topics if t.get("name") == topic or t.get("id") == payload.get("id")), None)
        if not row and topics:
            row = topics[0]
        if not row:
            row = _row(payload.get("id") or f"topic-{_hex()}", topic, {"type": "Standard", "subscriptions": 0, "status": "Active", "published": 0})
            topics.append(row)
        row["published"] = int(row.get("published") or 0) + 1
        row["lastPublish"] = _now()
        return {"ok": True, "message": f"Published to {row.get('name')}", "topic": row}

    if action == "create_sns_topic":
        name = (payload.get("name") or f"topic-{_hex(4)}").strip()
        topics = gr.setdefault("sns", {}).setdefault("topics", [])
        if any(t.get("name") == name for t in topics):
            return {"ok": False, "error": f"Topic '{name}' already exists"}
        row = _row(payload.get("id") or f"topic-{_hex()}", name, {
            "type": payload.get("type") or "Standard",
            "subscriptions": int(payload.get("subscriptions") or 0),
            "status": payload.get("status") or "Active",
            "published": 0,
        })
        topics.append(row)
        return {"ok": True, "message": f"Created SNS topic {name}", "topic": row}

    if action == "create_sqs_queue":
        name = (payload.get("name") or f"queue-{_hex(4)}").strip()
        queues = gr.setdefault("sqs", {}).setdefault("queues", [])
        if any(q.get("name") == name for q in queues):
            return {"ok": False, "error": f"Queue '{name}' already exists"}
        row = _row(payload.get("id") or f"queue-{_hex()}", name, {
            "type": payload.get("type") or "Standard",
            "messages": int(payload.get("messages") or 0),
            "status": payload.get("status") or "Active",
        })
        queues.append(row)
        return {"ok": True, "message": f"Created SQS queue {name}", "queue": row}

    if action == "create_secret":
        name = (payload.get("name") or f"secret-{_hex(4)}").strip()
        secrets = gr.setdefault("secretsmanager", {}).setdefault("secrets", [])
        if any(s.get("name") == name for s in secrets):
            return {"ok": False, "error": f"Secret '{name}' already exists"}
        row = _row(payload.get("id") or f"secret-{_hex()}", name, {
            "description": payload.get("description") or "",
            "status": payload.get("status") or "Active",
            "rotation": bool(payload.get("rotation")),
        })
        secrets.append(row)
        return {"ok": True, "message": f"Created secret {name}", "secret": row}

    if action == "request_certificate":
        name = (payload.get("name") or payload.get("domain") or f"*.lab-{_hex(4)}.example.com").strip()
        certs = gr.setdefault("acm", {}).setdefault("certificates", [])
        if any(c.get("name") == name for c in certs):
            return {"ok": False, "error": f"Certificate '{name}' already exists"}
        row = _row(payload.get("id") or f"cert-{_hex()}", name, {
            "type": payload.get("type") or "Amazon issued",
            "status": payload.get("status") or "Issued",
            "expires": payload.get("expires") or "2027-12-31",
        })
        certs.append(row)
        return {"ok": True, "message": f"Requested certificate {name}", "certificate": row}

    if action == "create_cloudfront_distribution":
        name = (payload.get("name") or f"dist-{_hex(4)}").strip()
        dists = gr.setdefault("cloudfront", {}).setdefault("distributions", [])
        if any(d.get("name") == name for d in dists):
            return {"ok": False, "error": f"Distribution '{name}' already exists"}
        dist_id = payload.get("id") or f"E{_hex(13).upper()}"
        row = _row(dist_id, name, {
            "domainName": payload.get("domainName") or f"d{_hex(14)}.cloudfront.net",
            "status": payload.get("status") or "Deployed",
            "priceClass": payload.get("priceClass") or "Use all edge locations",
        })
        dists.append(row)
        return {"ok": True, "message": f"Created CloudFront distribution {name}", "distribution": row}

    if action == "create_hosted_zone":
        name = (payload.get("name") or f"lab-{_hex(4)}.internal").strip()
        zones = gr.setdefault("route53", {}).setdefault("hosted-zones", [])
        if any(z.get("name") == name for z in zones):
            return {"ok": False, "error": f"Hosted zone '{name}' already exists"}
        row = _row(payload.get("id") or f"Z{_hex(13).upper()}", name, {
            "type": payload.get("type") or "Public",
            "records": int(payload.get("records") or 2),
            "status": payload.get("status") or "available",
            "recordSets": payload.get("recordSets") if isinstance(payload.get("recordSets"), list) else [],
        })
        zones.append(row)
        return {"ok": True, "message": f"Created hosted zone {name}", "zone": row}

    if action == "create_health_check":
        name = (payload.get("name") or f"hc-{_hex(4)}").strip()
        checks = gr.setdefault("route53", {}).setdefault("health-checks", [])
        if any(c.get("name") == name for c in checks):
            return {"ok": False, "error": f"Health check '{name}' already exists"}
        row = _row(payload.get("id") or f"hc-{_hex()}", name, {
            "protocol": payload.get("protocol") or "HTTPS",
            "status": payload.get("status") or "Healthy",
        })
        checks.append(row)
        return {"ok": True, "message": f"Created health check {name}", "health_check": row}

    if action == "create_ecr_repository":
        name = (payload.get("name") or f"repo-{_hex(4)}").strip()
        repos = gr.setdefault("ecr", {}).setdefault("repositories", [])
        if any(r.get("name") == name for r in repos):
            return {"ok": False, "error": f"Repository '{name}' already exists"}
        row = _row(payload.get("id") or f"repo-{_hex()}", name, {
            "visibility": payload.get("visibility") or "Private",
            "tagMutability": payload.get("tagMutability") or "Mutable",
            "scanOnPush": payload.get("scanOnPush") or "Enabled",
            "images": int(payload.get("images") or 0),
            "status": payload.get("status") or "Active",
        })
        repos.append(row)
        return {"ok": True, "message": f"Created ECR repository {name}", "repository": row}

    if action == "create_parameter":
        name = (payload.get("name") or f"/lab/param-{_hex(4)}").strip()
        params = gr.setdefault("systemsmanager", {}).setdefault("parameters", [])
        if any(p.get("name") == name for p in params):
            return {"ok": False, "error": f"Parameter '{name}' already exists"}
        row = _row(payload.get("id") or f"param-{_hex()}", name, {
            "type": payload.get("type") or "String",
            "tier": payload.get("tier") or "Standard",
            "status": payload.get("status") or "Active",
        })
        params.append(row)
        return {"ok": True, "message": f"Created parameter {name}", "parameter": row}

    if action == "create_key":
        name = (payload.get("name") or f"alias/lab-key-{_hex(4)}").strip()
        keys = gr.setdefault("kms", {}).setdefault("keys", [])
        if any(k.get("name") == name for k in keys):
            return {"ok": False, "error": f"Key '{name}' already exists"}
        row = _row(payload.get("id") or f"key-{_hex()}", name, {
            "usage": payload.get("usage") or "Encrypt and decrypt",
            "rotation": payload.get("rotation") or "Enabled",
            "status": payload.get("status") or "Enabled",
        })
        keys.append(row)
        return {"ok": True, "message": f"Created KMS key {name}", "key": row}

    if action == "create_sns_subscription":
        name = (payload.get("name") or payload.get("endpoint") or f"sub-{_hex(4)}@example.com").strip()
        subs = gr.setdefault("sns", {}).setdefault("subscriptions", [])
        if any(s.get("name") == name for s in subs):
            return {"ok": False, "error": f"Subscription '{name}' already exists"}
        row = _row(payload.get("id") or f"sub-{_hex()}", name, {
            "protocol": payload.get("protocol") or "Email",
            "status": payload.get("status") or "Confirmed",
        })
        subs.append(row)
        return {"ok": True, "message": f"Created SNS subscription {name}", "subscription": row}

    if action == "create_api":
        name = (payload.get("name") or f"api-{_hex(4)}").strip()
        apis = gr.setdefault("apigateway", {}).setdefault("apis", [])
        if any(a.get("name") == name for a in apis):
            return {"ok": False, "error": f"API '{name}' already exists"}
        row = _row(payload.get("id") or _hex(10), name, {
            "type": payload.get("type") or "HTTP",
            "stage": payload.get("stage") or "prod",
            "status": payload.get("status") or "Active",
        })
        apis.append(row)
        return {"ok": True, "message": f"Created API {name}", "api": row}

    if action == "create_event_rule":
        name = (payload.get("name") or f"rule-{_hex(4)}").strip()
        rules = gr.setdefault("eventbridge", {}).setdefault("rules", [])
        if any(r.get("name") == name for r in rules):
            return {"ok": False, "error": f"Rule '{name}' already exists"}
        row = _row(payload.get("id") or f"rule-{_hex()}", name, {
            "eventBus": payload.get("eventBus") or "default",
            "targets": int(payload.get("targets") or 1),
            "status": payload.get("status") or "Enabled",
        })
        rules.append(row)
        return {"ok": True, "message": f"Created EventBridge rule {name}", "rule": row}

    if action == "create_state_machine":
        name = (payload.get("name") or f"sm-{_hex(4)}").strip()
        machines = gr.setdefault("states", {}).setdefault("state-machines", [])
        if any(m.get("name") == name for m in machines):
            return {"ok": False, "error": f"State machine '{name}' already exists"}
        row = _row(payload.get("id") or f"sm-{_hex()}", name, {
            "type": payload.get("type") or "STANDARD",
            "executions": int(payload.get("executions") or 0),
            "status": payload.get("status") or "Active",
        })
        machines.append(row)
        return {"ok": True, "message": f"Created state machine {name}", "state_machine": row}

    if action == "create_trail":
        name = (payload.get("name") or f"trail-{_hex(4)}").strip()
        trails = gr.setdefault("cloudtrail", {}).setdefault("trails", [])
        if any(t.get("name") == name for t in trails):
            return {"ok": False, "error": f"Trail '{name}' already exists"}
        row = _row(payload.get("id") or f"trail-{_hex()}", name, {
            "multiRegion": payload.get("multiRegion") or "Yes",
            "logging": payload.get("logging") or "On",
            "status": payload.get("status") or "Active",
        })
        trails.append(row)
        return {"ok": True, "message": f"Created CloudTrail {name}", "trail": row}

    if action == "create_config_rule":
        name = (payload.get("name") or f"config-rule-{_hex(4)}").strip()
        rules = gr.setdefault("config", {}).setdefault("rules", [])
        if any(r.get("name") == name for r in rules):
            return {"ok": False, "error": f"Config rule '{name}' already exists"}
        row = _row(payload.get("id") or f"config-rule-{_hex()}", name, {
            "compliance": payload.get("compliance") or "COMPLIANT",
            "evaluations": int(payload.get("evaluations") or 0),
            "status": payload.get("status") or "Active",
        })
        rules.append(row)
        return {"ok": True, "message": f"Created Config rule {name}", "rule": row}

    if action == "create_web_acl":
        name = (payload.get("name") or f"web-acl-{_hex(4)}").strip()
        acls = gr.setdefault("waf", {}).setdefault("web-acls", [])
        if any(a.get("name") == name for a in acls):
            return {"ok": False, "error": f"Web ACL '{name}' already exists"}
        row = _row(payload.get("id") or f"waf-{_hex()}", name, {
            "scope": payload.get("scope") or "Regional",
            "rules": int(payload.get("rules") or 1),
            "status": payload.get("status") or "Active",
        })
        acls.append(row)
        return {"ok": True, "message": f"Created Web ACL {name}", "web_acl": row}

    if action == "create_user_pool":
        name = (payload.get("name") or f"pool-{_hex(4)}").strip()
        pools = gr.setdefault("cognito", {}).setdefault("user-pools", [])
        if any(p.get("name") == name for p in pools):
            return {"ok": False, "error": f"User pool '{name}' already exists"}
        row = _row(payload.get("id") or f"us-east-1_{_hex(8)}", name, {
            "users": int(payload.get("users") or 0),
            "mfa": payload.get("mfa") or "Optional",
            "status": payload.get("status") or "Enabled",
        })
        pools.append(row)
        return {"ok": True, "message": f"Created Cognito user pool {name}", "user_pool": row}

    if action == "create_change_set":
        name = (payload.get("name") or f"changeset-{_hex(4)}").strip()
        sets = gr.setdefault("cloudformation", {}).setdefault("change-sets", [])
        if any(c.get("name") == name for c in sets):
            return {"ok": False, "error": f"Change set '{name}' already exists"}
        row = _row(payload.get("id") or f"changeset-{_hex()}", name, {
            "status": payload.get("status") or "CREATE_COMPLETE",
            "changes": int(payload.get("changes") or 1),
        })
        sets.append(row)
        return {"ok": True, "message": f"Created change set {name}", "change_set": row}

    if action == "create_codecommit_repo":
        name = (payload.get("name") or f"repo-{_hex(4)}").strip()
        repos = gr.setdefault("codecommit", {}).setdefault("repositories", [])
        if any(r.get("name") == name for r in repos):
            return {"ok": False, "error": f"Repository '{name}' already exists"}
        row = _row(payload.get("id") or f"cc-{_hex()}", name, {
            "defaultBranch": payload.get("defaultBranch") or "main",
            "commits": int(payload.get("commits") or 0),
            "status": payload.get("status") or "Active",
        })
        repos.append(row)
        return {"ok": True, "message": f"Created CodeCommit repository {name}", "repository": row}

    if action == "create_codebuild_project":
        name = (payload.get("name") or f"project-{_hex(4)}").strip()
        projects = gr.setdefault("codebuild", {}).setdefault("projects", [])
        if any(p.get("name") == name for p in projects):
            return {"ok": False, "error": f"Project '{name}' already exists"}
        row = _row(payload.get("id") or f"cb-{_hex()}", name, {
            "environment": payload.get("environment") or "Linux container",
            "lastBuild": payload.get("lastBuild") or "SUCCEEDED",
            "status": payload.get("status") or "Active",
        })
        projects.append(row)
        return {"ok": True, "message": f"Created CodeBuild project {name}", "project": row}

    if action == "create_codepipeline":
        name = (payload.get("name") or f"pipeline-{_hex(4)}").strip()
        pipes = gr.setdefault("codepipeline", {}).setdefault("pipelines", [])
        if any(p.get("name") == name for p in pipes):
            return {"ok": False, "error": f"Pipeline '{name}' already exists"}
        row = _row(payload.get("id") or f"cp-{_hex()}", name, {
            "stages": int(payload.get("stages") or 3),
            "lastExecution": payload.get("lastExecution") or "Succeeded",
            "status": payload.get("status") or "Active",
        })
        pipes.append(row)
        return {"ok": True, "message": f"Created CodePipeline {name}", "pipeline": row}

    if action == "create_lambda_layer":
        name = (payload.get("name") or f"layer-{_hex(4)}").strip()
        layers = gr.setdefault("lambda", {}).setdefault("layers", [])
        if any(l.get("name") == name for l in layers):
            return {"ok": False, "error": f"Layer '{name}' already exists"}
        row = _row(payload.get("id") or f"layer-{_hex()}", name, {
            "runtime": payload.get("runtime") or "Python 3.12",
            "version": int(payload.get("version") or 1),
            "status": payload.get("status") or "Active",
        })
        layers.append(row)
        return {"ok": True, "message": f"Created Lambda layer {name}", "layer": row}

    if action == "create_eks_node_group":
        name = (payload.get("name") or f"ng-{_hex(4)}").strip()
        groups = gr.setdefault("eks", {}).setdefault("node-groups", [])
        if any(g.get("name") == name for g in groups):
            return {"ok": False, "error": f"Node group '{name}' already exists"}
        row = _row(payload.get("id") or f"ng-{_hex()}", name, {
            "instanceType": payload.get("instanceType") or "t3.medium",
            "desired": int(payload.get("desired") or 2),
            "status": payload.get("status") or "Active",
        })
        groups.append(row)
        return {"ok": True, "message": f"Created EKS node group {name}", "node_group": row}

    if action == "create_ecs_cluster":
        name = (payload.get("name") or f"cluster-{_hex(4)}").strip()
        clusters = gr.setdefault("ecs", {}).setdefault("clusters", [])
        if any(c.get("name") == name for c in clusters):
            return {"ok": False, "error": f"Cluster '{name}' already exists"}
        row = _row(payload.get("id") or f"ecscluster-{_hex()}", name, {
            "services": int(payload.get("services") or 0),
            "tasks": int(payload.get("tasks") or 0),
            "status": payload.get("status") or "Active",
        })
        clusters.append(row)
        return {"ok": True, "message": f"Created ECS cluster {name}", "cluster": row}

    if action == "create_ecs_task":
        name = (payload.get("name") or f"task-{_hex(4)}").strip()
        tasks = gr.setdefault("ecs", {}).setdefault("tasks", [])
        if any(t.get("name") == name for t in tasks):
            return {"ok": False, "error": f"Task '{name}' already exists"}
        row = _row(payload.get("id") or f"ecstask-{_hex()}", name, {
            "launchType": payload.get("launchType") or "FARGATE",
            "count": int(payload.get("count") or 1),
            "status": payload.get("status") or "RUNNING",
        })
        tasks.append(row)
        return {"ok": True, "message": f"Created ECS task {name}", "task": row}

    if action == "create_rds_snapshot":
        name = (payload.get("name") or f"snap-{_hex(4)}").strip()
        snaps = gr.setdefault("rds", {}).setdefault("snapshots", [])
        if any(s.get("name") == name for s in snaps):
            return {"ok": False, "error": f"Snapshot '{name}' already exists"}
        row = _row(payload.get("id") or f"snap-{_hex()}", name, {
            "engine": payload.get("engine") or "PostgreSQL",
            "status": payload.get("status") or "available",
            "created": payload.get("created") or _now(),
        })
        snaps.append(row)
        return {"ok": True, "message": f"Created RDS snapshot {name}", "snapshot": row}

    if action == "create_elasticache_cluster":
        name = (payload.get("name") or f"cache-{_hex(4)}").strip()
        clusters = gr.setdefault("elasticache", {}).setdefault("clusters", [])
        if any(c.get("name") == name for c in clusters):
            return {"ok": False, "error": f"Cluster '{name}' already exists"}
        row = _row(payload.get("id") or f"cache-{_hex()}", name, {
            "engine": payload.get("engine") or "Redis OSS",
            "nodeType": payload.get("nodeType") or "cache.t3.micro",
            "nodes": int(payload.get("nodes") or 1),
            "status": payload.get("status") or "available",
        })
        clusters.append(row)
        return {"ok": True, "message": f"Created ElastiCache cluster {name}", "cluster": row}

    if action == "create_redshift_cluster":
        name = (payload.get("name") or f"rs-{_hex(4)}").strip()
        clusters = gr.setdefault("redshift", {}).setdefault("clusters", [])
        if any(c.get("name") == name for c in clusters):
            return {"ok": False, "error": f"Cluster '{name}' already exists"}
        row = _row(payload.get("id") or f"redshift-{_hex()}", name, {
            "nodeType": payload.get("nodeType") or "ra3.xlplus",
            "nodes": int(payload.get("nodes") or 2),
            "status": payload.get("status") or "available",
        })
        clusters.append(row)
        return {"ok": True, "message": f"Created Redshift cluster {name}", "cluster": row}

    if action == "create_opensearch_domain":
        name = (payload.get("name") or f"os-{_hex(4)}").strip()
        domains = gr.setdefault("opensearch", {}).setdefault("domains", [])
        if any(d.get("name") == name for d in domains):
            return {"ok": False, "error": f"Domain '{name}' already exists"}
        row = _row(payload.get("id") or f"os-{_hex()}", name, {
            "version": payload.get("version") or "OpenSearch 2.13",
            "nodes": int(payload.get("nodes") or 3),
            "status": payload.get("status") or "Active",
        })
        domains.append(row)
        return {"ok": True, "message": f"Created OpenSearch domain {name}", "domain": row}

    if action == "create_kinesis_stream":
        name = (payload.get("name") or f"stream-{_hex(4)}").strip()
        streams = gr.setdefault("kinesis", {}).setdefault("streams", [])
        if any(s.get("name") == name for s in streams):
            return {"ok": False, "error": f"Stream '{name}' already exists"}
        row = _row(payload.get("id") or f"kinesis-{_hex()}", name, {
            "mode": payload.get("mode") or "On-demand",
            "shards": int(payload.get("shards") or 1),
            "status": payload.get("status") or "Active",
        })
        streams.append(row)
        return {"ok": True, "message": f"Created Kinesis stream {name}", "stream": row}

    if action == "create_glue_job":
        name = (payload.get("name") or f"job-{_hex(4)}").strip()
        jobs = gr.setdefault("glue", {}).setdefault("jobs", [])
        if any(j.get("name") == name for j in jobs):
            return {"ok": False, "error": f"Job '{name}' already exists"}
        row = _row(payload.get("id") or f"glue-job-{_hex()}", name, {
            "type": payload.get("type") or "Spark",
            "runs": int(payload.get("runs") or 0),
            "status": payload.get("status") or "Active",
        })
        jobs.append(row)
        return {"ok": True, "message": f"Created Glue job {name}", "job": row}

    if action == "create_glue_database":
        name = (payload.get("name") or f"db-{_hex(4)}").strip()
        dbs = gr.setdefault("glue", {}).setdefault("databases", [])
        if any(d.get("name") == name for d in dbs):
            return {"ok": False, "error": f"Database '{name}' already exists"}
        row = _row(payload.get("id") or f"glue-db-{_hex()}", name, {
            "tables": int(payload.get("tables") or 0),
            "status": payload.get("status") or "Active",
        })
        dbs.append(row)
        return {"ok": True, "message": f"Created Glue database {name}", "database": row}

    if action == "create_athena_workgroup":
        name = (payload.get("name") or f"wg-{_hex(4)}").strip()
        groups = gr.setdefault("athena", {}).setdefault("workgroups", [])
        if any(g.get("name") == name for g in groups):
            return {"ok": False, "error": f"Workgroup '{name}' already exists"}
        row = _row(payload.get("id") or f"athena-{_hex()}", name, {
            "queries": int(payload.get("queries") or 0),
            "bytesScanned": payload.get("bytesScanned") or "0 GB",
            "status": payload.get("status") or "Enabled",
        })
        groups.append(row)
        return {"ok": True, "message": f"Created Athena workgroup {name}", "workgroup": row}

    if action == "create_budget":
        name = (payload.get("name") or f"budget-{_hex(4)}").strip()
        budgets = gr.setdefault("billing", {}).setdefault("budgets", [])
        if any(b.get("name") == name for b in budgets):
            return {"ok": False, "error": f"Budget '{name}' already exists"}
        row = _row(payload.get("id") or f"budget-{_hex()}", name, {
            "amount": float(payload.get("amount") or 100),
            "actual": float(payload.get("actual") or 0),
            "status": payload.get("status") or "OK",
        })
        budgets.append(row)
        return {"ok": True, "message": f"Created budget {name}", "budget": row}

    if action == "create_org_account":
        name = (payload.get("name") or f"account-{_hex(4)}").strip()
        accounts = gr.setdefault("organizations", {}).setdefault("accounts", [])
        if any(a.get("name") == name for a in accounts):
            return {"ok": False, "error": f"Account '{name}' already exists"}
        row = _row(payload.get("id") or f"{random.randint(100000000000, 999999999999)}", name, {
            "email": payload.get("email") or f"{name}@example.com",
            "ou": payload.get("ou") or "Engineering",
            "status": payload.get("status") or "ACTIVE",
        })
        accounts.append(row)
        return {"ok": True, "message": f"Created org account {name}", "account": row}

    if action == "create_quota_request":
        name = (payload.get("name") or f"quota-{_hex(4)}").strip()
        reqs = gr.setdefault("servicequotas", {}).setdefault("requests", [])
        if any(r.get("name") == name for r in reqs):
            return {"ok": False, "error": f"Quota request '{name}' already exists"}
        row = _row(payload.get("id") or f"qr-{_hex()}", name, {
            "service": payload.get("service") or "EC2",
            "requested": int(payload.get("requested") or 64),
            "status": payload.get("status") or "CASE_OPENED",
        })
        reqs.append(row)
        return {"ok": True, "message": f"Created quota request {name}", "request": row}

    if action == "create_health_event":
        name = (payload.get("name") or f"event-{_hex(4)}").strip()
        events = gr.setdefault("health", {}).setdefault("events", [])
        if any(e.get("name") == name for e in events):
            return {"ok": False, "error": f"Health event '{name}' already exists"}
        row = _row(payload.get("id") or f"health-{_hex()}", name, {
            "service": payload.get("service") or "EC2",
            "impact": payload.get("impact") or "Informational",
            "status": payload.get("status") or "open",
        })
        events.append(row)
        return {"ok": True, "message": f"Created health event {name}", "event": row}

    if action == "create_trusted_advisor_check":
        name = (payload.get("name") or f"check-{_hex(4)}").strip()
        checks = gr.setdefault("trustedadvisor", {}).setdefault("checks", [])
        if any(c.get("name") == name for c in checks):
            return {"ok": False, "error": f"Check '{name}' already exists"}
        row = _row(payload.get("id") or f"ta-{_hex()}", name, {
            "category": payload.get("category") or "Security",
            "affected": int(payload.get("affected") or 0),
            "status": payload.get("status") or "OK",
        })
        checks.append(row)
        return {"ok": True, "message": f"Created Trusted Advisor check {name}", "check": row}

    if action == "create_wa_workload":
        name = (payload.get("name") or f"workload-{_hex(4)}").strip()
        workloads = gr.setdefault("wellarchitected", {}).setdefault("workloads", [])
        if any(w.get("name") == name for w in workloads):
            return {"ok": False, "error": f"Workload '{name}' already exists"}
        row = _row(payload.get("id") or f"wa-{_hex()}", name, {
            "lenses": payload.get("lenses") or "AWS Well-Architected Framework",
            "risks": int(payload.get("risks") or 0),
            "status": payload.get("status") or "Active",
        })
        workloads.append(row)
        return {"ok": True, "message": f"Created Well-Architected workload {name}", "workload": row}

    if action == "send_sqs":
        qname = payload.get("name") or "lab-queue"
        queues = gr.setdefault("sqs", {}).setdefault("queues", [])
        row = next((q for q in queues if q.get("name") == payload.get("name") or q.get("id") == payload.get("id")), None)
        if not row and queues:
            row = queues[0]
        if not row:
            row = _row(payload.get("id") or f"queue-{_hex()}", qname, {"type": "Standard", "messages": 0, "status": "Active"})
            queues.append(row)
        row["messages"] = int(row.get("messages") or 0) + int(payload.get("count") or 1)
        row["lastSend"] = _now()
        return {"ok": True, "message": f"Sent message to {row.get('name')}", "queue": row}

    if action == "receive_sqs":
        qname = payload.get("name") or "lab-queue"
        queues = gr.setdefault("sqs", {}).setdefault("queues", [])
        row = next((q for q in queues if q.get("name") == payload.get("name") or q.get("id") == payload.get("id")), None)
        if not row and queues:
            row = queues[0]
        if not row:
            row = _row(payload.get("id") or f"queue-{_hex()}", qname, {"type": "Standard", "messages": 0, "status": "Active"})
            queues.append(row)
        available = int(row.get("messages") or 0)
        took = min(available, int(payload.get("max") or 1))
        row["messages"] = available - took
        row["lastReceive"] = _now()
        return {"ok": True, "message": f"Received {took} message(s)", "queue": row, "count": took}

    if action == "purge_sqs":
        qname = payload.get("name") or "lab-queue"
        queues = gr.setdefault("sqs", {}).setdefault("queues", [])
        row = next((q for q in queues if q.get("name") == payload.get("name") or q.get("id") == payload.get("id")), None)
        if not row and queues:
            row = queues[0]
        if not row:
            row = _row(payload.get("id") or f"queue-{_hex()}", qname, {"type": "Standard", "messages": 0, "status": "Active"})
            queues.append(row)
        row["messages"] = 0
        row["lastPurge"] = _now()
        return {"ok": True, "message": f"Purged {row.get('name')}", "queue": row}

    if action == "get_secret_value":
        sname = payload.get("name") or "lab/secret"
        secrets = gr.setdefault("secretsmanager", {}).setdefault("secrets", [])
        row = next((s for s in secrets if s.get("name") == payload.get("name") or s.get("id") == payload.get("id")), None)
        if not row and secrets:
            row = secrets[0]
        if not row:
            row = _row(payload.get("id") or f"secret-{_hex()}", sname, {
                "rotation": "Disabled", "lastChanged": "Today", "status": "Active",
                "secretValue": f"lab-secret-{sname}", "versions": 1,
            })
            secrets.append(row)
        value = row.get("secretValue") or row.get("value") or f"lab-secret-{row.get('name', 'value')}"
        row["lastAccessed"] = _now()
        row["versions"] = int(row.get("versions") or 1)
        return {"ok": True, "message": "Secret retrieved", "secret": row, "value": value}

    if action == "rotate_secret":
        sname = payload.get("name") or "lab/secret"
        secrets = gr.setdefault("secretsmanager", {}).setdefault("secrets", [])
        row = next((s for s in secrets if s.get("name") == payload.get("name") or s.get("id") == payload.get("id")), None)
        if not row and secrets:
            row = secrets[0]
        if not row:
            row = _row(payload.get("id") or f"secret-{_hex()}", sname, {
                "rotation": "Disabled", "lastChanged": "Today", "status": "Active", "versions": 1,
            })
            secrets.append(row)
        row["rotation"] = "Enabled"
        row["versions"] = int(row.get("versions") or 1) + 1
        row["lastChanged"] = "Today"
        row["secretValue"] = f"rotated-{_hex(6)}"
        return {"ok": True, "message": f"Rotated {row.get('name')}", "secret": row}

    if action == "upsert_route53_record":
        zones = gr.setdefault("route53", {}).setdefault("hosted-zones", [])
        zone = next((z for z in zones if z.get("id") == payload.get("zone_id") or z.get("name") == payload.get("zone")), None)
        if not zone and zones:
            zone = zones[0]
        if not zone:
            zone = _row(payload.get("zone_id") or f"Z{_hex(10).upper()}", payload.get("zone") or "example.internal", {
                "type": "Private", "records": 0, "status": "available", "recordSets": [],
            })
            zones.append(zone)
        records = zone.setdefault("recordSets", [])
        name = (payload.get("record_name") or payload.get("name") or "app").strip()
        rtype = payload.get("type") or "A"
        existing = next((r for r in records if r.get("name") == name and r.get("type") == rtype), None)
        if existing:
            existing["value"] = payload.get("value") or existing.get("value")
            existing["ttl"] = int(payload.get("ttl") or existing.get("ttl") or 300)
            row = existing
        else:
            row = {
                "name": name, "type": rtype,
                "value": payload.get("value") or "10.0.0.10",
                "ttl": int(payload.get("ttl") or 300),
            }
            records.append(row)
            zone["records"] = len(records)
        return {"ok": True, "message": f"Upserted {rtype} {name}", "record": row, "zone": zone}

    if action == "create_cw_alarm":
        name = (payload.get("name") or f"alarm-{_hex(4)}").strip()
        alarms = state.setdefault("cwAlarms", [])
        if any(a.get("name") == name for a in alarms):
            return {"ok": False, "error": f"Alarm '{name}' already exists"}
        alarm = {
            "name": name,
            "region": payload.get("region") or "us-east-1",
            "metric": payload.get("metric") or "CPUUtilization",
            "namespace": payload.get("namespace") or "AWS/EC2",
            "state": payload.get("state") or "OK",
            "threshold": payload.get("threshold") or "> 80%",
        }
        alarms.append(alarm)
        return {"ok": True, "message": f"Created alarm {name}", "alarm": alarm}

    if action == "delete_cw_alarm":
        name = payload.get("name") or ""
        before = len(state.get("cwAlarms") or [])
        state["cwAlarms"] = [a for a in (state.get("cwAlarms") or []) if a.get("name") != name]
        if len(state["cwAlarms"]) == before:
            return {"ok": False, "error": "Alarm not found"}
        return {"ok": True, "message": f"Deleted alarm {name}"}

    if action == "create_cw_dashboard":
        name = (payload.get("name") or f"dash-{_hex(4)}").strip()
        dashes = state.setdefault("cwDashboards", [])
        if any(d.get("name") == name for d in dashes):
            return {"ok": False, "error": f"Dashboard '{name}' already exists"}
        dash = {
            "name": name,
            "region": payload.get("region") or "us-east-1",
            "widgets": int(payload.get("widgets") or 0),
            "created": _now(),
        }
        dashes.append(dash)
        return {"ok": True, "message": f"Created dashboard {name}", "dashboard": dash}

    if action == "delete_cw_dashboard":
        name = payload.get("name") or ""
        before = len(state.get("cwDashboards") or [])
        state["cwDashboards"] = [d for d in (state.get("cwDashboards") or []) if d.get("name") != name]
        if len(state["cwDashboards"]) == before:
            return {"ok": False, "error": "Dashboard not found"}
        return {"ok": True, "message": f"Deleted dashboard {name}"}

    return None
