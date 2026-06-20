#!/usr/bin/env python3
"""
Wire a FixitLab env file for the four-droplet cluster topology.

Patches the env file (default .env.cluster) so each service points at the correct
droplet over the private VPC:

    D1 Edge  : redis, rabbitmq, vault          -> EDGE_PRIVATE_IP
    D2 App   : backend + celery (no host edit; runs the app)
    D3 Data  : postgres + pgbouncer            -> DATA_PRIVATE_IP
    D4 Labs  : docker engine (remote)          -> ssh://root@LABS_PRIVATE_IP

Keys rewritten:
    POSTGRES_HOST        = <DATA_PRIVATE_IP>
    PGBOUNCER_HOST       = <DATA_PRIVATE_IP>      (port 6432)
    PGBOUNCER_PORT       = 6432
    REDIS_HOST           = <EDGE_PRIVATE_IP>
    CELERY_BROKER_URL    = amqp://<user>:<pass>@<EDGE_PRIVATE_IP>:5672//
    CELERY_RESULT_BACKEND= redis://:<redis_pass>@<EDGE_PRIVATE_IP>:6379/2
    DOCKER_SOCKET        = ssh://root@<LABS_PRIVATE_IP>
    DOCKER_HOST          = ssh://root@<LABS_PRIVATE_IP>
    VAULT_ADDR           = http://<EDGE_PRIVATE_IP>:8200
    APP_PRIVATE_IP       = <APP_PRIVATE_IP>       (consumed by the edge gateway)
    DJANGO_ALLOWED_HOSTS += APP_PRIVATE_IP, EDGE_PUBLIC_IP

Usage:
    EDGE_PRIVATE_IP=10.0.0.1 APP_PRIVATE_IP=10.0.0.2 DATA_PRIVATE_IP=10.0.0.3 \
    LABS_PRIVATE_IP=10.0.0.4 EDGE_PUBLIC_IP=203.0.113.10 \
    python3 scripts/ci-wire-cluster-env.py --file .env.cluster

DRY_RUN=1 prints the resulting diff (IPs are not secrets) without writing.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


def _is_truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in {"1", "true", "yes", "on"}


def read_rows(text: str) -> list[str]:
    return text.splitlines()


def get_val(lines: list[str], key: str) -> str | None:
    pat = re.compile(rf"^{re.escape(key)}=(.*)$")
    for line in lines:
        m = pat.match(line)
        if m:
            return m.group(1)
    return None


def set_val(lines: list[str], key: str, value: str) -> None:
    pat = re.compile(rf"^{re.escape(key)}=")
    for i, line in enumerate(lines):
        if pat.match(line):
            lines[i] = f"{key}={value}"
            return
    lines.append(f"{key}={value}")


def host_from(value: str | None, fallback: str) -> str:
    if value:
        m = re.search(r"@([^:/?#]+)", value)
        if m:
            return m.group(1)
    return fallback


def creds_from_broker(value: str | None) -> tuple[str, str]:
    """Return (user, password) parsed from amqp://user:pass@host..."""
    if value:
        m = re.search(r"://([^:@/]+):([^@]*)@", value)
        if m:
            return m.group(1), m.group(2)
    return "fixitlab", ""


def redis_pass_from(value: str | None) -> str:
    if value:
        m = re.search(r"://(?::([^@]*))?@", value)
        if m and m.group(1) is not None:
            return m.group(1)
        m2 = re.search(r"://([^@]*)@", value)
        if m2:
            return m2.group(1).lstrip(":")
    return ""


def merge_allowed_hosts(lines: list[str], extra: list[str]) -> None:
    cur = get_val(lines, "DJANGO_ALLOWED_HOSTS") or ""
    parts = [p.strip() for p in cur.split(",") if p.strip()]
    for ip in extra:
        if ip and ip not in parts:
            parts.append(ip)
    set_val(lines, "DJANGO_ALLOWED_HOSTS", ",".join(parts))


