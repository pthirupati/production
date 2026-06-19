#!/usr/bin/env bash
# Ensure Vault is attached to fixitlab_net and reachable from backend.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib.sh
source "$ROOT/scripts/vault/lib.sh"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"

vault_ensure_networks

VAULT_NAME="$(vault_container_name)"
VAULT_WAS_REACHABLE=0

_check_backend_vault_dns() {
  local backend="$1"
  [ -n "$backend" ] || return 1
  docker exec "$backend" getent hosts vault >/dev/null 2>&1
}

_restart_app_containers() {
  echo "[vault] Restarting app containers to reload Vault secrets"
  if [ -f "$ROOT/$ENV_FILE" ]; then
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --no-deps \
      backend celery_worker celery_provisioning celery_maintenance celery_beat 2>/dev/null || true
  else
    docker compose -f "$COMPOSE_FILE" up -d --no-deps \
      backend celery_worker celery_provisioning celery_maintenance celery_beat 2>/dev/null || true
  fi
}

_connect_vault_to_net() {
  local net="$1"
  [ -n "$net" ] || return 1
  if docker inspect "$VAULT_NAME" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null \
    | grep -qE "(^| )${net}( |$)"; then
    return 0
  fi
  echo "[vault] Connecting $VAULT_NAME to $net (alias vault)"
  docker network connect --alias vault "$net" "$VAULT_NAME" 2>/dev/null || return 1
}

if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$VAULT_NAME"; then
  echo "[vault] Container not running — starting on fixitlab_net"
  vault_compose up -d vault
  bash "$ROOT/scripts/vault/unseal.sh" 2>/dev/null || true
  _restart_app_containers
  exit 0
fi

BACKEND="$(docker ps --format '{{.Names}}' 2>/dev/null | grep -E 'backend' | head -1 || true)"
if [ -n "$BACKEND" ] && _check_backend_vault_dns "$BACKEND"; then
  VAULT_WAS_REACHABLE=1
fi

# Detach from stray default network (legacy standalone vault compose)
while read -r net; do
  [ -n "$net" ] || continue
  case "$net" in
    fixitlab_net|fixitlab_fixitlab_net|fixitlab_labs) continue ;;
  esac
  echo "[vault] Detaching $VAULT_NAME from legacy network: $net"
  docker network disconnect "$net" "$VAULT_NAME" 2>/dev/null || true
done < <(docker inspect "$VAULT_NAME" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}' 2>/dev/null)

_connect_vault_to_net fixitlab_net || true

if [ -n "$BACKEND" ]; then
  BACKEND_NET="$(docker inspect "$BACKEND" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}' 2>/dev/null \
    | grep -E 'fixitlab' | grep -v fixitlab_labs | head -1 || true)"
  _connect_vault_to_net "$BACKEND_NET" || true
fi

if [ -n "$BACKEND" ] && _check_backend_vault_dns "$BACKEND"; then
  echo "[vault] Backend resolves vault — OK"
  if [ "$VAULT_WAS_REACHABLE" -eq 0 ]; then
    _restart_app_containers
  fi
  exit 0
fi

echo "[vault] Backend cannot resolve vault — recreating container on fixitlab_net"
vault_compose up -d --force-recreate vault
bash "$ROOT/scripts/vault/unseal.sh" 2>/dev/null || true

# Recreate may land on fixitlab_net while backend is still on legacy network — connect both ways
if [ -n "$BACKEND" ]; then
  BACKEND_NET="$(docker inspect "$BACKEND" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}' 2>/dev/null \
    | grep -E 'fixitlab' | grep -v fixitlab_labs | head -1 || true)"
  _connect_vault_to_net "$BACKEND_NET" || true
fi

if [ -n "$BACKEND" ] && _check_backend_vault_dns "$BACKEND"; then
  echo "[vault] Backend resolves vault after recreate — OK"
  _restart_app_containers
  exit 0
fi

echo "[vault] WARN: vault hostname still not resolvable from backend"
exit 1
