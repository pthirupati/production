#!/usr/bin/env bash
# Unseal Vault using VAULT_UNSEAL_KEY (env or deploy/vault-init.json).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib.sh
source "$ROOT/scripts/vault/lib.sh"

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

# After a container recreate Vault starts sealed and, for the first few seconds,
# reports "not initialized" (Code 400) before it reads the file storage backend.
# Poll until it is initialized, then unseal — retrying the unseal itself — so a
# single call reliably leaves Vault unsealed instead of racing the storage load.
initialized=False; sealed=True
for _i in $(seq 1 30); do
  status="$(vault_compose exec -T vault vault status -format=json 2>/dev/null || echo '{}')"
  initialized="$(echo "$status" | python3 -c "import json,sys; print(json.load(sys.stdin).get('initialized', False))" 2>/dev/null || echo False)"
  sealed="$(echo "$status" | python3 -c "import json,sys; print(json.load(sys.stdin).get('sealed', True))" 2>/dev/null || echo True)"
  if [ "$sealed" = "False" ]; then
    echo "Vault already unsealed"
    exit 0
  fi
  if [ "$initialized" = "True" ]; then
    if vault_compose exec -T vault vault operator unseal "$UNSEAL_KEY" >/dev/null 2>&1; then
      echo "Vault unsealed"
      exit 0
    fi
  fi
  sleep 2
done

echo "ERROR: Vault did not unseal (initialized=$initialized sealed=$sealed)"
exit 1
