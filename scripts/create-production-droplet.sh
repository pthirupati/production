#!/usr/bin/env bash
# Create FixitLab production droplet on DigitalOcean using doctl.
#
# Prerequisites:
#   brew install doctl          # macOS
#   deploy/production.env       # with DO_API_TOKEN, DO_REGION, DO_SIZE
#   ~/.ssh/id_ed25519.pub       # SSH public key (or set SSH_PUBKEY_FILE)
#
# Usage:
#   ./scripts/create-production-droplet.sh
#   ./scripts/create-production-droplet.sh --no-bootstrap
#   ./scripts/create-production-droplet.sh --sync-only   # droplet exists — update env + commit metadata
#   ./scripts/create-production-droplet.sh --no-commit   # skip git commit
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/deploy/production.env}"
DROPLET_NAME="${DROPLET_NAME:-fixitlab-prod}"
IMAGE="${DO_IMAGE:-ubuntu-22-04-x64}"
SSH_PUBKEY_FILE="${SSH_PUBKEY_FILE:-$HOME/.ssh/id_ed25519.pub}"
RUN_BOOTSTRAP=1
SYNC_ONLY=0
DO_COMMIT=1
PUSH_SECRETS=1

for arg in "$@"; do
  case "$arg" in
    --no-bootstrap) RUN_BOOTSTRAP=0 ;;
    --sync-only) SYNC_ONLY=1 ;;
    --no-commit) DO_COMMIT=0 ;;
    --no-push-secrets) PUSH_SECRETS=0 ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
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

DO_API_TOKEN="$(read_env DO_API_TOKEN)"
DO_REGION="$(read_env DO_REGION blr1)"
DO_SIZE="$(read_env DO_SIZE s-2vcpu-8gb-160gb-intel)"

# DO renamed slugs — map legacy names to current ones (region-specific).
resolve_do_size() {
  local size="$1" region="$2"
  case "$size" in
    s-2vcpu-8gb) size="s-2vcpu-8gb-160gb-intel" ;;
    s-1vcpu-1gb) size="s-1vcpu-1gb-intel" ;;
  esac
  if ! command -v python3 >/dev/null 2>&1; then
    echo "$size"
    return
  fi
  python3 - "$size" "$region" "$DO_API_TOKEN" <<'PY'
import json, sys, urllib.request
size, region, token = sys.argv[1:4]
req = urllib.request.Request(
    "https://api.digitalocean.com/v2/sizes?per_page=200",
    headers={"Authorization": f"Bearer {token}"},
)
with urllib.request.urlopen(req, timeout=30) as resp:
    sizes = json.load(resp).get("sizes", [])
by_slug = {s["slug"]: s for s in sizes}
if size in by_slug and region in by_slug[size].get("regions", []) and by_slug[size].get("available"):
    print(size)
    sys.exit(0)
# Same vCPU/RAM in region
want = by_slug.get(size)
if want:
    vcpus, mem = want["vcpus"], want["memory"]
else:
    vcpus, mem = 2, 8192
for s in sizes:
    if region in s.get("regions", []) and s.get("available") and s["vcpus"] == vcpus and s["memory"] == mem:
        print(s["slug"])
        sys.exit(0)
print(size, file=sys.stderr)
sys.exit(1)
PY
}

DO_SIZE="$(resolve_do_size "$DO_SIZE" "$DO_REGION" 2>/dev/null)" || {
  echo "Invalid DO_SIZE for region $DO_REGION."
  echo "Pick one available in $DO_REGION, e.g.:"
  echo "  doctl compute size list -o json | jq -r '.[] | select(.regions[]==\"$DO_REGION\" and .available) | .slug'"
  echo ""
  echo "For 2 vCPU / 8 GB in blr1 use: s-2vcpu-8gb-160gb-intel"
  exit 1
}

if ! command -v doctl >/dev/null 2>&1; then
  echo "doctl not found. Install it:"
  echo "  macOS:  brew install doctl"
  echo "  Linux:  https://docs.digitalocean.com/reference/doctl/how-to/install/"
  exit 1
fi

if [ -z "$DO_API_TOKEN" ]; then
  echo "Missing DO_API_TOKEN in $ENV_FILE (or export DIGITALOCEAN_ACCESS_TOKEN)"
  exit 1
fi

export DIGITALOCEAN_ACCESS_TOKEN="$DO_API_TOKEN"
doctl auth init -t "$DO_API_TOKEN" >/dev/null 2>&1 || true

if [ ! -f "$SSH_PUBKEY_FILE" ]; then
  echo "SSH public key not found: $SSH_PUBKEY_FILE"
  echo "Generate one:  ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519"
  exit 1
