#!/usr/bin/env bash
# Start Vault container if needed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

docker compose -f docker-compose.vault.yml up -d vault

for i in $(seq 1 30); do
  if docker compose -f docker-compose.vault.yml exec -T vault vault status >/dev/null 2>&1 \
    || docker compose -f docker-compose.vault.yml exec -T vault vault status 2>&1 | grep -q "Sealed"; then
    echo "Vault container ready"
    exit 0
  fi
  sleep 2
done

echo "ERROR: Vault container did not become ready"
exit 1
