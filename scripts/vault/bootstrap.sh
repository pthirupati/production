#!/usr/bin/env bash
# One-time Vault setup: init → unseal → KV engine → AppRole → seed secrets from env file.
#
# Usage (on server or laptop with Docker):
#   ./scripts/vault/bootstrap.sh deploy/production.env
#
# Creates (gitignored):
#   deploy/vault-init.json      — unseal key + root token (store root token offline; use AppRole in prod)
#   deploy/vault-approle.env    — VAULT_ROLE_ID + VAULT_SECRET_ID for FixitLab app
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

ENV_FILE="${1:-$ROOT/deploy/production.env}"
INIT_FILE="${VAULT_INIT_FILE:-$ROOT/deploy/vault-init.json}"
APPROLE_FILE="${VAULT_APPROLE_FILE:-$ROOT/deploy/vault-approle.env}"
KV_PATH="${VAULT_KV_PATH:-secret/fixitlab/config}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  echo "Usage: $0 deploy/production.env"
  exit 1
fi

mkdir -p "$(dirname "$INIT_FILE")" "$(dirname "$APPROLE_FILE")"
chmod 700 "$(dirname "$INIT_FILE")" 2>/dev/null || true

chmod +x "$ROOT/scripts/vault/"*.sh "$ROOT/scripts/vault/env-kv-helper.py"
bash "$ROOT/scripts/vault/start.sh"

# shellcheck source=lib.sh
source "$ROOT/scripts/vault/lib.sh"

export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

_vault() {
  vault_compose exec -T -e VAULT_ADDR -e VAULT_TOKEN vault vault "$@"
}

# ── Init (once) ──
if _vault status -format=json 2>/dev/null | grep -q '"initialized":true'; then
  if [ ! -f "$INIT_FILE" ]; then
    echo "ERROR: Vault is initialized but $INIT_FILE is missing (need unseal key + root token backup)"
    exit 1
  fi
  echo "Vault already initialized — using $INIT_FILE"
else
  echo "Initializing Vault (1 unseal key — save $INIT_FILE offline)..."
  _vault operator init -key-shares=1 -key-threshold=1 -format=json > "$INIT_FILE"
  chmod 600 "$INIT_FILE"
  echo "  ✓ Wrote $INIT_FILE"
fi

UNSEAL_KEY="$(python3 -c "import json; print(json.load(open('$INIT_FILE'))['unseal_keys_b64'][0])")"
ROOT_TOKEN="$(python3 -c "import json; print(json.load(open('$INIT_FILE'))['root_token'])")"
export VAULT_TOKEN="$ROOT_TOKEN"

_vault operator unseal "$UNSEAL_KEY" >/dev/null || true

# ── KV v2 ──
if ! _vault secrets list -format=json 2>/dev/null | grep -q '"secret/"'; then
  _vault secrets enable -path=secret kv-v2
  echo "  ✓ Enabled KV v2 at secret/"
fi

# ── Policy + AppRole ──
POLICY_HCL='path "secret/data/fixitlab/*" { capabilities = ["read"] }'
echo "$POLICY_HCL" | _vault policy write fixitlab-read -
_vault auth enable approle 2>/dev/null || true
_vault write auth/approle/role/fixitlab-app token_policies=fixitlab-read token_ttl=24h token_max_ttl=72h
_vault write auth/approle/role/fixitlab-app secret_id_ttl=0 secret_id_num_uses=0

ROLE_ID="$(_vault read -field=role_id auth/approle/role/fixitlab-app/role-id)"
SECRET_ID="$(_vault write -field=secret_id -f auth/approle/role/fixitlab-app/secret-id)"

cat > "$APPROLE_FILE" <<EOF
# FixitLab Vault AppRole — gitignored, upload to GitHub secrets after bootstrap
VAULT_ADDR=http://127.0.0.1:8200
VAULT_ROLE_ID=$ROLE_ID
VAULT_SECRET_ID=$SECRET_ID
VAULT_UNSEAL_KEY=$UNSEAL_KEY
EOF
chmod 600 "$APPROLE_FILE"
echo "  ✓ Wrote $APPROLE_FILE"

# ── Seed secrets ──
TMP_JSON="$(mktemp)"
python3 "$ROOT/scripts/vault/env-kv-helper.py" env-to-json "$ENV_FILE" > "$TMP_JSON"
chmod 600 "$TMP_JSON"

docker cp "$TMP_JSON" fixitlab_vault:/tmp/vault-seed.json
vault_compose exec -T -e VAULT_TOKEN vault \
  vault kv put "$KV_PATH" @/tmp/vault-seed.json
vault_compose exec -T vault rm -f /tmp/vault-seed.json

rm -f "$TMP_JSON"
echo "  ✓ Seeded Vault path: $KV_PATH ($(grep -c '^[A-Z]' "$ENV_FILE" || echo 0) keys from env file)"

echo ""
echo "=== Vault bootstrap complete ==="
echo ""
echo "Next steps:"
echo "  1. Back up $INIT_FILE and $APPROLE_FILE offline (1Password / encrypted drive)"
echo "  2. Upload to GitHub:"
echo "       ./scripts/upload-vault-secrets-to-github.sh"
echo "  3. Enable Vault in deploy/production.env:"
echo "       VAULT_ENABLED=true"
echo "  4. Render env from Vault and restart:"
echo "       ./scripts/vault/render-env.sh"
echo "       ./scripts/platform-start.sh"
echo ""
echo "Optional: remove plaintext $ENV_FILE from server after verifying Vault render works."
