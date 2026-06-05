#!/usr/bin/env bash
# Update GitHub Environment secrets + repo metadata after droplet create (CI only).
#
# Usage:
#   PUBLIC_IP=... DROPLET_ID=... SSH_KEY_ID=... ./scripts/ci-sync-droplet-secrets.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PUBLIC_IP="${PUBLIC_IP:?PUBLIC_IP required}"
DROPLET_ID="${DROPLET_ID:?DROPLET_ID required}"
SSH_KEY_ID="${SSH_KEY_ID:-}"
REPO="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY required}"
ENV_NAME="${GITHUB_ENVIRONMENT:-production}"

if [ -z "${PRODUCTION_ENV_B64:-}" ]; then
  echo "ERROR: PRODUCTION_ENV_B64 secret required"
  exit 1
fi

TMP_ENV="$(mktemp)"
trap 'rm -f "$TMP_ENV"' EXIT
echo "$PRODUCTION_ENV_B64" | base64 -d > "$TMP_ENV"
chmod 600 "$TMP_ENV"

python3 - "$TMP_ENV" "$PUBLIC_IP" "$DROPLET_ID" "$SSH_KEY_ID" <<'PY'
import re, sys
from pathlib import Path
path, ip, droplet_id, ssh_key_id = sys.argv[1:5]
lines = Path(path).read_text().splitlines()

def set_key(key, value):
    global lines
    pat = re.compile(rf"^{re.escape(key)}=")
    out, found = [], False
    for line in lines:
        if pat.match(line):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    lines = out

def merge_allowed_hosts(ip):
    global lines
    domains = ["fixitlab.in", "www.fixitlab.in", "localhost", "127.0.0.1", ip]
    seen = set()
    ordered = []
    for d in domains:
        if d not in seen:
            seen.add(d)
            ordered.append(d)
    for line in lines:
        if line.startswith("DJANGO_ALLOWED_HOSTS="):
            for part in line.split("=", 1)[1].split(","):
                part = part.strip()
                if not part or (re.match(r"^\d+\.\d+\.\d+\.\d+$", part) and part != ip):
                    continue
                if part not in seen:
                    seen.add(part)
                    ordered.append(part)
            break
    set_key("DJANGO_ALLOWED_HOSTS", ",".join(ordered))

set_key("PROD_HOST", ip)
set_key("PROD_USER", "root")
set_key("DO_PROTECTED_DROPLET_IDS", droplet_id)
set_key("DO_PROTECTED_DROPLET_NAMES", "fixitlab-prod")
if ssh_key_id:
    set_key("DO_SSH_KEY_ID", ssh_key_id)
merge_allowed_hosts(ip)
Path(path).write_text("\n".join(lines) + "\n")
PY

NEW_B64="$(base64 < "$TMP_ENV" | tr -d '\n')"

echo "Updating GitHub Environment secrets ($ENV_NAME)..."
if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh CLI required"
  exit 1
fi

gh api "repos/${REPO}/environments/${ENV_NAME}" -X PUT -f wait_timer=0 >/dev/null 2>&1 || true

printf '%s' "$PUBLIC_IP" | gh secret set PROD_HOST --env "$ENV_NAME" --repo "$REPO"
echo "  ✓ PROD_HOST=$PUBLIC_IP"

printf '%s' "$NEW_B64" | gh secret set PRODUCTION_ENV_B64 --env "$ENV_NAME" --repo "$REPO"
echo "  ✓ PRODUCTION_ENV_B64 (PROD_HOST + DJANGO_ALLOWED_HOSTS updated)"

# Update tracked metadata in repo (no secrets)
META="$ROOT/infra/digitalocean/production.json"
mkdir -p "$(dirname "$META")"
python3 - "$META" "$PUBLIC_IP" "$DROPLET_ID" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
path, ip, did = sys.argv[1:4]
data = {
    "droplet_name": "fixitlab-prod",
    "droplet_id": str(did),
    "public_ipv4": ip,
    "region": "blr1",
    "domain": "fixitlab.in",
    "ssh_user": "root",
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
Path(path).write_text(json.dumps(data, indent=2) + "\n")
PY

# Export for same-workflow deploy job
if [ -n "${GITHUB_ENV:-}" ]; then
  echo "PROD_HOST=$PUBLIC_IP" >> "$GITHUB_ENV"
  echo "PRODUCTION_ENV_B64=$NEW_B64" >> "$GITHUB_ENV"
fi

echo "ci_prod_host=$PUBLIC_IP"
if [ -n "${GITHUB_OUTPUT:-}" ]; then
  echo "prod_host=$PUBLIC_IP" >> "$GITHUB_OUTPUT"
fi
