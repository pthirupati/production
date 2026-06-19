#!/usr/bin/env bash
# Toggle JWT session enforcement on the running backend for parallel CI E2E.
# E2E scripts call the live backend over HTTP — env on `docker exec` alone is not enough.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
BACKUP="${ENV_FILE}.jwt-session.bak"

wait_backend() {
  for _ in $(seq 1 45); do
    if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
      curl -sf -H "X-Forwarded-Proto: https" -H "Host: fixitlab.in" \
      http://127.0.0.1:8000/api/health/ >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "WARN: backend health check timed out"
  return 1
}

disable() {
  if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: $ENV_FILE not found"
    exit 1
  fi
  cp "$ENV_FILE" "$BACKUP"
  if grep -q '^JWT_SESSION_ENFORCEMENT=' "$ENV_FILE"; then
    sed -i 's/^JWT_SESSION_ENFORCEMENT=.*/JWT_SESSION_ENFORCEMENT=0/' "$ENV_FILE"
  else
    echo "JWT_SESSION_ENFORCEMENT=0" >> "$ENV_FILE"
  fi
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --no-deps backend
  wait_backend || true
  echo "Backend running with JWT_SESSION_ENFORCEMENT=0 for E2E"
}

restore() {
  if [ -f "$BACKUP" ]; then
    mv "$BACKUP" "$ENV_FILE"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --no-deps backend
    wait_backend || true
    echo "Restored JWT session enforcement from backup"
    return 0
  fi
  if [ -f "$ENV_FILE" ] && grep -q '^JWT_SESSION_ENFORCEMENT=0' "$ENV_FILE"; then
    sed -i 's/^JWT_SESSION_ENFORCEMENT=0/JWT_SESSION_ENFORCEMENT=1/' "$ENV_FILE"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --no-deps backend
    wait_backend || true
    echo "Reset JWT_SESSION_ENFORCEMENT=1"
  fi
}

case "${1:-}" in
  disable) disable ;;
  restore) restore ;;
  *)
    echo "Usage: $0 disable|restore"
    exit 1
    ;;
esac