fi

echo "=== FixitLab production droplet (doctl) ==="
echo "  name:   $DROPLET_NAME"
echo "  region: $DO_REGION"
echo "  size:   $DO_SIZE"
echo "  image:  $IMAGE"
echo ""

# Reuse or import SSH key in DO account
SSH_KEY_NAME="fixitlab-prod-$(whoami)"
FINGERPRINT="$(ssh-keygen -lf "$SSH_PUBKEY_FILE" -E md5 | awk '{print $2}' | sed 's/MD5://')"
EXISTING_ID="$(doctl compute ssh-key list --format ID,FingerPrint --no-header 2>/dev/null | awk -v fp="$FINGERPRINT" '$2==fp {print $1; exit}')"

if [ -n "$EXISTING_ID" ]; then
  SSH_KEY_ID="$EXISTING_ID"
  echo "Using existing DO SSH key id=$SSH_KEY_ID"
else
  echo "Importing SSH key to DigitalOcean..."
  doctl compute ssh-key import "$SSH_KEY_NAME" --public-key-file "$SSH_PUBKEY_FILE"
  SSH_KEY_ID="$(doctl compute ssh-key list --format ID,Name --no-header | awk -v n="$SSH_KEY_NAME" '$2==n {print $1; exit}')"
fi

if [ -z "$SSH_KEY_ID" ]; then
  echo "Could not resolve SSH key id in DO account"
  exit 1
fi

if doctl compute droplet list --format Name --no-header | grep -qx "$DROPLET_NAME"; then
  if [ "$SYNC_ONLY" -eq 1 ]; then
    echo "Droplet '$DROPLET_NAME' exists — syncing host metadata..."
    SYNC_ARGS=(--from-doctl "$DROPLET_NAME")
    [ "$DO_COMMIT" -eq 1 ] && SYNC_ARGS+=(--commit)
    [ "$PUSH_SECRETS" -eq 1 ] && SYNC_ARGS+=(--push-secrets)
    exec "$ROOT/scripts/update-production-host.sh" "${SYNC_ARGS[@]}"
  fi
  echo "Droplet '$DROPLET_NAME' already exists:"
  doctl compute droplet list --format ID,Name,PublicIPv4,Status,Region --no-header | grep "$DROPLET_NAME" || true
  echo ""
  echo "Sync env + commit metadata (no new droplet):"
  echo "  ./scripts/create-production-droplet.sh --sync-only"
  exit 1
fi

CREATE_ARGS=(
  "$DROPLET_NAME"
  --region "$DO_REGION"
  --size "$DO_SIZE"
  --image "$IMAGE"
  --ssh-keys "$SSH_KEY_ID"
  --tag-names fixitlab,production,fixitlab-prod
  --enable-monitoring
  --enable-ipv6
  --wait
)

if [ "$RUN_BOOTSTRAP" -eq 1 ] && [ -f "$ROOT/infra/digitalocean/bootstrap-platform.sh" ]; then
  echo "Cloud-init: running bootstrap-platform.sh on first boot"
  CREATE_ARGS+=(--user-data-file "$ROOT/infra/digitalocean/bootstrap-platform.sh")
fi

echo "Creating droplet (this takes 1–3 minutes)..."
doctl compute droplet create "${CREATE_ARGS[@]}"

DROPLET_ID="$(doctl compute droplet list --format ID,Name --no-header | awk -v n="$DROPLET_NAME" '$2==n {print $1; exit}')"
PUBLIC_IP="$(doctl compute droplet get "$DROPLET_ID" --format PublicIPv4 --no-header)"

echo ""
echo "=== Droplet ready ==="
echo "  id:  $DROPLET_ID"
echo "  ip:  $PUBLIC_IP"
echo "  ssh: ssh root@${PUBLIC_IP}"
echo ""

SYNC_ARGS=("$PUBLIC_IP" "$DROPLET_ID")
[ "$DO_COMMIT" -eq 1 ] && SYNC_ARGS+=(--commit)
[ "$PUSH_SECRETS" -eq 1 ] && SYNC_ARGS+=(--push-secrets)
"$ROOT/scripts/update-production-host.sh" "${SYNC_ARGS[@]}"

echo ""
echo "Next steps:"
echo "  1. Wait ~2 min for cloud-init bootstrap, then: ssh root@${PUBLIC_IP}"
echo "  2. Deploy: ./scripts/upload-env-production.sh && git push origin main"
echo "  3. DNS: point fixitlab.in → ${PUBLIC_IP}"
