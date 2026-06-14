#!/usr/bin/env python3
"""Convert .env files ↔ Vault KV JSON (stdlib only)."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def parse_env(path: str | Path) -> dict[str, str]:
    data: dict[str, str] = {}
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            data[key.strip()] = value.strip()
    return data


def env_to_json(path: str) -> None:
    print(json.dumps(parse_env(path), ensure_ascii=False))


def kv_json_to_env(payload: str) -> None:
    obj = json.loads(payload)
    inner = obj.get("data", {}).get("data")
    if inner is None and isinstance(obj.get("data"), dict):
        inner = obj["data"]
    if inner is None:
        inner = obj
    if not isinstance(inner, dict):
        raise SystemExit("Unexpected Vault KV JSON shape")
    for key in sorted(inner.keys()):
        value = inner[key]
        if value is None:
            value = ""
        text = str(value)
        if "\n" in text:
            text = text.replace("\n", "\\n")
        print(f"{key}={text}")


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: env-kv-helper.py env-to-json PATH", file=sys.stderr)
        print("       env-kv-helper.py kv-to-env   (reads JSON from stdin)", file=sys.stderr)
        raise SystemExit(2)
    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "env-to-json":
        env_to_json(arg)
    elif cmd == "kv-to-env":
        kv_json_to_env(sys.stdin.read())
    else:
        raise SystemExit(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
