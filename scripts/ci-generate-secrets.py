#!/usr/bin/env python3
"""
Generate / rotate FixitLab production secrets for the four-droplet cluster.

Reads the existing production env template (base64 in PRODUCTION_ENV_B64, or a
file path argument), ROTATES only the infrastructure secrets we own, REBUILDS the
Celery broker / result-backend URLs to match, and PRESERVES everything else
(OAuth, payment, Jira, GoDaddy, email, business config).

NEVER touches DO_API_TOKEN or PROD_SSH_KEY (those are managed out-of-band and
must never be rotated by this automation).

Rotated keys:
    DJANGO_SECRET_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD, RABBITMQ_PASS,
    SUPERUSER_PASSWORD (>=24 chars), JWT_HS256_SECRET, JIRA_WEBHOOK_SECRET,
    RAZORPAY_WEBHOOK_SECRET (only if already present in the template)

Rebuilt (derived) keys:
    CELERY_BROKER_URL          = amqp://<user>:<RABBITMQ_PASS>@<rabbit-host>:5672//
    CELERY_RESULT_BACKEND      = redis://:<REDIS_PASSWORD>@<redis-host>:6379/2

Usage:
    # From PRODUCTION_ENV_B64 (CI) — writes rotated env to OUT_FILE (default .env.cluster)
    PRODUCTION_ENV_B64="$B64" ROTATE_SECRETS=1 python3 scripts/ci-generate-secrets.py

    # From a file
    python3 scripts/ci-generate-secrets.py --in deploy/production.env --out .env.cluster

    # Emit a base64 of the result on stdout for the next GH step (masked in DRY_RUN)
    python3 scripts/ci-generate-secrets.py --print-b64

Environment:
    PRODUCTION_ENV_B64   base64 of the source env (used when --in is omitted)
    ROTATE_SECRETS=1     rotate the secrets above (default: 1). When 0, only
                         missing/placeholder secrets are filled, existing kept.
    DRY_RUN=1            print MASKED values + the actions taken; do not reveal
                         any real generated secret. Still writes the env file so
                         downstream dry-run steps have something to read, but the
                         summary/stdout is masked and ::add-mask:: lines are
                         emitted for GitHub Actions.

Outputs (when GITHUB_OUTPUT set): out_file, rotated_keys (comma list)
"""
from __future__ import annotations

import argparse
import base64
import os
import re
import secrets
import string
import sys
from pathlib import Path

# Secrets we generate/rotate. Keys NOT in here are preserved verbatim.
ROTATE_KEYS = [
    "POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
    "RABBITMQ_PASS",
    "SUPERUSER_PASSWORD",
    "JIRA_WEBHOOK_SECRET",
]
# Signing/identity keys: generated ONCE when missing and NEVER rotated on a
# routine OR a rotate_secrets deploy. Rotating DJANGO_SECRET_KEY invalidates every
# Django session + outstanding password-reset token; rotating JWT_HS256_SECRET
# invalidates every issued JWT — either causes a platform-wide forced logout that
# looks exactly like the recurring "logged out + invalid credentials" report.
# Only a deliberate, explicit key-roll (ROTATE_SIGNING_KEYS=1) regenerates them.
SIGNING_KEYS = ["DJANGO_SECRET_KEY", "JWT_HS256_SECRET"]
ROTATE_SIGNING_KEYS = os.environ.get("ROTATE_SIGNING_KEYS", "0") == "1"
# Rotated only if already present (we never introduce a Razorpay secret).
ROTATE_IF_PRESENT = ["RAZORPAY_WEBHOOK_SECRET"]

# NEVER rotate or print these — managed out of band.
PROTECTED_KEYS = {"DO_API_TOKEN", "PROD_SSH_KEY", "DO_SSH_KEY_PEM"}

# Treated as "not really set" — safe to (re)generate even when ROTATE_SECRETS=0.
PLACEHOLDER_RE = re.compile(r"CHANGE-ME|your-|xxxxx|rzp_test_your", re.IGNORECASE)

_ALNUM = string.ascii_letters + string.digits
# URL/shell-safe punctuation only (no @ : / # that would break URLs or env parsing)
_SAFE_PUNCT = "._-~"


