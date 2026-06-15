#!/usr/bin/env bash
# Start the full FixitLab platform (preserves all database/user data in named volumes)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"

_env_true() {
  case "${1:-}" in
    1|true|TRUE|True|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

# Sync production env from Vault, GitHub secrets, or local deploy/production.env
chmod +x "$ROOT/scripts/sync-production-env.sh" "$ROOT/scripts/ensure-ssl-certs.sh" "$ROOT/scripts/startup.sh" \
  "$ROOT/scripts/vault/"*.sh "$ROOT/scripts/vault/env-kv-helper.py" 2>/dev/null || true

# Vault must be up before render-env (when enabled via env or local approle file)
if _env_true "${VAULT_ENABLED:-}" || [ -f "$ROOT/deploy/vault-approle.env" ]; then
  bash "$ROOT/scripts/vault/start.sh" 2>/dev/null || true
  VAULT_CFG_HASH="$(md5sum "$ROOT/infra/vault/config.hcl" 2>/dev/null | awk '{print $1}' || md5 -q "$ROOT/infra/vault/config.hcl" 2>/dev/null || true)"
  VAULT_CFG_MARKER="/tmp/fixitlab-vault-config-hash"
  if [ -n "$VAULT_CFG_HASH" ] && [ -f "$VAULT_CFG_MARKER" ] && [ "$(cat "$VAULT_CFG_MARKER")" != "$VAULT_CFG_HASH" ]; then
    echo "Vault config changed — recreating container"
    docker compose -f docker-compose.vault.yml up -d --force-recreate vault 2>/dev/null || true
    bash "$ROOT/scripts/vault/unseal.sh" 2>/dev/null || true
  fi
  [ -n "$VAULT_CFG_HASH" ] && echo "$VAULT_CFG_HASH" > "$VAULT_CFG_MARKER"
fi

bash "$ROOT/scripts/sync-production-env.sh" "$ROOT/.env.production"
ENV_FILE=".env.production"

echo "=== FixitLab Platform START ==="
echo "Compose: $COMPOSE_FILE | Env: $ENV_FILE"

# Lab network is external to compose (shared by per-user lab containers)
docker network inspect fixitlab_labs >/dev/null 2>&1 || docker network create fixitlab_labs

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build

# Recreate app workers when env file changes so containers pick up new secrets
ENV_HASH="$(md5sum "$ENV_FILE" 2>/dev/null | awk '{print $1}' || md5 -q "$ENV_FILE" 2>/dev/null || true)"
ENV_HASH_FILE="/tmp/fixitlab-env-hash"
if [ -n "$ENV_HASH" ] && [ -f "$ENV_HASH_FILE" ] && [ "$(cat "$ENV_HASH_FILE")" != "$ENV_HASH" ]; then
  echo "Env changed — recreating backend/celery containers"
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --force-recreate \
    backend celery_worker celery_provisioning celery_maintenance celery_beat
fi
[ -n "$ENV_HASH" ] && echo "$ENV_HASH" > "$ENV_HASH_FILE"

echo "Waiting for backend..."
for i in $(seq 1 60); do
  if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend python -c \
    "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/api/health/'); assert r.status==200" 2>/dev/null; then
    break
  fi
  sleep 3
done

echo "Ensuring SSL certificates (Let's Encrypt)..."
export COMPOSE_FILE ENV_FILE
if bash "$ROOT/scripts/ensure-ssl-certs.sh"; then
  echo "SSL ready"
else
  echo "WARNING: SSL certificate not obtained — site available on HTTP only until DNS/port 80 is fixed"
fi

echo "Running migrations (safe — does not wipe data)..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend python manage.py migrate --noinput

echo "Syncing superuser credentials from env..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend python /scripts/create_superuser.py || true

echo "Seeding/updating scenarios..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend python manage.py seed_scenarios --dir /scenarios

should_build_scenarios() {
  case "${1:-true}" in
    1|true|TRUE|True|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

if should_build_scenarios "${BUILD_SCENARIOS:-true}"; then
  echo "Building scenario lab images (BUILD_SCENARIOS=${BUILD_SCENARIOS:-true})..."
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend bash /scripts/build-scenario-images.sh 2>/dev/null || \
    bash "$ROOT/scripts/build-scenario-images.sh"
  echo "Validating scenario images..."
  bash "$ROOT/scripts/validate-scenario-images.sh"
else
  echo "Skipping scenario image build (BUILD_SCENARIOS=${BUILD_SCENARIOS})"
  bash "$ROOT/scripts/validate-scenario-images.sh" || {
    echo "ERROR: Scenario images missing. Re-run with BUILD_SCENARIOS=true"
    exit 1
  }
fi

echo ""
echo "✅ Platform is UP"
echo "   Users, subscriptions, and progress are stored in Docker volume: fixitlab_db_data"
# shellcheck source=env-helpers.sh
source "$ROOT/scripts/env-helpers.sh"
echo "   Site: $(env_val SITE_URL "$ENV_FILE")"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
