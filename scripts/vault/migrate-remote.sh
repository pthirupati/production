#!/usr/bin/env bash
# Run Vault migration on the production server over SSH.
# Usage: ./scripts/vault/migrate-remote.sh [--cleanup]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

PROD_HOST="${PROD_HOST:-}"
PROD_USER="${PROD_USER:-root}"

if [ -z "$PROD_HOST" ] && [ -f "$ROOT/deploy/production.env" ]; then
  PROD_HOST="$(grep '^PROD_HOST=' "$ROOT/deploy/production.env" | cut -d= -f2- | tr -d '[:space:]' || true)"
fi
if [ -z "$PROD_HOST" ]; then
  PROD_HOST="$(gh secret get PROD_HOST --env production --repo "${GITHUB_REPOSITORY:-pthirupati/production}" 2>/dev/null || true)"
fi

if [ -z "$PROD_HOST" ]; then
  echo "ERROR: Set PROD_HOST or add to deploy/production.env"
  exit 1
fi

CLEANUP_FLAG=""
[ "${1:-}" = "--cleanup" ] && CLEANUP_FLAG="--cleanup"

echo "=== Remote Vault migration → ${PROD_USER}@${PROD_HOST} ==="

# Push merged env to server (never print contents)
MERGED="$(mktemp)"
trap 'rm -f "$MERGED"' EXIT
python3 "$ROOT/scripts/vault/merge-env-sources.py" > "$MERGED"
chmod 600 "$MERGED"

ssh -o StrictHostKeyChecking=accept-new "${PROD_USER}@${PROD_HOST}" "mkdir -p /opt/fixitlab/deploy"
scp -q "$MERGED" "${PROD_USER}@${PROD_HOST}:/opt/fixitlab/deploy/production.env"
scp -q "$ROOT/scripts/vault/"*.sh "$ROOT/scripts/vault/"*.py \
  "${PROD_USER}@${PROD_HOST}:/opt/fixitlab/scripts/vault/" 2>/dev/null || true

ssh "${PROD_USER}@${PROD_HOST}" bash -s <<REMOTE
set -euo pipefail
cd /opt/fixitlab
git fetch origin main
git reset --hard origin/main
chmod +x scripts/vault/*.sh scripts/vault/*.py scripts/sync-production-env.sh \
  scripts/platform-start.sh scripts/upload-vault-secrets-to-github.sh 2>/dev/null || true
chmod 600 deploy/production.env
./scripts/vault/migrate-all-secrets.sh ${CLEANUP_FLAG}
./scripts/platform-start.sh
REMOTE

echo "=== Remote migration complete ==="
