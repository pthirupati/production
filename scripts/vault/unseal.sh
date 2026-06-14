#!/usr/bin/env bash
# Unseal Vault using VAULT_UNSEAL_KEY (env or deploy/vault-init.json).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

bash "$ROOT/scripts/vault/start.sh"

UNSEAL_KEY="${VAULT_UNSEAL_KEY:-}"
INIT_FILE="${VAULT_INIT_FILE:-$ROOT/deploy/vault-init.json}"

if [ -z "$UNSEAL_KEY" ] && [ -f "$INIT_FILE" ]; then
  UNSEAL_KEY="$(python3 -c "import json; d=json.load(open('$INIT_FILE')); print(d['unseal_keys_b64'][0])" 2>/dev/null || true)"
fi

if [ -z "$UNSEAL_KEY" ]; then
  echo "ERROR: Set VAULT_UNSEAL_KEY or create $INIT_FILE via vault/bootstrap.sh"
  exit 1
fi

status="$(docker compose -f docker-compose.vault.yml exec -T vault vault status -format=json 2>/dev/null || echo '{}')"
sealed="$(echo "$status" | python3 -c "import json,sys; print(json.load(sys.stdin).get('sealed', True))" 2>/dev/null || echo True)"

if [ "$sealed" = "False" ]; then
  echo "Vault already unsealed"
  exit 0
fi

docker compose -f docker-compose.vault.yml exec -T vault vault operator unseal "$UNSEAL_KEY" >/dev/null
echo "Vault unsealed"
