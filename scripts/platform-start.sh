#!/usr/bin/env bash
# Start the full FixitLab platform (preserves all database/user data in named volumes)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"

# Sync committed production env (enables push + workflow without manual upload)
if [ -f "$ROOT/deploy/production.env" ]; then
  cp "$ROOT/deploy/production.env" "$ROOT/.env.production"
  ENV_FILE=".env.production"
fi

[ -f "$ENV_FILE" ] || ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: Missing $ENV_FILE — add deploy/production.env or upload .env.production"
  exit 1
fi

echo "=== FixitLab Platform START ==="
echo "Compose: $COMPOSE_FILE | Env: $ENV_FILE"

# Lab network is external to compose (shared by per-user lab containers)
docker network inspect fixitlab_labs >/dev/null 2>&1 || docker network create fixitlab_labs

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build

echo "Waiting for backend..."
for i in $(seq 1 60); do
  if docker compose -f "$COMPOSE_FILE" exec -T backend python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health/')" 2>/dev/null; then
    break
  fi
  sleep 3
done

echo "Running migrations (safe — does not wipe data)..."
docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py migrate --noinput

echo "Seeding/updating scenarios..."
docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py seed_scenarios --dir /scenarios 2>/dev/null || \
  docker compose -f "$COMPOSE_FILE" exec -T backend python manage.py seed_scenarios

if [ "${BUILD_SCENARIOS:-1}" = "1" ]; then
  echo "Building scenario lab images..."
  docker compose -f "$COMPOSE_FILE" exec -T backend bash /scripts/build-scenario-images.sh 2>/dev/null || \
    bash "$ROOT/scripts/build-scenario-images.sh"
fi

echo ""
echo "✅ Platform is UP"
echo "   Users, subscriptions, and progress are stored in Docker volume: fixitlab_db_data"
echo "   Site: ${SITE_URL:-http://localhost}"
docker compose -f "$COMPOSE_FILE" ps
