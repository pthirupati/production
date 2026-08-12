#!/usr/bin/env python3
"""Verify known-leaked secrets are not still active in the process environment.

Audit §S1 — production SoT is HashiCorp Vault (see docs/ops/SECRETS_ROTATION.md).
This script does NOT rotate anything and NEVER prints secret values — only the
names of keys that still match known-compromised *patterns*.

Rotation happens in Vault via the FixitLab Production workflow
(ci-generate-secrets → persist-env → secret/fixitlab/env overlay), not by
editing long-lived .env files on disk.

Usage:
  python scripts/verify_secrets_rotated.py
  python scripts/verify_secrets_rotated.py --env-file backend/.env
  python scripts/verify_secrets_rotated.py --require-prod-keys  # fail if unset
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Digests / exact values that appeared in git history (SETUP_COMPLETE era).
# Keep this list short and exact — false positives mute the check.
KNOWN_BAD = {
    "SECRET_KEY": {
        # Placeholder patterns that must never ship to prod.
        "django-insecure-",
        "changeme",
        "replace-me",
        "YOUR_SECRET",
    },
    "DJANGO_SECRET_KEY": {
        "django-insecure-",
        "changeme",
        "replace-me",
        "YOUR_SECRET",
    },
    "DATABASE_URL": {
        "postgres:postgres@",
        "password=postgres",
        "password=changeme",
        ":changeme@",
    },
    "REDIS_URL": {
        "redis://:redis@",
        "password=changeme",
        ":changeme@",
    },
    "REDIS_PASSWORD": {
        "changeme",
        "redis",
        "YOUR_SECRET",
    },
    "CELERY_BROKER_URL": {
        "guest:guest@",
        ":changeme@",
        "password=changeme",
        "rabbitmq:rabbitmq@",
    },
    "RABBITMQ_DEFAULT_PASS": {
        "guest",
        "changeme",
        "YOUR_SECRET",
    },
    "RAZORPAY_KEY_SECRET": {
        "rzp_test_replace",
        "changeme",
        "YOUR_SECRET",
    },
}

# Keys that must be non-empty when --require-prod-keys is passed (OWNER gate).
PROD_REQUIRED = (
    "SECRET_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "RAZORPAY_KEY_SECRET",
)


def _load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--env-file", type=Path, default=None)
    ap.add_argument(
        "--require-prod-keys",
        action="store_true",
        help="Also fail if core prod secrets are unset (OWNER deploy gate).",
    )
    args = ap.parse_args()

    env = dict(os.environ)
    if args.env_file:
        env.update(_load_env_file(args.env_file))

    hits: list[str] = []
    for key, needles in KNOWN_BAD.items():
        val = env.get(key) or ""
        if not val:
            continue
        low = val.lower()
        for n in needles:
            if n.lower() in low:
                hits.append(f"{key} still matches known-bad pattern {n!r}")
                break

    if args.require_prod_keys:
        for key in PROD_REQUIRED:
            # SECRET_KEY may live as DJANGO_SECRET_KEY depending on settings.
            if key == "SECRET_KEY" and (env.get("SECRET_KEY") or env.get("DJANGO_SECRET_KEY")):
                continue
            if not (env.get(key) or "").strip():
                hits.append(f"{key} is unset (required for production)")

    if hits:
        print("SECRET ROTATION CHECK FAILED:", file=sys.stderr)
        for h in hits:
            # Key names + pattern labels only — never echo secret values.
            print(f"  - {h}", file=sys.stderr)
        print(
            "Rotate via Vault (docs/ops/SECRETS_ROTATION.md / production.yml "
            "rotate_secrets → persist secret/fixitlab/env). Never commit or log values.",
            file=sys.stderr,
        )
        return 1

    print("secret rotation check: no known-bad patterns (values not printed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
