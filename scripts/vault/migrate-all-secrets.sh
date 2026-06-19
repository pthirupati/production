#!/usr/bin/env bash
# Merge all local env sources → HashiCorp Vault KV → render .env.production (+ .env).
#
# Usage:
#   ./scripts/vault/migrate-all-secrets.sh              # merge + seed/update Vault + render
#   ./scripts/vault/migrate-all-secrets.sh --cleanup  # also archive plaintext env backups
#
# Requires Docker. On first run creates deploy/vault-init.json + deploy/vault-approle.env.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

CLEANUP=0
for arg in "$@"; do
  case "$arg" in
    --cleanup) CLEANUP=1 ;;
    -h|--help)
      echo "Usage: $0 [--cleanup]"
      exit 0
      ;;
  esac
done

MERGED="$(mktemp)"
trap 'rm -f "$MERGED"' EXIT

chmod +x "$ROOT/scripts/vault/"*.sh "$ROOT/scripts/vault/"*.py 2>/dev/null || true

echo "=== FixitLab Vault migration ==="
echo "[1/6] Merging env sources (deploy/production.env → .env.production → .env)"
python3 "$ROOT/scripts/vault/merge-env-sources.py" > "$MERGED"
chmod 600 "$MERGED"
KEY_COUNT="$(grep -c '^[A-Z]' "$MERGED" || true)"
echo "      $KEY_COUNT variables merged"

# Keep deploy/production.env in sync as the offline master copy
mkdir -p "$ROOT/deploy"
cp "$MERGED" "$ROOT/deploy/production.env"
chmod 600 "$ROOT/deploy/production.env"
echo "[2/6] Updated deploy/production.env (master copy)"

INIT_FILE="${VAULT_INIT_FILE:-$ROOT/deploy/vault-init.json}"
APPROLE_FILE="${VAULT_APPROLE_FILE:-$ROOT/deploy/vault-approle.env}"

bash "$ROOT/scripts/vault/start.sh"

# shellcheck source=lib.sh
source "$ROOT/scripts/vault/lib.sh"

VAULT_INITIALIZED=false
if vault_compose exec -T vault vault status -format=json 2>/dev/null \
  | grep -q '"initialized":true'; then
  VAULT_INITIALIZED=true
fi

if [ "$VAULT_INITIALIZED" = false ]; then
  echo "[3/6] First-time Vault bootstrap"
  bash "$ROOT/scripts/vault/bootstrap.sh" "$MERGED"
elif [ -f "$INIT_FILE" ]; then
  echo "[3/6] Vault initialized — re-seeding KV from merged env"
  bash "$ROOT/scripts/vault/seed-from-env.sh" "$MERGED"
else
  echo "[3/6] Vault initialized — bootstrap re-seed (no local init file)"
  bash "$ROOT/scripts/vault/bootstrap.sh" "$MERGED"
fi

echo "[4/6] Uploading AppRole credentials to GitHub (if gh available)"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  bash "$ROOT/scripts/upload-vault-secrets-to-github.sh" "$APPROLE_FILE" || echo "WARN: GitHub upload skipped"
else
  echo "      Skipped — run ./scripts/upload-vault-secrets-to-github.sh manually"
fi

echo "[5/6] Rendering .env.production from Vault"
bash "$ROOT/scripts/vault/render-env.sh" "$ROOT/.env.production"

echo "[6/6] Validating rendered env"
# shellcheck disable=SC1090
[ -f "$APPROLE_FILE" ] && source "$APPROLE_FILE"
export VAULT_ENABLED=true
bash "$ROOT/scripts/sync-production-env.sh" "$ROOT/.env.production"

if [ "$CLEANUP" -eq 1 ]; then
  STAMP="$(date +%Y%m%d-%H%M%S)"
  ARCHIVE="$ROOT/deploy/archived-env-$STAMP"
  mkdir -p "$ARCHIVE"
  for f in "$ROOT/.env" "$ROOT/.env.production"; do
    if [ -f "$f" ] && [ "$f" != "$ROOT/.env.production" ]; then
      cp "$f" "$ARCHIVE/" 2>/dev/null || true
      rm -f "$f"
      echo "      Archived and removed $f"
    fi
  done
  echo "      Plaintext backups in $ARCHIVE (store encrypted, then delete)"
  echo ""
  echo "Optional: remove PRODUCTION_ENV_B64 from GitHub after verifying deploy:"
  echo "  gh secret delete PRODUCTION_ENV_B64 --env production --repo OWNER/REPO"
fi

echo ""
echo "=== Vault migration complete ==="
echo "  KV path: ${VAULT_KV_PATH:-secret/fixitlab/config}"
echo "  AppRole: $APPROLE_FILE"
echo "  Render:  .env.production ($(grep -c '^[A-Z]' "$ROOT/.env.production" || echo 0) vars)"
echo ""
echo "Restart platform:  ./scripts/platform-start.sh"
