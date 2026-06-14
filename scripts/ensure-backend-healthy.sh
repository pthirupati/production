#!/usr/bin/env bash
# Ensure backend (and celery) are running after heavy E2E lab tests.
# Long all-scenario runs can OOM or restart the backend; step 6 needs a live API.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
MAX_WAIT="${BACKEND_HEALTH_WAIT:-120}"

_backend_ok() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend python -c \
    "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/api/health/'); assert r.status==200" \
    >/dev/null 2>&1
}

echo ">>> Ensuring backend is healthy (timeout ${MAX_WAIT}s)..."

if _backend_ok; then
  echo "  ✓ Backend already healthy"
  exit 0
fi

echo "  Backend not responding — restarting backend + celery workers..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d backend celery_worker celery_provisioning celery_maintenance celery_beat

elapsed=0
while [ "$elapsed" -lt "$MAX_WAIT" ]; do
  if _backend_ok; then
    echo "  ✓ Backend healthy after ${elapsed}s"
    exit 0
  fi
  sleep 5
  elapsed=$((elapsed + 5))
done

echo "ERROR: Backend did not become healthy within ${MAX_WAIT}s"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps backend || true
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs backend --tail 40 || true
exit 1
