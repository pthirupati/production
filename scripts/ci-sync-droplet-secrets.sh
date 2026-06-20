#!/usr/bin/env bash
# Update GitHub Environment secrets + repo metadata after droplet create (CI only).
#
# Usage:
#   PUBLIC_IP=... DROPLET_ID=... SSH_KEY_ID=... ./scripts/ci-sync-droplet-secrets.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# ──────────────────────────────────────────────────────────────────────────
# CLUSTER_MODE=1 — four-droplet topology. Sets cluster GitHub secrets + commits
# infra/digitalocean/cluster.json (no secrets). Single-droplet path below is
# left completely unchanged and is used when CLUSTER_MODE is unset.
# ──────────────────────────────────────────────────────────────────────────
if [ "${CLUSTER_MODE:-0}" = "1" ]; then
  REPO="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY required}"
  ENV_NAME="${GITHUB_ENVIRONMENT:-production}"
  : "${EDGE_PUBLIC_IP:?EDGE_PUBLIC_IP required}"
  : "${APP_PRIVATE_IP:?APP_PRIVATE_IP required}"
  : "${DATA_PRIVATE_IP:?DATA_PRIVATE_IP required}"
  : "${LABS_PRIVATE_IP:?LABS_PRIVATE_IP required}"
  DRY_RUN="${DRY_RUN:-0}"

  _is_true() { case "${1:-}" in 1|true|TRUE|yes|on) return 0;; *) return 1;; esac; }

  gh_secret() {
    # gh_secret NAME VALUE  (masked; printed-only in DRY_RUN)
    local name="$1" val="$2"
    [ -z "$val" ] && return 0
    [ -n "${GITHUB_ACTIONS:-}" ] && echo "::add-mask::${val}"
    if _is_true "$DRY_RUN"; then
      echo "DRY_RUN gh secret set ${name} --env ${ENV_NAME} --repo ${REPO}  (value masked)"
      return 0
    fi
    printf '%s' "$val" | gh secret set "$name" --env "$ENV_NAME" --repo "$REPO"
    echo "  set ${name}"
  }

  echo "=== cluster secret sync (dry_run=${DRY_RUN}) ==="
  # Edge public IP is the canonical PROD_HOST (gateway lives on D1).
  gh_secret PROD_HOST "$EDGE_PUBLIC_IP"
  gh_secret PROD_EDGE_HOST "$EDGE_PUBLIC_IP"
  gh_secret PROD_APP_HOST "$APP_PRIVATE_IP"
  gh_secret PROD_DB_HOST "$DATA_PRIVATE_IP"
  gh_secret PROD_LABS_HOST "$LABS_PRIVATE_IP"
  [ -n "${EDGE_PRIVATE_IP:-}" ] && gh_secret PROD_EDGE_PRIVATE_HOST "$EDGE_PRIVATE_IP"

  # Vault AppRole secrets captured by ci-vault-cluster-bootstrap.sh
  gh_secret VAULT_ROLE_ID "${VAULT_ROLE_ID:-}"
  gh_secret VAULT_SECRET_ID "${VAULT_SECRET_ID:-}"
  gh_secret VAULT_UNSEAL_KEY "${VAULT_UNSEAL_KEY:-}"
  [ -n "${VAULT_ENABLED:-}" ] && gh_secret VAULT_ENABLED "${VAULT_ENABLED}"

  # Rotated full env (base64) — only when provided by generate-secrets step.
  if [ -n "${CLUSTER_ENV_B64:-}" ]; then
    gh_secret PRODUCTION_ENV_B64 "$CLUSTER_ENV_B64"
  fi

  # Point fixitlab.in DNS at the edge (D1) public IP — automatic when GoDaddy keys
  # are present (rotated env or GODADDY_* env); otherwise update the A record manually.
  if [ -n "${EDGE_PUBLIC_IP:-}" ] && [ -x "$ROOT/scripts/update-godaddy-dns.sh" ]; then
    if [ -z "${GODADDY_API_KEY:-}" ] && [ -n "${CLUSTER_ENV_B64:-}" ]; then
      _cenv="$(echo "$CLUSTER_ENV_B64" | base64 -d 2>/dev/null || true)"
      export GODADDY_API_KEY="$(printf '%s' "$_cenv" | grep '^GODADDY_API_KEY=' | cut -d= -f2- | tr -d '\r')"
      export GODADDY_API_SECRET="$(printf '%s' "$_cenv" | grep '^GODADDY_API_SECRET=' | cut -d= -f2- | tr -d '\r')"
    fi
    if [ "${DRY_RUN:-0}" = "1" ]; then
      echo "DRY_RUN update-godaddy-dns.sh $EDGE_PUBLIC_IP  (point fixitlab.in A record at edge)"
    elif [ -n "${GODADDY_API_KEY:-}" ]; then
      "$ROOT/scripts/update-godaddy-dns.sh" "$EDGE_PUBLIC_IP" \
        || echo "WARN: GoDaddy DNS update failed — set the fixitlab.in A record to $EDGE_PUBLIC_IP manually"
    else
      echo "NOTE: GoDaddy API keys not present — set the fixitlab.in A record to $EDGE_PUBLIC_IP manually"
    fi
  fi

  # Update committed metadata (no secrets).
  META="$ROOT/infra/digitalocean/cluster.json"
  mkdir -p "$(dirname "$META")"
  python3 - "$META" <<PY
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
path = sys.argv[1]
data = json.loads(Path(path).read_text()) if Path(path).exists() else {}
data.setdefault("topology", "four-droplet")
data["vpc_id"] = os.environ.get("VPC_ID", data.get("vpc_id", ""))
d = data.setdefault("droplets", {})
def upd(role, id_key, pub_key=None):
    node = d.setdefault(role, {})
    node["droplet_id"] = os.environ.get(id_key, node.get("droplet_id", ""))
    node["private_ipv4"] = os.environ.get(role.upper() + "_PRIVATE_IP", node.get("private_ipv4", ""))
    if pub_key:
        node["public_ipv4"] = os.environ.get(pub_key, node.get("public_ipv4", ""))
upd("edge", "EDGE_ID", "EDGE_PUBLIC_IP")
upd("app", "APP_ID")
upd("data", "DATA_ID")
upd("labs", "LABS_ID")
data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
Path(path).write_text(json.dumps(data, indent=2) + "\n")
print(f"[cluster] wrote {path}")
PY

  echo "=== cluster secret sync done ==="
  exit 0
fi

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

# GoDaddy DNS (optional — keys in PRODUCTION_ENV_B64 or GODADDY_* env)
if [ -x "$ROOT/scripts/update-godaddy-dns.sh" ]; then
  export PRODUCTION_ENV_B64="$NEW_B64"
  export ENV_FILE="$TMP_ENV"
  "$ROOT/scripts/update-godaddy-dns.sh" "$PUBLIC_IP" || echo "WARN: GoDaddy DNS update failed or skipped"
fi