def main() -> int:
    ap = argparse.ArgumentParser(description="Wire env for four-droplet cluster")
    ap.add_argument("--file", default=os.environ.get("OUT_FILE", ".env.cluster"))
    args = ap.parse_args()

    edge = os.environ.get("EDGE_PRIVATE_IP", "")
    app = os.environ.get("APP_PRIVATE_IP", "")
    data = os.environ.get("DATA_PRIVATE_IP", "")
    labs = os.environ.get("LABS_PRIVATE_IP", "")
    edge_public = os.environ.get("EDGE_PUBLIC_IP", "")

    missing = [n for n, v in [
        ("EDGE_PRIVATE_IP", edge), ("APP_PRIVATE_IP", app),
        ("DATA_PRIVATE_IP", data), ("LABS_PRIVATE_IP", labs),
    ] if not v]
    if missing:
        print(f"ERROR: missing required IPs: {', '.join(missing)}", file=sys.stderr)
        return 2

    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: env file not found: {path}", file=sys.stderr)
        return 2

    lines = read_rows(path.read_text(encoding="utf-8"))

    rabbit_user, rabbit_pass = creds_from_broker(get_val(lines, "CELERY_BROKER_URL"))
    rabbit_pass = get_val(lines, "RABBITMQ_PASS") or rabbit_pass
    redis_pass = get_val(lines, "REDIS_PASSWORD") or redis_pass_from(get_val(lines, "CELERY_RESULT_BACKEND"))

    # ── Data droplet (D3) ──
    set_val(lines, "POSTGRES_HOST", data)
    set_val(lines, "PGBOUNCER_HOST", data)
    set_val(lines, "PGBOUNCER_PORT", "6432")

    # ── Edge droplet (D1): redis / rabbitmq / vault ──
    set_val(lines, "REDIS_HOST", edge)
    if rabbit_pass:
        set_val(lines, "CELERY_BROKER_URL", f"amqp://{rabbit_user}:{rabbit_pass}@{edge}:5672//")
    if redis_pass:
        set_val(lines, "CELERY_RESULT_BACKEND", f"redis://:{redis_pass}@{edge}:6379/2")
    set_val(lines, "VAULT_ADDR", f"http://{edge}:8200")

    # ── Labs droplet (D4): remote docker engine ──
    set_val(lines, "DOCKER_SOCKET", f"ssh://root@{labs}")
    set_val(lines, "DOCKER_HOST", f"ssh://root@{labs}")
    set_val(lines, "DOCKER_NETWORK", get_val(lines, "DOCKER_NETWORK") or "fixitlab_labs")
    set_val(lines, "LAB_PROVIDER", "docker")

    # ── Edge gateway needs the app private IP for the upstream template ──
    set_val(lines, "APP_PRIVATE_IP", app)

    merge_allowed_hosts(lines, [app, edge, edge_public])

    out_text = "\n".join(lines).rstrip("\n") + "\n"

    dry_run = _is_truthy(os.environ.get("DRY_RUN"))
    summary_keys = [
        "POSTGRES_HOST", "PGBOUNCER_HOST", "PGBOUNCER_PORT", "REDIS_HOST",
        "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "DOCKER_SOCKET",
        "VAULT_ADDR", "APP_PRIVATE_IP", "DJANGO_ALLOWED_HOSTS",
    ]

    def redact(key: str, val: str) -> str:
        # Mask embedded passwords in URLs; IPs and ports are safe to show.
        # Handles amqp://user:pass@host  AND  redis://:pass@host (empty user).
        return re.sub(r"://([^:@/]*):([^@]+)@", r"://\1:****@", val)

    if dry_run:
        print(f"[wire-cluster] DRY_RUN — would patch {path} with:")
        for k in summary_keys:
            v = get_val(lines, k) or ""
            print(f"    {k}={redact(k, v)}")
        print("[wire-cluster] DRY_RUN — not writing file")
        return 0

    path.write_text(out_text, encoding="utf-8")
    os.chmod(path, 0o600)
    print(f"[wire-cluster] patched {path} for four-droplet topology")
    for k in summary_keys:
        v = get_val(lines, k) or ""
        print(f"    {k}={redact(k, v)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
