#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib.sh
source "$ROOT/scripts/vault/lib.sh"

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

echo "=== Vault status ==="
vault_compose ps vault 2>/dev/null || echo "Vault container not running"

if vault_compose exec -T vault vault status 2>&1; then
  :
else
  echo "(Vault sealed or not initialized)"
fi

BACKEND="$(docker ps --format '{{.Names}}' 2>/dev/null | grep -E 'backend' | head -1 || true)"
if [ -n "$BACKEND" ]; then
  if docker exec "$BACKEND" getent hosts vault >/dev/null 2>&1; then
    echo "Backend DNS: vault → $(docker exec "$BACKEND" getent hosts vault | awk '{print $1}')"
  else
    echo "Backend DNS: vault — NOT RESOLVABLE (run scripts/vault/ensure-network.sh)"
  fi
fi

if [ -f "$ROOT/deploy/vault-approle.env" ]; then
  echo ""
  echo "AppRole file: deploy/vault-approle.env (present)"
fi

if [ -f "$ROOT/deploy/vault-init.json" ]; then
  echo "Init file: deploy/vault-init.json (present — keep offline backup)"
fi
