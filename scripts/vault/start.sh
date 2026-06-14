#!/usr/bin/env bash
# Start Vault container if needed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

docker compose -f docker-compose.vault.yml up -d vault

# Remove stray one-off vault containers that can block the listener port
docker ps -a --filter ancestor=hashicorp/vault:1.17 --format '{{.Names}}' 2>/dev/null \
  | grep -v '^fixitlab_vault$' | xargs -r docker rm -f 2>/dev/null || true

for i in $(seq 1 30); do
  status="$(docker compose -f docker-compose.vault.yml exec -T vault vault status 2>&1 || true)"
  if echo "$status" | grep -qE 'Seal Type|connection refused|Error'; then
    if echo "$status" | grep -qv 'connection refused'; then
      echo "Vault container ready"
      exit 0
    fi
  fi
  if docker compose -f docker-compose.vault.yml ps vault 2>/dev/null | grep -q 'Up'; then
    echo "Vault container ready"
    exit 0
  fi
  sleep 2
done

echo "ERROR: Vault container did not become ready"
exit 1
