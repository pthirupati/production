#!/usr/bin/env bash
# Shared Vault Docker Compose helpers.
# Vault must run on fixitlab_net so backend/celery can resolve http://vault:8200.
set -euo pipefail

VAULT_LIB_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

vault_compose_file() {
  if [ -f "$VAULT_LIB_ROOT/docker-compose.prod.yml" ]; then
    echo "docker-compose.prod.yml"
  else
    echo "docker-compose.vault.yml"
  fi
}

vault_env_file() {
  local env="${ENV_FILE:-.env.production}"
  if [ -f "$VAULT_LIB_ROOT/$env" ]; then
    echo "$env"
  fi
}

vault_ensure_networks() {
  docker network inspect fixitlab_net >/dev/null 2>&1 || docker network create fixitlab_net
}

vault_compose() {
  local cf envf
  cf="$(vault_compose_file)"
  cd "$VAULT_LIB_ROOT"
  vault_ensure_networks
  envf="$(vault_env_file)"
  if [ "$cf" = "docker-compose.prod.yml" ] && [ -n "$envf" ]; then
    docker compose -f "$cf" --env-file "$envf" "$@"
  else
    docker compose -f "$cf" "$@"
  fi
}

vault_container_name() {
  echo "fixitlab_vault"
}
