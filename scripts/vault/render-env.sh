#!/usr/bin/env bash
# Fetch all production secrets from Vault → .env.production (+ .env for compose interpolation).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

OUT="${1:-$ROOT/.env.production}"
KV_PATH="${VAULT_KV_PATH:-secret/fixitlab/config}"
export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

chmod +x "$ROOT/scripts/vault/"*.sh "$ROOT/scripts/vault/env-kv-helper.py"

bash "$ROOT/scripts/vault/unseal.sh"

ROLE_ID="${VAULT_ROLE_ID:-}"
SECRET_ID="${VAULT_SECRET_ID:-}"
APPROLE_FILE="${VAULT_APPROLE_FILE:-$ROOT/deploy/vault-approle.env}"
if [ -f "$APPROLE_FILE" ]; then
  # shellcheck disable=SC1090
  source "$APPROLE_FILE"
fi

if [ -z "$ROLE_ID" ] || [ -z "$SECRET_ID" ]; then
  echo "ERROR: VAULT_ROLE_ID and VAULT_SECRET_ID required (see deploy/vault-approle.env)"
  exit 1
fi

export VAULT_TOKEN="$(docker compose -f docker-compose.vault.yml exec -T vault \
  vault write -field=token auth/approle/login role_id="$ROLE_ID" secret_id="$SECRET_ID")"

JSON="$(docker compose -f docker-compose.vault.yml exec -T -e VAULT_TOKEN vault \
  vault kv get -format=json "$KV_PATH")"

mkdir -p "$(dirname "$OUT")"
echo "$JSON" | python3 "$ROOT/scripts/vault/env-kv-helper.py" kv-to-env > "$OUT"
chmod 600 "$OUT"

COMPOSE_ENV="$ROOT/.env"
cp "$OUT" "$COMPOSE_ENV"
chmod 600 "$COMPOSE_ENV"

count="$(grep -c '^[A-Z]' "$OUT" || true)"
echo "[vault] Rendered $count variables → $OUT"
