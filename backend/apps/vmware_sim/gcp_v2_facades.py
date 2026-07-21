"""GCP Console V2 service facades (Cloud Run, GKE, Pub/Sub, Functions, SQL, etc.).

Seed + action handlers for Lab Environment expansions inside FixitLab.
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


def seed_v2(project: str = "fixitlab-prod-247319") -> dict[str, Any]:
    return {
        "cloud_run_services": [
            {
                "id": f"run-{_hex()}", "name": "api-service", "region": "us-central1",
                "project": project, "url": f"https://api-service-xyz-{project}.a.run.app",
                "image": "gcr.io/cloudrun/hello", "cpu": "1", "memory": "512Mi",
                "min_instances": 0, "max_instances": 10, "concurrency": 80,
                "revisions": [
                    {"name": "api-service-00001-abc", "traffic_pct": 100, "active": True},
                ],
            },
        ],
        "pubsub_topics": [
            {
                "id": f"topic-{_hex()}", "name": "orders", "project": project,
                "message_retention": "7d", "subscriptions": [
                    {"name": "orders-push", "type": "Push", "endpoint": "https://api-service-xyz.a.run.app/pubsub",
                     "ack_deadline_s": 10, "undelivered": 0},
                    {"name": "orders-pull", "type": "Pull", "endpoint": "",
                     "ack_deadline_s": 60, "undelivered": 3},
                ],
            },
        ],
        "gke_clusters": [
            {
                "id": f"gke-{_hex()}", "name": "gke-prod", "location": "us-central1",
                "mode": "Standard", "version": "1.29.4-gke.1043002", "status": "RUNNING",
                "endpoint": "35.188.10.20", "node_pools": [
                    {
                        "name": "default-pool", "machine_type": "e2-standard-4",
                        "node_count": 3, "autoscaling": {"min": 1, "max": 6},
                        "status": "RUNNING",
                    },
                ],
            },
        ],
        "cloud_functions": [
            {
                "id": f"fn-{_hex()}", "name": "process-order", "region": "us-central1",
                "runtime": "python312", "entry_point": "handle", "gen": "2nd gen",
                "trigger": "HTTP", "url": f"https://us-central1-{project}.cloudfunctions.net/process-order",
                "status": "ACTIVE", "invocations_24h": 214,
            },
        ],
        "cloud_sql_instances": [
            {
                "id": f"sql-{_hex()}", "name": "sql-prod", "database_version": "POSTGRES_15",
                "tier": "db-custom-2-7680", "region": "us-central1", "state": "RUNNABLE",
                "ip": "34.66.10.5", "private_ip": "10.128.0.50",
                "databases": [
                    {"name": "appdb", "charset": "UTF8"},
                    {"name": "postgres", "charset": "UTF8"},
                ],
            },
        ],
        "secrets": [
            {
                "id": f"sec-{_hex()}", "name": "db-password", "project": project,
                "versions": [
                    {"version": "1", "state": "ENABLED", "created": _now()},
                    {"version": "2", "state": "ENABLED", "created": _now()},
                ],
            },
        ],
        "armor_policies": [
            {
                "id": f"armor-{_hex()}", "name": "edge-waf",
                "rules": [
                    {"priority": 1000, "action": "allow", "match": "srcIpRanges=*", "description": "default allow"},
                    {"priority": 100, "action": "deny(403)", "match": "expr: evaluatePreconfiguredExpr('sqli-v33-stable')",
                     "description": "SQLi"},
                ],
            },
        ],
        "spanner_instances": [
            {
                "id": f"span-{_hex()}", "name": "spanner-prod", "config": "regional-us-central1",
                "processing_units": 100, "state": "READY",
                "databases": [
                    {"name": "ledger", "tables": 4, "size_gb": 2.1},
                ],
            },
        ],
        "bigquery_datasets": [
            {
                "id": f"bq-{_hex()}", "dataset_id": "analytics", "project": project,
                "location": "US", "tables": [
                    {"name": "events", "rows": 1250000, "size_gb": 4.2, "type": "TABLE"},
                    {"name": "daily_agg", "rows": 3650, "size_gb": 0.1, "type": "TABLE"},
                ],
            },
        ],
        "http_load_balancers": [
            {
                "id": f"lb-{_hex()}", "name": "web-https-lb", "protocol": "HTTPS",
                "ip": "34.111.20.5", "port": 443, "backend_service": "web-backend",
                "backends": [{"instance_group": "web-ig", "zone": "us-central1-a", "capacity": 100}],
                "health_check": "hc-web-https", "ssl_cert": "fixitlab-io",
                "status": "ACTIVE",
            },
        ],
    }


def ensure_v2(state: dict) -> None:
    project = (state.get("project") or {}).get("id") or "fixitlab-prod-247319"
    seed = seed_v2(project)
    for key, value in seed.items():
        if key not in state or state.get(key) is None:
            state[key] = value


def apply_v2_action(state: dict, action: str, payload: dict) -> dict | None:
    project = (state.get("project") or {}).get("id") or "fixitlab-prod-247319"

    if action == "create_cloud_run_service":
        name = (payload.get("name") or f"svc-{_hex(4)}").strip()
        if any(s.get("name") == name for s in state.get("cloud_run_services") or []):
            return {"ok": False, "error": f"Service '{name}' already exists"}
        item = {
            "id": f"run-{_hex()}", "name": name, "region": payload.get("region") or "us-central1",
            "project": project,
            "url": f"https://{name}-xyz-{project}.a.run.app",
            "image": payload.get("image") or "gcr.io/cloudrun/hello",
            "cpu": payload.get("cpu") or "1", "memory": payload.get("memory") or "512Mi",
            "min_instances": int(payload.get("min_instances") or 0),
            "max_instances": int(payload.get("max_instances") or 10),
            "concurrency": int(payload.get("concurrency") or 80),
            "revisions": [{"name": f"{name}-00001-abc", "traffic_pct": 100, "active": True}],
        }
        state.setdefault("cloud_run_services", []).append(item)
        return {"ok": True, "message": f"Deployed Cloud Run service {name}", "service": item}

    if action == "update_cloud_run_traffic":
        name = payload.get("name") or ""
        svc = next((s for s in state.get("cloud_run_services") or [] if s.get("name") == name), None)
        if not svc:
            return {"ok": False, "error": "Cloud Run service not found"}
        pct = int(payload.get("traffic_pct") or 100)
        revs = svc.setdefault("revisions", [])
        if len(revs) < 2:
            revs.append({"name": f"{name}-00002-xyz", "traffic_pct": 0, "active": True})
        revs[0]["traffic_pct"] = max(0, 100 - pct)
        revs[1]["traffic_pct"] = pct
        return {"ok": True, "message": f"Updated traffic on {name}", "service": svc}

    if action == "create_pubsub_topic":
        name = (payload.get("name") or f"topic-{_hex(4)}").strip()
        if any(t.get("name") == name for t in state.get("pubsub_topics") or []):
            return {"ok": False, "error": f"Topic '{name}' already exists"}
        item = {
            "id": f"topic-{_hex()}", "name": name, "project": project,
            "message_retention": payload.get("retention") or "7d", "subscriptions": [],
        }
        state.setdefault("pubsub_topics", []).append(item)
        return {"ok": True, "message": f"Created topic {name}", "topic": item}

    if action == "create_pubsub_subscription":
        topic_name = payload.get("topic") or ""
        topic = next((t for t in state.get("pubsub_topics") or [] if t.get("name") == topic_name), None)
        if not topic:
            return {"ok": False, "error": "Topic not found"}
        sub_name = (payload.get("name") or f"{topic_name}-sub").strip()
        sub = {
            "name": sub_name,
            "type": payload.get("type") or "Pull",
            "endpoint": payload.get("endpoint") or "",
            "ack_deadline_s": int(payload.get("ack_deadline_s") or 10),
            "undelivered": 0,
        }
        topic.setdefault("subscriptions", []).append(sub)
        return {"ok": True, "message": f"Created subscription {sub_name}", "topic": topic}

    if action == "publish_pubsub":
        topic_name = payload.get("topic") or ""
        topic = next((t for t in state.get("pubsub_topics") or [] if t.get("name") == topic_name), None)
        if not topic:
            return {"ok": False, "error": "Topic not found"}
        for sub in topic.get("subscriptions") or []:
            if sub.get("type") == "Pull":
                sub["undelivered"] = int(sub.get("undelivered") or 0) + 1
        topic["last_publish"] = _now()
        return {"ok": True, "message": f"Published message to {topic_name}", "topic": topic}

    if action == "create_gke_cluster":
        name = (payload.get("name") or f"gke-{_hex(4)}").strip()
        if any(c.get("name") == name for c in state.get("gke_clusters") or []):
            return {"ok": False, "error": f"Cluster '{name}' already exists"}
        nodes = int(payload.get("node_count") or 3)
        item = {
            "id": f"gke-{_hex()}", "name": name,
            "location": payload.get("location") or "us-central1",
            "mode": payload.get("mode") or "Standard",
            "version": payload.get("version") or "1.29.4-gke.1043002",
            "status": "RUNNING", "endpoint": f"35.{random.randint(1, 250)}.10.{random.randint(1, 250)}",
            "node_pools": [{
                "name": "default-pool",
                "machine_type": payload.get("machine_type") or "e2-standard-4",
                "node_count": nodes,
                "autoscaling": {"min": 1, "max": max(nodes, 6)},
                "status": "RUNNING",
            }],
        }
        state.setdefault("gke_clusters", []).append(item)
        return {"ok": True, "message": f"Created GKE cluster {name}", "cluster": item}

    if action == "resize_gke_node_pool":
        cluster_name = payload.get("cluster") or ""
        pool_name = payload.get("pool") or "default-pool"
        cluster = next((c for c in state.get("gke_clusters") or [] if c.get("name") == cluster_name), None)
        if not cluster:
            return {"ok": False, "error": "Cluster not found"}
        pool = next((p for p in cluster.get("node_pools") or [] if p.get("name") == pool_name), None)
        if not pool:
            return {"ok": False, "error": "Node pool not found"}
        pool["node_count"] = max(0, int(payload.get("node_count") or pool.get("node_count") or 1))
        return {"ok": True, "message": f"Resized {pool_name} to {pool['node_count']}", "cluster": cluster}

    if action == "create_cloud_function":
        name = (payload.get("name") or f"fn-{_hex(4)}").strip()
        if any(f.get("name") == name for f in state.get("cloud_functions") or []):
            return {"ok": False, "error": f"Function '{name}' already exists"}
        item = {
            "id": f"fn-{_hex()}", "name": name,
            "region": payload.get("region") or "us-central1",
            "runtime": payload.get("runtime") or "nodejs20",
            "entry_point": payload.get("entry_point") or "helloHttp",
            "gen": "2nd gen", "trigger": payload.get("trigger") or "HTTP",
            "url": f"https://us-central1-{project}.cloudfunctions.net/{name}",
            "status": "ACTIVE", "invocations_24h": 0,
        }
        state.setdefault("cloud_functions", []).append(item)
        return {"ok": True, "message": f"Deployed function {name}", "function": item}

    if action == "create_sql_instance":
        name = (payload.get("name") or f"sql-{_hex(4)}").strip()
        if any(i.get("name") == name for i in state.get("cloud_sql_instances") or []):
            return {"ok": False, "error": f"Instance '{name}' already exists"}
        item = {
            "id": f"sql-{_hex()}", "name": name,
            "database_version": payload.get("database_version") or "POSTGRES_15",
            "tier": payload.get("tier") or "db-custom-1-3840",
            "region": payload.get("region") or "us-central1",
            "state": "RUNNABLE",
            "ip": f"34.{random.randint(1, 250)}.10.{random.randint(1, 250)}",
            "private_ip": f"10.128.0.{random.randint(20, 200)}",
            "databases": [{"name": "postgres", "charset": "UTF8"}],
        }
        state.setdefault("cloud_sql_instances", []).append(item)
        return {"ok": True, "message": f"Created Cloud SQL instance {name}", "instance": item}

    if action == "create_sql_database":
        inst_name = payload.get("instance") or ""
        inst = next((i for i in state.get("cloud_sql_instances") or [] if i.get("name") == inst_name), None)
        if not inst:
            return {"ok": False, "error": "SQL instance not found"}
        db_name = (payload.get("name") or "appdb").strip()
        if any(d.get("name") == db_name for d in inst.get("databases") or []):
            return {"ok": False, "error": f"Database '{db_name}' already exists"}
        inst.setdefault("databases", []).append({"name": db_name, "charset": "UTF8"})
        return {"ok": True, "message": f"Created database {db_name}", "instance": inst}

    if action == "create_secret":
        name = (payload.get("name") or f"secret-{_hex(4)}").strip()
        if any(s.get("name") == name for s in state.get("secrets") or []):
            return {"ok": False, "error": f"Secret '{name}' already exists"}
        item = {
            "id": f"sec-{_hex()}", "name": name, "project": project,
            "versions": [{"version": "1", "state": "ENABLED", "created": _now()}],
        }
        state.setdefault("secrets", []).append(item)
        return {"ok": True, "message": f"Created secret {name}", "secret": item}

    if action == "add_secret_version":
        name = payload.get("name") or ""
        sec = next((s for s in state.get("secrets") or [] if s.get("name") == name), None)
        if not sec:
            return {"ok": False, "error": "Secret not found"}
        vers = sec.setdefault("versions", [])
        next_v = str(len(vers) + 1)
        vers.append({"version": next_v, "state": "ENABLED", "created": _now()})
        return {"ok": True, "message": f"Added version {next_v} to {name}", "secret": sec}

    if action == "create_armor_policy":
        name = (payload.get("name") or f"armor-{_hex(4)}").strip()
        if any(p.get("name") == name for p in state.get("armor_policies") or []):
            return {"ok": False, "error": f"Policy '{name}' already exists"}
        item = {
            "id": f"armor-{_hex()}", "name": name,
            "rules": [{"priority": 2147483647, "action": "allow", "match": "srcIpRanges=*", "description": "default"}],
        }
        state.setdefault("armor_policies", []).append(item)
        return {"ok": True, "message": f"Created Armor policy {name}", "policy": item}

    if action == "add_armor_rule":
        name = payload.get("name") or payload.get("policy") or ""
        pol = next((p for p in state.get("armor_policies") or [] if p.get("name") == name), None)
        if not pol:
            return {"ok": False, "error": "Armor policy not found"}
        rule = {
            "priority": int(payload.get("priority") or 1000),
            "action": payload.get("action") or "deny(403)",
            "match": payload.get("match") or "srcIpRanges=0.0.0.0/0",
            "description": payload.get("description") or "",
        }
        pol.setdefault("rules", []).insert(0, rule)
        return {"ok": True, "message": f"Added rule to {name}", "policy": pol}

    if action == "create_spanner_instance":
        name = (payload.get("name") or f"spanner-{_hex(4)}").strip()
        if any(s.get("name") == name for s in state.get("spanner_instances") or []):
            return {"ok": False, "error": f"Instance '{name}' already exists"}
        item = {
            "id": f"span-{_hex()}", "name": name,
            "config": payload.get("config") or "regional-us-central1",
            "processing_units": int(payload.get("processing_units") or 100),
            "state": "READY",
            "databases": [],
        }
        state.setdefault("spanner_instances", []).append(item)
        return {"ok": True, "message": f"Created Spanner instance {name}", "instance": item}

    if action == "create_bigquery_dataset":
        dataset_id = (payload.get("dataset_id") or payload.get("name") or f"ds_{_hex(4)}").strip()
        if any(d.get("dataset_id") == dataset_id for d in state.get("bigquery_datasets") or []):
            return {"ok": False, "error": f"Dataset '{dataset_id}' already exists"}
        item = {
            "id": f"bq-{_hex()}", "dataset_id": dataset_id, "project": project,
            "location": payload.get("location") or "US", "tables": [],
        }
        state.setdefault("bigquery_datasets", []).append(item)
        return {"ok": True, "message": f"Created dataset {dataset_id}", "dataset": item}

    if action == "create_bigquery_table":
        dataset_id = payload.get("dataset_id") or payload.get("dataset") or ""
        ds = next((d for d in state.get("bigquery_datasets") or [] if d.get("dataset_id") == dataset_id), None)
        if not ds:
            return {"ok": False, "error": "Dataset not found"}
        table_name = (payload.get("name") or f"table_{_hex(4)}").strip()
        if any(t.get("name") == table_name for t in ds.get("tables") or []):
            return {"ok": False, "error": f"Table '{table_name}' already exists"}
        table = {
            "name": table_name,
            "rows": int(payload.get("rows") or 0),
            "size_gb": float(payload.get("size_gb") or 0),
            "type": payload.get("type") or "TABLE",
        }
        ds.setdefault("tables", []).append(table)
        return {"ok": True, "message": f"Created table {table_name}", "dataset": ds}

    if action == "run_bigquery_query":
        sql = (payload.get("sql") or "SELECT 1").strip()
        rows = [
            {"col1": "alpha", "col2": 42, "col3": _now()[:10]},
            {"col1": "beta", "col2": 17, "col3": _now()[:10]},
            {"col1": "gamma", "col2": 99, "col3": _now()[:10]},
        ]
        job = {
            "id": f"job_{_hex()}", "sql": sql[:200], "state": "DONE",
            "bytes_processed": 1048576, "rows_returned": len(rows), "created": _now(),
        }
        state.setdefault("bigquery_jobs", []).insert(0, job)
        state["bigquery_jobs"] = state["bigquery_jobs"][:20]
        return {"ok": True, "message": f"Query job {job['id']} completed", "job": job, "rows": rows}

    if action == "create_http_load_balancer":
        name = (payload.get("name") or f"lb-{_hex(4)}").strip()
        if any(lb.get("name") == name for lb in state.get("http_load_balancers") or []):
            return {"ok": False, "error": f"Load balancer '{name}' already exists"}
        item = {
            "id": f"lb-{_hex()}", "name": name,
            "protocol": payload.get("protocol") or "HTTPS",
            "ip": f"34.{random.randint(1, 250)}.{random.randint(1, 250)}.{random.randint(1, 250)}",
            "port": int(payload.get("port") or 443),
            "backend_service": payload.get("backend_service") or f"{name}-backend",
            "backends": [{"instance_group": payload.get("instance_group") or "web-ig",
                          "zone": "us-central1-a", "capacity": 100}],
            "health_check": payload.get("health_check") or f"hc-{name}",
            "ssl_cert": payload.get("ssl_cert") or "fixitlab-io",
            "status": "ACTIVE",
        }
        state.setdefault("http_load_balancers", []).append(item)
        return {"ok": True, "message": f"Created load balancer {name}", "load_balancer": item}

    if action == "upload_gcs_object":
        bucket_name = payload.get("bucket") or ""
        bucket = next((b for b in state.get("buckets") or [] if b.get("name") == bucket_name), None)
        if not bucket:
            return {"ok": False, "error": "Bucket not found"}
        obj_name = (payload.get("name") or f"uploads/object-{_hex(4)}.bin").strip()
        obj = {"name": obj_name, "size_kb": int(payload.get("size_kb") or 64)}
        bucket.setdefault("objects", []).append(obj)
        return {"ok": True, "message": f"Uploaded gs://{bucket_name}/{obj_name}", "bucket": bucket, "object": obj}

    return None
