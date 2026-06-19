#!/usr/bin/env bash
# Re-upload secrets from local env file into Vault (after editing deploy/production.env).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

ENV_FILE="${1:-$ROOT/deploy/production.env}"
KV_PATH="${VAULT_KV_PATH:-secret/fixitlab/config}"
INIT_FILE="${VAULT_INIT_FILE:-$ROOT/deploy/vault-init.json}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE"
  exit 1
fi

if [ ! -f "$INIT_FILE" ]; then
  echo "Vault not initialized. Run: ./scripts/vault/bootstrap.sh $ENV_FILE"
  exit 1
fi

chmod +x "$ROOT/scripts/vault/"*.sh
bash "$ROOT/scripts/vault/unseal.sh"

# shellcheck source=lib.sh
source "$ROOT/scripts/vault/lib.sh"

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
export VAULT_TOKEN="$(python3 -c "import json; print(json.load(open('$INIT_FILE'))['root_token'])")"

TMP_JSON="$(mktemp)"
python3 "$ROOT/scripts/vault/env-kv-helper.py" env-to-json "$ENV_FILE" > "$TMP_JSON"
chmod 600 "$TMP_JSON"

docker cp "$TMP_JSON" fixitlab_vault:/tmp/vault-seed.json
vault_compose exec -T -e VAULT_TOKEN vault \
  vault kv put "$KV_PATH" @/tmp/vault-seed.json
vault_compose exec -T vault rm -f /tmp/vault-seed.json

rm -f "$TMP_JSON"
echo "[vault] Updated $KV_PATH from $ENV_FILE"