def _is_truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in {"1", "true", "yes", "on"}


def gen_token(length: int = 48, punct: bool = False) -> str:
    alphabet = _ALNUM + (_SAFE_PUNCT if punct else "")
    return "".join(secrets.choice(alphabet) for _ in range(length))


def gen_django_secret_key() -> str:
    # 50 chars of entropy. Use ONLY env/compose-safe characters — a '$' (or '{')
    # in the value makes `docker compose --env-file` try to interpolate it
    # ("variable eg6 is not set"), corrupting the secret. Charset doesn't affect
    # key strength.
    chars = _ALNUM + _SAFE_PUNCT
    return "".join(secrets.choice(chars) for _ in range(50))


def parse_env(text: str) -> list[tuple[str, str | None, str]]:
    """Return ordered list of (key, value, raw_line). Comments/blanks: key=None."""
    rows: list[tuple[str, str | None, str]] = []
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            rows.append(("", None, line))
            continue
        key, _, value = stripped.partition("=")
        rows.append((key.strip(), value, line))
    return rows


def get_val(rows: list[tuple[str, str | None, str]], key: str) -> str | None:
    for k, v, _ in rows:
        if k == key:
            return v
    return None


def set_val(rows: list[tuple[str, str | None, str]], key: str, value: str) -> None:
    for i, (k, _v, raw) in enumerate(rows):
        if k == key:
            rows[i] = (key, value, f"{key}={value}")
            return
    rows.append((key, value, f"{key}={value}"))


def host_from(value: str | None, default: str) -> str:
    """Best-effort host extraction from an existing broker URL, else default."""
    if not value:
        return default
    m = re.search(r"@([^:/?#]+)", value)
    if m:
        return m.group(1)
    return default


def mask(value: str) -> str:
    if not value:
        return "(empty)"
    if len(value) <= 8:
        return "****"
    return f"{value[:3]}…{value[-2:]} (len={len(value)})"


