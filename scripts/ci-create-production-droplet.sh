#!/usr/bin/env bash
# Create fixitlab-prod droplet in GitHub Actions (non-interactive).
# Requires: DIGITALOCEAN_ACCESS_TOKEN or DO_API_TOKEN, PROD_SSH_KEY (private key for root SSH)
#
# Outputs (GITHUB_OUTPUT if set):
#   droplet_id, public_ip, ssh_key_id
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DROPLET_NAME="${DROPLET_NAME:-fixitlab-prod}"
DO_REGION="${DO_REGION:-blr1}"
DO_SIZE="${DO_SIZE:-s-2vcpu-8gb-160gb-intel}"
IMAGE="${DO_IMAGE:-ubuntu-22-04-x64}"

if [ -z "${DIGITALOCEAN_ACCESS_TOKEN:-}" ] && [ -n "${DO_API_TOKEN:-}" ]; then
  export DIGITALOCEAN_ACCESS_TOKEN="$DO_API_TOKEN"
fi
if [ -z "${DIGITALOCEAN_ACCESS_TOKEN:-}" ] && [ -n "${PRODUCTION_ENV_B64:-}" ]; then
  export DIGITALOCEAN_ACCESS_TOKEN="$(echo "$PRODUCTION_ENV_B64" | base64 -d | grep '^DO_API_TOKEN=' | cut -d= -f2- | tr -d '\r')"
fi

if [ -z "${DIGITALOCEAN_ACCESS_TOKEN:-}" ]; then
  echo "ERROR: Set DO_API_TOKEN or PRODUCTION_ENV_B64 with DO_API_TOKEN"
  exit 1
fi

if ! command -v doctl >/dev/null 2>&1; then
  echo "ERROR: doctl not installed"
  exit 1
fi

# Map legacy size slugs
case "$DO_SIZE" in
  s-2vcpu-8gb) DO_SIZE="s-2vcpu-8gb-160gb-intel" ;;
esac

doctl auth init -t "$DIGITALOCEAN_ACCESS_TOKEN" >/dev/null 2>&1 || true

# Resolve SSH key for droplet root login
SSH_KEY_ID="${DO_SSH_KEY_ID:-}"
if [ -z "$SSH_KEY_ID" ] && [ -n "${PROD_SSH_KEY:-}" ]; then
  KEY_FILE="$(mktemp)"
  PUB_FILE="$(mktemp)"
  trap 'rm -f "$KEY_FILE" "$PUB_FILE"' EXIT
  printf '%s\n' "$PROD_SSH_KEY" > "$KEY_FILE"
  chmod 600 "$KEY_FILE"
  ssh-keygen -y -f "$KEY_FILE" > "$PUB_FILE" 2>/dev/null || {
    echo "ERROR: PROD_SSH_KEY is not a valid private key"
    exit 1
  }
  FINGERPRINT="$(ssh-keygen -lf "$PUB_FILE" -E md5 | awk '{print $2}' | sed 's/MD5://')"
  SSH_KEY_ID="$(doctl compute ssh-key list --format ID,FingerPrint --no-header | awk -v fp="$FINGERPRINT" '$2==fp {print $1; exit}')"
  if [ -z "$SSH_KEY_ID" ]; then
    doctl compute ssh-key import "fixitlab-ci-$(date +%Y%m%d)" --public-key-file "$PUB_FILE"
    SSH_KEY_ID="$(doctl compute ssh-key list --format ID,FingerPrint --no-header | awk -v fp="$FINGERPRINT" '$2==fp {print $1; exit}')"
  fi
fi

if [ -z "$SSH_KEY_ID" ]; then
  echo "ERROR: Set DO_SSH_KEY_ID or PROD_SSH_KEY for droplet SSH access"
  exit 1
fi

EXISTING_ID="$(doctl compute droplet list --format ID,Name --no-header | awk -v n="$DROPLET_NAME" '$2==n {print $1; exit}')"

if [ -n "$EXISTING_ID" ]; then
  echo "Droplet $DROPLET_NAME already exists (id=$EXISTING_ID) — reusing"
  DROPLET_ID="$EXISTING_ID"
else
  USER_DATA=""
  BOOTSTRAP="$ROOT/infra/digitalocean/bootstrap-platform.sh"
  CREATE_ARGS=(
    "$DROPLET_NAME"
    --region "$DO_REGION"
    --size "$DO_SIZE"
    --image "$IMAGE"
    --ssh-keys "$SSH_KEY_ID"
    --tag-names fixitlab,production,fixitlab-prod
    --enable-monitoring
    --wait
  )
  if [ -f "$BOOTSTRAP" ]; then
    CREATE_ARGS+=(--user-data-file "$BOOTSTRAP")
  fi
  echo "Creating droplet $DROPLET_NAME in $DO_REGION ($DO_SIZE)..."
  doctl compute droplet create "${CREATE_ARGS[@]}"
  DROPLET_ID="$(doctl compute droplet list --format ID,Name --no-header | awk -v n="$DROPLET_NAME" '$2==n {print $1; exit}')"
fi

PUBLIC_IP="$(doctl compute droplet get "$DROPLET_ID" --format PublicIPv4 --no-header)"

echo "droplet_id=$DROPLET_ID"
echo "public_ip=$PUBLIC_IP"
echo "ssh_key_id=$SSH_KEY_ID"

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  {
    echo "droplet_id=$DROPLET_ID"
    echo "public_ip=$PUBLIC_IP"
    echo "ssh_key_id=$SSH_KEY_ID"
  } >> "$GITHUB_OUTPUT"
fi

# Wait for SSH (cloud-init bootstrap)
echo "Waiting for SSH on $PUBLIC_IP..."
SSH_OPTS=(-o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes)
KEY_FILE=""
if [ -n "${PROD_SSH_KEY:-}" ]; then
  KEY_FILE="$(mktemp)"
  printf '%s\n' "$PROD_SSH_KEY" | tr -d '\r' > "$KEY_FILE"
  chmod 600 "$KEY_FILE"
  SSH_OPTS+=(-i "$KEY_FILE")
fi
for i in $(seq 1 40); do
  if ssh "${SSH_OPTS[@]}" "root@${PUBLIC_IP}" "command -v docker" >/dev/null 2>&1; then
    echo "SSH ready (attempt $i)"
    [ -n "$KEY_FILE" ] && rm -f "$KEY_FILE"
    exit 0
  fi
  echo "  attempt $i/40..."
  sleep 15
done
[ -n "$KEY_FILE" ] && rm -f "$KEY_FILE"

echo "WARN: SSH not ready yet — deploy job may retry. IP=$PUBLIC_IP"
exit 0
