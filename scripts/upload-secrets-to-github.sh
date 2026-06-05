#!/usr/bin/env bash
# Upload production secrets to GitHub Actions (Environment: production).
# Run once from your machine after filling deploy/production.env locally.
#
# Requires: gh auth login
# Usage:   ./scripts/upload-secrets-to-github.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${1:-$ROOT/deploy/production.env}"
REPO="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)}"

if ! command -v gh >/dev/null 2>&1; then
  echo "Install GitHub CLI: https://cli.github.com/"
  exit 1
fi

if [ -z "$REPO" ]; then
  echo "Run from inside the git repo or set GITHUB_REPOSITORY=owner/repo"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE"
  echo "Copy env.production.example → deploy/production.env and fill all values (including Jira)."
  exit 1
fi

# Read deploy SSH settings from env file or defaults
PROD_HOST="${PROD_HOST:-$(grep '^PROD_HOST=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || echo '139.59.58.8')}"
PROD_USER="${PROD_USER:-$(grep '^PROD_USER=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || echo 'root')}"

if [ -z "${PROD_SSH_KEY:-}" ]; then
  for keyfile in "$HOME/.ssh/id_rsa" "$HOME/.ssh/id_ed25519"; do
    if [ -f "$keyfile" ]; then
      PROD_SSH_KEY="$(cat "$keyfile")"
      break
    fi
  done
fi

if [ -z "${PROD_SSH_KEY:-}" ]; then
  echo "Set PROD_SSH_KEY to your SSH private key, or place key at ~/.ssh/id_ed25519"
  exit 1
fi

echo "Uploading secrets to GitHub repo: $REPO (environment: production)"
echo ""

gh api "repos/${REPO}/environments/production" -X PUT -f wait_timer=0 >/dev/null 2>&1 || true

# Full env file as base64 (handles multiline values safely)
base64 < "$ENV_FILE" | gh secret set PRODUCTION_ENV_B64 --env production --repo "$REPO"
echo "  ✓ PRODUCTION_ENV_B64 (full .env from $ENV_FILE)"

printf '%s' "$PROD_HOST" | gh secret set PROD_HOST --env production --repo "$REPO"
echo "  ✓ PROD_HOST=$PROD_HOST"

printf '%s' "$PROD_USER" | gh secret set PROD_USER --env production --repo "$REPO"
echo "  ✓ PROD_USER=$PROD_USER"

printf '%s' "$PROD_SSH_KEY" | gh secret set PROD_SSH_KEY --env production --repo "$REPO"
echo "  ✓ PROD_SSH_KEY (private key)"

echo ""
echo "Done. GitHub Actions → production environment now has all env vars."
echo "Push to main or run Platform Start — workflows use PRODUCTION_ENV_B64 on the server."
