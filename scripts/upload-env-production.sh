#!/usr/bin/env bash
# Copy production env to the server (reads PROD_HOST from deploy/production.env).
#
# Usage:
#   ./scripts/upload-env-production.sh
#   ./scripts/upload-env-production.sh deploy/production.env
#   ./scripts/upload-env-production.sh --sync-first   # refresh IP from doctl, then upload
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_ENV="$ROOT/deploy/production.env"
LOCAL_ENV="$ROOT/.env.production"
META_FILE="$ROOT/infra/digitalocean/production.json"
SYNC_FIRST=0
ENV_FILE=""

for arg in "$@"; do
  case "$arg" in
    --sync-first) SYNC_FIRST=1 ;;
    -h|--help)
      sed -n '2,8p' "$0"
      exit 0
      ;;
    *)
      [ -z "$ENV_FILE" ] && ENV_FILE="$arg"
      ;;
  esac
done

read_env_key() {
  local file="$1" key="$2"
  [ -f "$file" ] || return 1
  grep "^${key}=" "$file" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\r'
}

resolve_prod_host() {
  if [ -n "${PROD_HOST:-}" ]; then
    echo "$PROD_HOST"
    return
  fi
  local v
  for f in "$DEPLOY_ENV" "$LOCAL_ENV"; do
    v="$(read_env_key "$f" PROD_HOST || true)"
    if [ -n "$v" ]; then
      echo "$v"
      return
    fi
  done
  if [ -f "$META_FILE" ] && command -v python3 >/dev/null 2>&1; then
    python3 -c "import json; print(json.load(open('$META_FILE'))['public_ipv4'])"
    return
  fi
  echo "ERROR: PROD_HOST not set. Run ./scripts/update-production-host.sh --from-doctl fixitlab-prod" >&2
  exit 1
}

resolve_prod_user() {
  if [ -n "${PROD_USER:-}" ]; then
    echo "$PROD_USER"
    return
  fi
  local v
  for f in "$DEPLOY_ENV" "$LOCAL_ENV"; do
    v="$(read_env_key "$f" PROD_USER || true)"
    if [ -n "$v" ]; then
      echo "$v"
      return
    fi
  done
  if [ -f "$META_FILE" ] && command -v python3 >/dev/null 2>&1; then
    python3 -c "import json; print(json.load(open('$META_FILE')).get('ssh_user', 'root'))"
    return
  fi
  echo "root"
}

if [ "$SYNC_FIRST" -eq 1 ] && [ -x "$ROOT/scripts/update-production-host.sh" ]; then
  echo "Syncing host metadata from DigitalOcean..."
  "$ROOT/scripts/update-production-host.sh" --from-doctl fixitlab-prod || {
    echo "WARN: doctl sync failed — using local deploy/production.env"
  }
fi

# Source of truth: deploy/production.env → mirror to .env.production before upload
if [ -z "$ENV_FILE" ]; then
  if [ -f "$DEPLOY_ENV" ]; then
    ENV_FILE="$DEPLOY_ENV"
  elif [ -f "$LOCAL_ENV" ]; then
    ENV_FILE="$LOCAL_ENV"
  else
    echo "Missing deploy/production.env — copy from env.production.example and fill secrets."
    exit 1
  fi
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE"
  exit 1
fi

# Keep .env.production in sync when uploading from deploy/production.env
if [ "$ENV_FILE" = "$DEPLOY_ENV" ]; then
  cp "$DEPLOY_ENV" "$LOCAL_ENV"
  chmod 600 "$LOCAL_ENV" "$DEPLOY_ENV"
  echo "Synced $DEPLOY_ENV → $LOCAL_ENV"
fi

PROD_HOST="$(resolve_prod_host)"
PROD_USER="$(resolve_prod_user)"

# Warn if env file PROD_HOST differs from resolved host
ENV_PROD_HOST="$(read_env_key "$ENV_FILE" PROD_HOST || true)"
if [ -n "$ENV_PROD_HOST" ] && [ "$ENV_PROD_HOST" != "$PROD_HOST" ]; then
  echo "WARN: $ENV_FILE has PROD_HOST=$ENV_PROD_HOST but using $PROD_HOST"
  echo "      Run: ./scripts/update-production-host.sh --from-doctl fixitlab-prod"
fi

REMOTE_DIR="/opt/fixitlab"
REMOTE_ENV="${REMOTE_DIR}/.env.production"

echo ""
echo "Uploading $ENV_FILE → ${PROD_USER}@${PROD_HOST}:${REMOTE_ENV}"

ssh -o ConnectTimeout=15 "${PROD_USER}@${PROD_HOST}" "mkdir -p ${REMOTE_DIR}" || {
  echo "ERROR: Cannot SSH to ${PROD_USER}@${PROD_HOST}"
  echo "  Wait for cloud-init (~2 min after droplet create), then retry."
  exit 1
}

scp "$ENV_FILE" "${PROD_USER}@${PROD_HOST}:${REMOTE_ENV}"
ssh "${PROD_USER}@${PROD_HOST}" "chmod 600 ${REMOTE_ENV} && cp ${REMOTE_ENV} ${REMOTE_DIR}/.env 2>/dev/null || true"

echo ""
echo "Done. Start or restart platform on server:"
echo "  ssh ${PROD_USER}@${PROD_HOST} 'cd ${REMOTE_DIR} && ./scripts/platform-start.sh'"
echo ""
echo "Or push to main — GitHub Actions deploy uses PRODUCTION_ENV_B64 secret."
