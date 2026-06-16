#!/usr/bin/env python3
"""Merge multiple .env sources into one file (stdout). First file wins per key."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES = [
    ROOT / "deploy" / "production.env",
    ROOT / ".env.production",
    ROOT / ".env",
]

SKIP_KEYS = frozenset({
    "VAULT_ROLE_ID",
    "VAULT_SECRET_ID",
    "VAULT_UNSEAL_KEY",
    "VAULT_TOKEN",
})


def parse_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key in SKIP_KEYS:
            continue
        if key not in data or not data[key].strip():
            data[key] = value.strip()
    return data


def main() -> None:
    sources = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else DEFAULT_SOURCES
    merged: dict[str, str] = {}
    used: list[str] = []
    for src in sources:
        chunk = parse_env(src)
        if chunk:
            used.append(str(src))
        for key, value in chunk.items():
            if key not in merged or not merged[key].strip():
                merged[key] = value

    merged["VAULT_ENABLED"] = "true"
    merged.setdefault("VAULT_ADDR", "http://127.0.0.1:8200")

    for key in sorted(merged.keys()):
        print(f"{key}={merged[key]}")

    print(f"# merged from: {', '.join(used) or 'none'}", file=sys.stderr)
    if not merged or len(merged) <= 2:
        print("ERROR: no env variables found to merge", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
