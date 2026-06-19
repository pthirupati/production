#!/usr/bin/env bash
# Ensure Vault is attached to fixitlab_net and reachable from backend.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib.sh
source "$ROOT/scripts/vault/lib.sh"

vault_ensure_networks

VAULT_NAME="$(vault_container_name)"
if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$VAULT_NAME"; then
  echo "[vault] Container not running — starting on fixitlab_net"
  vault_compose up -d vault
  bash "$ROOT/scripts/vault/unseal.sh" 2>/dev/null || true
  exit 0
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

_connect_vault_to_net() {
  local net="$1"
  [ -n "$net" ] || return 1
  if docker inspect "$VAULT_NAME" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null \
    | grep -qE "(^| )${net}( |$)"; then
    return 0
  fi
  echo "[vault] Connecting $VAULT_NAME to $net"
  docker network connect "$net" "$VAULT_NAME" 2>/dev/null || return 1
}

_connect_vault_to_net fixitlab_net || true

BACKEND="$(docker ps --format '{{.Names}}' 2>/dev/null | grep -E 'backend' | head -1 || true)"
if [ -n "$BACKEND" ]; then
  BACKEND_NET="$(docker inspect "$BACKEND" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}' 2>/dev/null \
    | grep -E 'fixitlab' | grep -v fixitlab_labs | head -1 || true)"
  _connect_vault_to_net "$BACKEND_NET" || true
fi

if [ -n "$BACKEND" ] && docker exec "$BACKEND" getent hosts vault >/dev/null 2>&1; then
  echo "[vault] Backend resolves vault — OK"
  exit 0
fi

echo "[vault] Backend cannot resolve vault — recreating container on fixitlab_net"
vault_compose up -d --force-recreate vault
bash "$ROOT/scripts/vault/unseal.sh" 2>/dev/null || true

if [ -n "$BACKEND" ] && docker exec "$BACKEND" getent hosts vault >/dev/null 2>&1; then
  echo "[vault] Backend resolves vault after recreate — OK"
else
  echo "[vault] WARN: vault hostname still not resolvable from backend"
  exit 1
fi
