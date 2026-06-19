#!/usr/bin/env bash
# Start Vault container on fixitlab_net (reachable as http://vault:8200 from app containers).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib.sh
source "$ROOT/scripts/vault/lib.sh"

vault_ensure_networks
vault_compose up -d vault

# Remove stray one-off vault containers that can block the listener port
docker ps -a --filter ancestor=hashicorp/vault:1.17 --format '{{.Names}}' 2>/dev/null \
  | grep -v '^fixitlab_vault$' | xargs -r docker rm -f 2>/dev/null || true

bash "$ROOT/scripts/vault/ensure-network.sh" 2>/dev/null || true

for i in $(seq 1 30); do
  status="$(vault_compose exec -T vault vault status 2>&1 || true)"
  if echo "$status" | grep -qE 'Seal Type|connection refused|Error'; then
    if echo "$status" | grep -qv 'connection refused'; then
      echo "Vault container ready"
      exit 0
    fi
  fi
  if vault_compose ps vault 2>/dev/null | grep -q 'Up'; then
    echo "Vault container ready"
    exit 0
  fi
  sleep 2
done

echo "ERROR: Vault container did not become ready"
exit 1
