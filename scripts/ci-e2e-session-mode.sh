#!/usr/bin/env bash
# Toggle JWT session enforcement on the running backend for parallel CI E2E.
#
# IMPORTANT (production-safety): this script used to back up .env.production,
# flip JWT_SESSION_ENFORCEMENT, and RESTART the live backend (`up -d --no-deps
# backend`). That restart + enforcement flip ran on the SAME backend real users
# hit, twice per deploy, and logged everyone out with a "server error" popup.
#
# It now flips a RUNTIME override in the shared cache via a management command
# (`manage.py jwt_session_mode`) executed INSIDE the already-running backend
# container. No restart, no .env mutation, no disruption to live sessions. The
# override carries a safety TTL so a missed "restore" self-heals.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"

# Run a manage.py command inside the live backend container (no restart).
_manage() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T backend \
    python manage.py "$@"
}

disable() {
  # Turn enforcement OFF for the duration of the parallel E2E logins.
  if _manage jwt_session_mode disable; then
    echo "JWT session enforcement DISABLED at runtime (no restart) for E2E"
  else
    echo "WARN: could not disable JWT session enforcement at runtime"
    return 1
  fi
}

restore() {
  # Re-enable enforcement at runtime. We set the override explicitly to ON
  # (rather than 'clear') so the live state is deterministic regardless of what
  # the static .env says, then it self-heals via TTL.
  if _manage jwt_session_mode enable; then
    echo "JWT session enforcement RE-ENABLED at runtime (no restart)"
  else
    echo "WARN: could not restore JWT session enforcement at runtime"
    return 1
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
