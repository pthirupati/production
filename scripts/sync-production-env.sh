#!/usr/bin/env bash
# Write .env.production from GitHub secrets or local file (never commit real secrets).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/.env.production}"

write_env() {
  mkdir -p "$(dirname "$OUT")"
  cp "$1" "$OUT"
  chmod 600 "$OUT"
}

if [ -n "${PRODUCTION_ENV_B64:-}" ]; then
  echo "[env] Writing .env.production from PRODUCTION_ENV_B64 (GitHub secret)"
  echo "$PRODUCTION_ENV_B64" | base64 -d > "$OUT"
  chmod 600 "$OUT"
elif [ -n "${PRODUCTION_ENV:-}" ]; then
  echo "[env] Writing .env.production from PRODUCTION_ENV (GitHub secret)"
  printf '%s\n' "$PRODUCTION_ENV" > "$OUT"
  chmod 600 "$OUT"
elif [ -f "$ROOT/deploy/production.env" ]; then
  echo "[env] Using local deploy/production.env (dev only — use GitHub secrets in CI)"
  write_env "$ROOT/deploy/production.env"
elif [ -f "$OUT" ]; then
  echo "[env] Using existing $OUT"
  chmod 600 "$OUT"
else
  echo "ERROR: No production environment found."
  echo ""
  echo "Set GitHub Environment secrets (Settings → Environments → production):"
  echo "  PRODUCTION_ENV_B64  — base64 of full .env file (recommended)"
  echo "  PROD_HOST, PROD_USER, PROD_SSH_KEY"
  echo ""
  echo "One-time setup from your machine:"
  echo "  ./scripts/upload-secrets-to-github.sh"
  echo ""
  echo "Or copy env.production.example → deploy/production.env and fill values."
  exit 1
fi

# Validate required keys
REQUIRED=(
  DJANGO_SECRET_KEY POSTGRES_PASSWORD REDIS_PASSWORD
  CELERY_BROKER_URL SITE_URL FRONTEND_URL
)
MISSING=0
for key in "${REQUIRED[@]}"; do
  if ! grep -q "^${key}=" "$OUT" || [ -z "$(grep "^${key}=" "$OUT" | cut -d= -f2- | tr -d '[:space:]')" ]; then
    echo "  MISSING: $key"
    MISSING=1
  fi
done

if grep -q '^JIRA_ENABLED=true' "$OUT"; then
  for key in JIRA_BASE_URL JIRA_EMAIL JIRA_API_TOKEN JIRA_PROJECT_KEY JIRA_WEBHOOK_SECRET; do
    if ! grep -q "^${key}=" "$OUT" || [ -z "$(grep "^${key}=" "$OUT" | cut -d= -f2- | tr -d '[:space:]')" ]; then
      echo "  MISSING (Jira enabled): $key"
      MISSING=1
    fi
  done
fi

if [ "$MISSING" -ne 0 ]; then
  echo "ERROR: .env.production is incomplete. See env.production.example"
  exit 1
fi

echo "[env] OK — $(grep -c '^[A-Z]' "$OUT" || true) variables loaded"
