#!/usr/bin/env bash
# Start the full FixitLab platform (preserves all database/user data in named volumes)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"

# Sync production env from GitHub secrets or local deploy/production.env
chmod +x "$ROOT/scripts/sync-production-env.sh" "$ROOT/scripts/ensure-ssl-certs.sh" "$ROOT/scripts/startup.sh" 2>/dev/null || true
bash "$ROOT/scripts/sync-production-env.sh" "$ROOT/.env.production"
ENV_FILE=".env.production"

echo "=== FixitLab Platform START ==="
echo "Compose: $COMPOSE_FILE | Env: $ENV_FILE"

# Lab network is external to compose (shared by per-user lab containers)
docker network inspect fixitlab_labs >/dev/null 2>&1 || docker network create fixitlab_labs

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build

echo "Waiting for backend..."
for i in $(seq 1 60); do
  if docker compose -f "$COMPOSE_FILE" exec -T backend python -c \
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
docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py migrate --noinput

echo "Seeding/updating scenarios..."
docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py seed_scenarios --dir /scenarios

if [ "${BUILD_SCENARIOS:-1}" = "1" ]; then
  echo "Building scenario lab images..."
  docker compose -f "$COMPOSE_FILE" exec -T backend bash /scripts/build-scenario-images.sh 2>/dev/null || \
    bash "$ROOT/scripts/build-scenario-images.sh"
fi

echo ""
echo "✅ Platform is UP"
echo "   Users, subscriptions, and progress are stored in Docker volume: fixitlab_db_data"
# shellcheck disable=SC1090
set -a && source "$ENV_FILE" && set +a
echo "   Site: ${SITE_URL:-http://localhost}"
docker compose -f "$COMPOSE_FILE" ps
