#!/usr/bin/env bash
# Login with AppRole and export VAULT_TOKEN for subsequent vault CLI calls.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

ROLE_ID="${VAULT_ROLE_ID:-}"
SECRET_ID="${VAULT_SECRET_ID:-}"
APPROLE_FILE="${VAULT_APPROLE_FILE:-$ROOT/deploy/vault-approle.env}"

if [ -f "$APPROLE_FILE" ]; then
  # shellcheck disable=SC1090
  source "$APPROLE_FILE"
  ROLE_ID="${VAULT_ROLE_ID:-$ROLE_ID}"
  SECRET_ID="${VAULT_SECRET_ID:-$SECRET_ID}"
fi

if [ -z "$ROLE_ID" ] || [ -z "$SECRET_ID" ]; then
  echo "ERROR: Set VAULT_ROLE_ID + VAULT_SECRET_ID or create $APPROLE_FILE"
  exit 1
fi

bash "$ROOT/scripts/vault/unseal.sh"

TOKEN="$(docker compose -f docker-compose.vault.yml exec -T vault \
  vault write -field=token auth/approle/login role_id="$ROLE_ID" secret_id="$SECRET_ID")"

export VAULT_TOKEN="$TOKEN"
echo "$TOKEN"