def gh_mask(value: str) -> None:
    """Emit a GitHub Actions mask so the value never appears in logs."""
    if value and os.environ.get("GITHUB_ACTIONS"):
        # ::add-mask:: must be on its own line, unquoted.
        print(f"::add-mask::{value}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate/rotate FixitLab cluster secrets")
    ap.add_argument("--in", dest="infile", default=None, help="source env file")
    ap.add_argument("--out", dest="outfile", default=os.environ.get("OUT_FILE", ".env.cluster"))
    ap.add_argument("--print-b64", action="store_true", help="print base64 of result on stdout")
    args = ap.parse_args()

    dry_run = _is_truthy(os.environ.get("DRY_RUN"))
    rotate = _is_truthy(os.environ.get("ROTATE_SECRETS", "1"))

    # ── Load source env ──
    if args.infile:
        src_text = Path(args.infile).read_text(encoding="utf-8")
    elif os.environ.get("PRODUCTION_ENV_B64"):
        src_text = base64.b64decode(os.environ["PRODUCTION_ENV_B64"]).decode("utf-8")
    else:
        print("ERROR: provide --in FILE or set PRODUCTION_ENV_B64", file=sys.stderr)
        return 2

    rows = parse_env(src_text)
    rotated: list[str] = []

    def should_set(key: str) -> bool:
        if key in PROTECTED_KEYS:
            return False
        cur = get_val(rows, key)
        missing = cur is None or cur == "" or bool(PLACEHOLDER_RE.search(cur or ""))
        return rotate or missing

    # ── Rotate / fill secrets ──
    new_secrets: dict[str, str] = {}
    for key in ROTATE_KEYS:
        if not should_set(key):
            continue
        if key == "DJANGO_SECRET_KEY":
            val = gen_django_secret_key()
        elif key == "SUPERUSER_PASSWORD":
            # >= 24 chars per spec; include safe punctuation for strength
            val = gen_token(28, punct=True)
        elif key == "JWT_HS256_SECRET":
            val = gen_token(64)
        else:
            # passwords used inside URLs — keep them alnum to avoid URL-encoding
            val = gen_token(40)
        new_secrets[key] = val

    # Signing keys: generate only when genuinely absent (preserve across every
    # deploy, including rotate_secrets=true) unless an explicit ROTATE_SIGNING_KEYS=1
    # deliberate roll is requested. This is what keeps users logged in across deploys.
    for key in SIGNING_KEYS:
        if key in PROTECTED_KEYS:
            continue
        cur = get_val(rows, key)
        missing = cur is None or cur == "" or bool(PLACEHOLDER_RE.search(cur or ""))
        if not (missing or ROTATE_SIGNING_KEYS):
            continue
        new_secrets[key] = gen_django_secret_key() if key == "DJANGO_SECRET_KEY" else gen_token(64)

    for key in ROTATE_IF_PRESENT:
        cur = get_val(rows, key)
        if cur is None:
            continue  # never introduce
        if rotate or PLACEHOLDER_RE.search(cur or "") or cur == "":
            new_secrets[key] = gen_token(40)

    for key, val in new_secrets.items():
        gh_mask(val)
        set_val(rows, key, val)
        rotated.append(key)

    # ── Rebuild derived broker / result-backend URLs ──
    rabbit_user = get_val(rows, "RABBITMQ_USER") or "fixitlab"
    rabbit_pass = get_val(rows, "RABBITMQ_PASS") or ""
    redis_pass = get_val(rows, "REDIS_PASSWORD") or ""
    rabbit_host = host_from(get_val(rows, "CELERY_BROKER_URL"), "rabbitmq")
    redis_host = host_from(get_val(rows, "CELERY_RESULT_BACKEND"), "redis")

    if rabbit_pass:
        broker = f"amqp://{rabbit_user}:{rabbit_pass}@{rabbit_host}:5672//"
        gh_mask(broker)
        set_val(rows, "CELERY_BROKER_URL", broker)
        rotated.append("CELERY_BROKER_URL")
    if redis_pass:
        backend = f"redis://:{redis_pass}@{redis_host}:6379/2"
        gh_mask(backend)
        set_val(rows, "CELERY_RESULT_BACKEND", backend)
        rotated.append("CELERY_RESULT_BACKEND")

    # Confirm protected keys were untouched (defensive).
    for key in PROTECTED_KEYS:
        if key in rotated:
            print(f"ERROR: refused to rotate protected key {key}", file=sys.stderr)
            return 3

    out_text = "\n".join(r[2] for r in rows).rstrip("\n") + "\n"

    # ── Write env file (chmod 600). In DRY_RUN we still write so downstream
    #    dry-run steps have a file, but we never print real values. ──
    out_path = Path(args.outfile)
    out_path.write_text(out_text, encoding="utf-8")
    os.chmod(out_path, 0o600)

    # ── Report ──
    print(f"[generate-secrets] source: {'PRODUCTION_ENV_B64' if not args.infile else args.infile}")
    print(f"[generate-secrets] rotate_secrets={rotate} dry_run={dry_run}")
    print(f"[generate-secrets] wrote {out_path} ({len(rows)} lines, mode 600)")
    print(f"[generate-secrets] rotated keys ({len(rotated)}): {', '.join(rotated) or '(none)'}")
    print("[generate-secrets] preserved (not rotated): OAuth, payment, Jira config, "
          "GoDaddy, email, business details, DO_API_TOKEN, PROD_SSH_KEY")
    if dry_run:
        print("[generate-secrets] DRY_RUN — masked values:")
        for key in rotated:
            print(f"    {key} = {mask(get_val(rows, key) or '')}")

    if args.print_b64:
        b64 = base64.b64encode(out_text.encode("utf-8")).decode("ascii")
        gh_mask(b64)
        if dry_run:
            print(f"[generate-secrets] DRY_RUN — base64 of env: {mask(b64)}")
        else:
            print(b64)

    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"out_file={out_path}\n")
            fh.write(f"rotated_keys={','.join(rotated)}\n")
            # Boolean flag (true iff any secret was actually rotated) so the
            # workflow can drive the credentials-email sync-status note.
            fh.write(f"rotated={'true' if rotated else 'false'}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
