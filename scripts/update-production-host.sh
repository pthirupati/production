#!/usr/bin/env bash
# Sync production droplet IP/ID into local env + tracked metadata (no secrets in git).
#
# Usage:
#   ./scripts/update-production-host.sh 64.227.175.89 575580846
#   ./scripts/update-production-host.sh --from-doctl fixitlab-prod
#   ./scripts/update-production-host.sh --from-doctl fixitlab-prod --commit --push-secrets
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/deploy/production.env}"
META_FILE="$ROOT/infra/digitalocean/production.json"
DROPLET_NAME="${DROPLET_NAME:-fixitlab-prod}"
DO_COMMIT=0
PUSH_SECRETS=0
FROM_DOCTL=""

PUBLIC_IP=""
DROPLET_ID=""
SSH_KEY_ID=""

while [ $# -gt 0 ]; do
  case "$1" in
    --from-doctl)
      FROM_DOCTL="${2:-fixitlab-prod}"
      shift 2
      ;;
    --commit) DO_COMMIT=1; shift ;;
    --push-secrets) PUSH_SECRETS=1; shift ;;
    -h|--help)
      sed -n '2,8p' "$0"
      exit 0
      ;;
    *)
      if [ -z "$PUBLIC_IP" ]; then
        PUBLIC_IP="$1"
      elif [ -z "$DROPLET_ID" ]; then
        DROPLET_ID="$1"
      fi
      shift
      ;;
  esac
done

read_env() {
  local key="$1" default="${2:-}"
  if [ -f "$ENV_FILE" ] && grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    grep "^${key}=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '\r'
  else
    echo "$default"
  fi
}

if [ -n "$FROM_DOCTL" ]; then
  if ! command -v doctl >/dev/null 2>&1; then
    echo "doctl required for --from-doctl"
    exit 1
  fi
  TOKEN="$(read_env DO_API_TOKEN)"
  [ -n "$TOKEN" ] && export DIGITALOCEAN_ACCESS_TOKEN="$TOKEN"
  DROPLET_NAME="$FROM_DOCTL"
  DROPLET_ID="$(doctl compute droplet list --format ID,Name --no-header | awk -v n="$DROPLET_NAME" '$2==n {print $1; exit}')"
  if [ -z "$DROPLET_ID" ]; then
    echo "Droplet not found: $DROPLET_NAME"
    exit 1
  fi
  PUBLIC_IP="$(doctl compute droplet get "$DROPLET_ID" --format PublicIPv4 --no-header)"
fi

if [ -z "$PUBLIC_IP" ] || [ -z "$DROPLET_ID" ]; then
  echo "Usage: $0 <public_ip> <droplet_id> [--commit] [--push-secrets]"
  echo "   or: $0 --from-doctl fixitlab-prod [--commit] [--push-secrets]"
  exit 1
fi

SSH_KEY_ID="$(read_env DO_SSH_KEY_ID)"
DO_REGION="$(read_env DO_REGION blr1)"
DO_SIZE="$(read_env DO_SIZE s-2vcpu-8gb-160gb-intel)"
DOMAIN="$(read_env SITE_URL https://fixitlab.in | sed -E 's|https?://||; s|/.*||')"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE — copy from env.production.example first"
  exit 1
fi

echo "=== Updating production host metadata ==="
echo "  ip:       $PUBLIC_IP"
echo "  droplet:  $DROPLET_ID ($DROPLET_NAME)"
echo ""

python3 - "$ENV_FILE" "$PUBLIC_IP" "$DROPLET_ID" "$SSH_KEY_ID" "$DO_REGION" "$DO_SIZE" <<'PY'
import re, sys
from pathlib import Path

path, ip, droplet_id, ssh_key_id, region, size = sys.argv[1:7]
text = Path(path).read_text()
lines = text.splitlines()

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
    seen, ordered = set(), []
    for d in domains:
        if d not in seen:
            seen.add(d)
            ordered.append(d)
    # Keep any custom entries from existing line (except old IPv4 literals we replace)
    for line in lines:
        if line.startswith("DJANGO_ALLOWED_HOSTS="):
            for part in line.split("=", 1)[1].split(","):
                part = part.strip()
                if not part:
                    continue
                if re.match(r"^\d+\.\d+\.\d+\.\d+$", part) and part != ip:
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
set_key("DO_REGION", region)
set_key("DO_SIZE", size)
merge_allowed_hosts(ip)

# Update header comment line if present
for i, line in enumerate(lines):
    if line.startswith("#  Server:"):
        lines[i] = f"#  Server: {ip} ({Path(path).stem}, {region.upper()}) | Domain: fixitlab.in"
        break

Path(path).write_text("\n".join(lines) + "\n")
print(f"  ✓ {path}")
PY

