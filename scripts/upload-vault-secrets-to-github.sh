#!/usr/bin/env bash
# Upload Vault credentials to GitHub Actions (production environment).
# Run after ./scripts/vault/bootstrap.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APPROLE_FILE="${1:-$ROOT/deploy/vault-approle.env}"

if ! command -v gh >/dev/null 2>&1; then
  echo "Install GitHub CLI: brew install gh && gh auth login"
  exit 1
fi

if [ ! -f "$APPROLE_FILE" ]; then
  echo "Missing $APPROLE_FILE — run: ./scripts/vault/bootstrap.sh deploy/production.env"
  exit 1
fi

# shellcheck disable=SC1090
source "$APPROLE_FILE"

REPO="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
ENV_NAME="${GITHUB_ENVIRONMENT:-production}"

gh api "repos/${REPO}/environments/${ENV_NAME}" -X PUT -f wait_timer=0 >/dev/null 2>&1 || true

printf '%s' "${VAULT_UNSEAL_KEY:-}" | gh secret set VAULT_UNSEAL_KEY --env "$ENV_NAME" --repo "$REPO"
printf '%s' "${VAULT_ROLE_ID:-}" | gh secret set VAULT_ROLE_ID --env "$ENV_NAME" --repo "$REPO"
printf '%s' "${VAULT_SECRET_ID:-}" | gh secret set VAULT_SECRET_ID --env "$ENV_NAME" --repo "$REPO"
printf '%s' "true" | gh secret set VAULT_ENABLED --env "$ENV_NAME" --repo "$REPO"

echo "Uploaded to GitHub environment '$ENV_NAME':"
echo "  VAULT_UNSEAL_KEY, VAULT_ROLE_ID, VAULT_SECRET_ID, VAULT_ENABLED=true"
echo ""
echo "After Vault is verified on the server, you may remove PRODUCTION_ENV_B64 from GitHub"
echo "(keep a backup of deploy/production.env offline only)."
