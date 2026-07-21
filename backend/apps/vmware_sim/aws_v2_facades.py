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
