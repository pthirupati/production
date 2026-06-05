#!/usr/bin/env bash
# Upload production secrets to GitHub Actions (Environment: production).
# Run once from your machine after filling deploy/production.env locally.
#
# Requires: gh auth login
# Usage:   ./scripts/upload-secrets-to-github.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/deploy/production.env"
if [ -n "${1:-}" ] && [ "${1:-}" != "--print-manual" ]; then
  ENV_FILE="$1"
fi
if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) is not installed."
  echo ""
  echo "  macOS:   brew install gh"
  echo "  Linux:   https://github.com/cli/cli/blob/trunk/docs/install_linux.md"
  echo "  Windows: winget install GitHub.cli"
  echo ""
  echo "Then:  gh auth login"
  echo "       ./scripts/upload-secrets-to-github.sh"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "GitHub CLI is installed but you are not logged in."
  echo ""
  echo "  gh auth login"
  echo ""
  echo "Choose: GitHub.com → HTTPS → Login with browser (or paste a token)."
  echo "Then re-run:  ./scripts/upload-secrets-to-github.sh"
  exit 1
fi

if [ "${1:-}" = "--print-manual" ]; then
  ENV_FILE="${2:-$ROOT/deploy/production.env}"
  if [ ! -f "$ENV_FILE" ]; then
    echo "Missing $ENV_FILE"
    exit 1
  fi
  echo "Manual upload (GitHub web UI):"
  echo "  Repo → Settings → Environments → production → Add secret"
  echo ""
  echo "PRODUCTION_ENV_B64 — paste output of:"
  echo "  base64 < deploy/production.env | pbcopy   # macOS, copies to clipboard"
  echo ""
  echo "PROD_HOST=139.59.58.8"
  echo "PROD_USER=root"
  echo "PROD_SSH_KEY — paste contents of ~/.ssh/id_ed25519 (full PEM)"
  exit 0
fi

REPO="${GITHUB_REPOSITORY:-$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || true)}"

if [ -z "$REPO" ]; then
  echo "Run from inside the git repo or set GITHUB_REPOSITORY=owner/repo"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE"
  echo "Copy env.production.example → deploy/production.env and fill all values (including Jira)."
  exit 1
fi

# Read deploy SSH settings from env file, infra metadata, or defaults
META="$ROOT/infra/digitalocean/production.json"
DEFAULT_HOST=""
if [ -f "$META" ]; then
  DEFAULT_HOST="$(python3 -c "import json; print(json.load(open('$META')).get('public_ipv4',''))" 2>/dev/null || true)"
fi
PROD_HOST="${PROD_HOST:-$(grep '^PROD_HOST=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '\r' || true)}"
PROD_HOST="${PROD_HOST:-$DEFAULT_HOST}"
PROD_HOST="${PROD_HOST:-139.59.58.8}"
PROD_USER="${PROD_USER:-$(grep '^PROD_USER=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '\r' || echo 'root')}"

SSH_KEY_FILE="${PROD_SSH_KEY_FILE:-}"
if [ -z "$SSH_KEY_FILE" ]; then
  for keyfile in "$HOME/.ssh/id_ed25519" "$HOME/.ssh/id_rsa"; do
    if [ -f "$keyfile" ]; then
      SSH_KEY_FILE="$keyfile"
      break
    fi
  done
fi

if [ -z "${PROD_SSH_KEY:-}" ]; then
  if [ -n "$SSH_KEY_FILE" ] && [ -f "$SSH_KEY_FILE" ]; then
    PROD_SSH_KEY="$(cat "$SSH_KEY_FILE")"
  fi
fi

if [ -z "${PROD_SSH_KEY:-}" ]; then
  echo "Set PROD_SSH_KEY to your SSH private key, or place key at ~/.ssh/id_ed25519"
  exit 1
fi

# PEM private keys must end with a newline for GitHub Actions SSH actions
case "$PROD_SSH_KEY" in
  *$'\n') ;;
  *) PROD_SSH_KEY="${PROD_SSH_KEY}"$'\n' ;;
esac

if [ -n "$SSH_KEY_FILE" ] && ssh-keygen -y -f "$SSH_KEY_FILE" >/dev/null 2>&1; then
  echo "Using SSH key: $SSH_KEY_FILE"
  if ! ssh -i "$SSH_KEY_FILE" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 \
      "${PROD_USER}@${PROD_HOST}" 'echo ok' >/dev/null 2>&1; then
    echo "ERROR: SSH key does not work for ${PROD_USER}@${PROD_HOST}"
    echo "Fix PROD_HOST or use the private key whose public key is on the server."
    exit 1
  fi
  echo "  ✓ SSH verified to ${PROD_USER}@${PROD_HOST}"
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
echo "  ✓ PROD_SSH_KEY (private key, trailing newline preserved)"

echo ""
echo "Done. GitHub Actions → production environment now has all env vars."
echo "Push to main or run Platform Start — workflows use PRODUCTION_ENV_B64 on the server."