# Mirror to .env.production if present or create from deploy copy
LOCAL_PROD="$ROOT/.env.production"
cp "$ENV_FILE" "$LOCAL_PROD"
chmod 600 "$LOCAL_PROD" "$ENV_FILE"
echo "  ✓ $LOCAL_PROD"

mkdir -p "$(dirname "$META_FILE")"
python3 - "$META_FILE" "$DROPLET_NAME" "$DROPLET_ID" "$PUBLIC_IP" "$DO_REGION" "$DO_SIZE" "$DOMAIN" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path

path, name, did, ip, region, size, domain = sys.argv[1:8]
data = {
    "droplet_name": name,
    "droplet_id": str(did),
    "public_ipv4": ip,
    "region": region,
    "size": size,
    "domain": domain,
    "ssh_user": "root",
    "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
Path(path).write_text(json.dumps(data, indent=2) + "\n")
print(f"  ✓ {path}")
PY

# Update docs/examples that reference PROD_HOST placeholder (no secrets)
for doc in "$ROOT/env.production.example" "$ROOT/docs/PUSH_AND_RUN.md" "$ROOT/docs/GITHUB_SECRETS.md" "$ROOT/docs/DNS_AND_SSL.md"; do
  [ -f "$doc" ] || continue
  if grep -q 'PROD_HOST=\|139\.59\.58\.8\|150\.136\.13\.58\|165\.22\.211\.41' "$doc" 2>/dev/null; then
    sed -i '' \
      -e "s/PROD_HOST=[0-9.]*/PROD_HOST=${PUBLIC_IP}/g" \
      -e "s/\`139\.59\.58\.8\`/\`${PUBLIC_IP}\`/g" \
      -e "s/139\.59\.58\.8/${PUBLIC_IP}/g" \
      -e "s/150\.136\.13\.58/${PUBLIC_IP}/g" \
      -e "s/165\.22\.211\.41/${PUBLIC_IP}/g" \
      "$doc" 2>/dev/null || sed -i \
      -e "s/PROD_HOST=[0-9.]*/PROD_HOST=${PUBLIC_IP}/g" \
      -e "s/139\.59\.58\.8/${PUBLIC_IP}/g" \
      "$doc"
    echo "  ✓ $doc"
  fi
done

# Fix upload-env-production.sh default fallback IP
UPLOAD="$ROOT/scripts/upload-env-production.sh"
if [ -f "$UPLOAD" ]; then
  sed -i '' "s/PROD_HOST=\"\${PROD_HOST:-[0-9.]*}\"/PROD_HOST=\"\${PROD_HOST:-${PUBLIC_IP}}\"/" "$UPLOAD" 2>/dev/null || \
  sed -i "s/PROD_HOST=\"\${PROD_HOST:-[0-9.]*}\"/PROD_HOST=\"\${PROD_HOST:-${PUBLIC_IP}}\"/" "$UPLOAD"
  echo "  ✓ $UPLOAD"
fi

if [ "$PUSH_SECRETS" -eq 1 ]; then
  echo ""
  echo "Uploading GitHub secrets..."
  if [ -x "$ROOT/scripts/upload-secrets-to-github.sh" ]; then
    "$ROOT/scripts/upload-secrets-to-github.sh" || echo "  (GitHub upload skipped — run: gh auth login && ./scripts/upload-secrets-to-github.sh)"
  fi
fi

if [ "$DO_COMMIT" -eq 1 ]; then
  echo ""
  echo "Committing non-secret metadata..."
  cd "$ROOT"
  git add infra/digitalocean/production.json env.production.example docs/PUSH_AND_RUN.md docs/GITHUB_SECRETS.md docs/DNS_AND_SSL.md scripts/upload-env-production.sh scripts/update-production-host.sh scripts/create-production-droplet.sh 2>/dev/null || true
  if git diff --cached --quiet; then
    echo "  (nothing to commit)"
  else
    git commit -m "$(cat <<EOF
Update production host metadata after droplet sync.

Droplet ${DROPLET_NAME} (${DROPLET_ID}) at ${PUBLIC_IP}. Secrets stay in deploy/production.env and GitHub PRODUCTION_ENV_B64 only.
EOF
)"
    echo "  ✓ git commit created — run: git push origin main"
  fi
fi

if [ -x "$ROOT/scripts/update-godaddy-dns.sh" ]; then
  echo ""
  "$ROOT/scripts/update-godaddy-dns.sh" "$PUBLIC_IP" || echo "  (GoDaddy DNS skipped — add GODADDY_API_KEY/SECRET to deploy/production.env)"
fi

echo ""
echo "Done. deploy/production.env updated (gitignored — not committed)."
echo "  ssh root@${PUBLIC_IP}"
echo "  ./scripts/upload-env-production.sh"
if [ "$DO_COMMIT" -eq 0 ]; then
  echo "  $0 --from-doctl ${DROPLET_NAME} --commit --push-secrets   # commit metadata + GitHub secrets"
fi
