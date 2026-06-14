#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

echo "=== Vault status ==="
docker compose -f docker-compose.vault.yml ps vault 2>/dev/null || echo "Vault container not running"

if docker compose -f docker-compose.vault.yml exec -T vault vault status 2>&1; then
  :
else
  echo "(Vault sealed or not initialized)"
fi

if [ -f "$ROOT/deploy/vault-approle.env" ]; then
  echo ""
  echo "AppRole file: deploy/vault-approle.env (present)"
fi

if [ -f "$ROOT/deploy/vault-init.json" ]; then
  echo "Init file: deploy/vault-init.json (present — keep offline backup)"
fi
