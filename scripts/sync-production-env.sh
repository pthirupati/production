#!/usr/bin/env bash
# Write .env.production from GitHub secrets or local file (never commit real secrets).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/.env.production}"

_env_true() {
  case "${1:-}" in
    1|true|TRUE|True|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

write_env() {
  mkdir -p "$(dirname "$OUT")"
  cp "$1" "$OUT"
  chmod 600 "$OUT"
}

_load_vault_approle() {
  local approle="${VAULT_APPROLE_FILE:-$ROOT/deploy/vault-approle.env}"
  if [ -f "$approle" ]; then
    # shellcheck disable=SC1090
    source "$approle"
    export VAULT_ROLE_ID="${VAULT_ROLE_ID:-}"
    export VAULT_SECRET_ID="${VAULT_SECRET_ID:-}"
    export VAULT_UNSEAL_KEY="${VAULT_UNSEAL_KEY:-}"
    export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
  fi
  if _env_true "${VAULT_ENABLED:-}"; then
    export VAULT_ENABLED=true
  fi
}

_load_vault_approle

_vault_ready() {
  _env_true "${VAULT_ENABLED:-}" \
    && [ -n "${VAULT_ROLE_ID:-}" ] \
    && [ -n "${VAULT_SECRET_ID:-}" ] \
    && [ -n "${VAULT_UNSEAL_KEY:-}" ] \
    && [ -x "$ROOT/scripts/vault/render-env.sh" ]
}

_vault_can_seed() {
  _env_true "${VAULT_ENABLED:-}" \
    && [ -f "$ROOT/deploy/vault-init.json" ] \
    && [ -x "$ROOT/scripts/vault/seed-from-env.sh" ]
}

_seed_vault_from_file() {
  local src="$1"
  if [ ! -f "$src" ]; then
    return 0
  fi
  if grep -q '^VAULT_ENABLED=true' "$src" 2>/dev/null; then
    export VAULT_ENABLED=true
  fi
  if _vault_can_seed; then
    echo "[env] Syncing Vault KV from updated env source"
    bash "$ROOT/scripts/vault/seed-from-env.sh" "$src" || echo "[env] WARN: Vault KV seed failed"
    return 0
  fi
  if _env_true "${VAULT_ENABLED:-}" && [ -x "$ROOT/scripts/vault/bootstrap.sh" ] && [ ! -f "$ROOT/deploy/vault-init.json" ]; then
    echo "[env] First-time Vault bootstrap from env source"
    bash "$ROOT/scripts/vault/bootstrap.sh" "$src" || echo "[env] WARN: Vault bootstrap failed"
  fi
}

if [ -n "${PRODUCTION_ENV_B64:-}" ] && _vault_ready; then
  echo "[env] Vault enabled — seeding KV from PRODUCTION_ENV_B64 then rendering (not writing plaintext)"
  TMP_SEED="$(mktemp)"
  echo "$PRODUCTION_ENV_B64" | base64 -d > "$TMP_SEED"
  chmod 600 "$TMP_SEED"
  _seed_vault_from_file "$TMP_SEED"
  rm -f "$TMP_SEED"
  if ! bash "$ROOT/scripts/vault/render-env.sh" "$OUT"; then
    echo "[env] WARN: Vault render failed — falling back to PRODUCTION_ENV_B64"
    echo "$PRODUCTION_ENV_B64" | base64 -d > "$OUT"
    chmod 600 "$OUT"
  fi
elif _vault_ready; then
  echo "[env] Rendering .env.production from HashiCorp Vault"
  bash "$ROOT/scripts/vault/render-env.sh" "$OUT"
elif [ -n "${PRODUCTION_ENV_B64:-}" ]; then
  echo "[env] Writing .env.production from PRODUCTION_ENV_B64 (GitHub secret)"
  echo "$PRODUCTION_ENV_B64" | base64 -d > "$OUT"
  chmod 600 "$OUT"
elif [ -n "${PRODUCTION_ENV:-}" ]; then
  echo "[env] Writing .env.production from PRODUCTION_ENV (GitHub secret)"
  printf '%s\n' "$PRODUCTION_ENV" > "$OUT"
  chmod 600 "$OUT"
elif _env_true "${VAULT_ENABLED:-}" && [ -x "$ROOT/scripts/vault/render-env.sh" ]; then
  echo "[env] Rendering .env.production from HashiCorp Vault (local AppRole file)"
  bash "$ROOT/scripts/vault/render-env.sh" "$OUT"
elif [ -f "$ROOT/deploy/production.env" ]; then
  echo "[env] Using local deploy/production.env (dev only — use GitHub secrets in CI)"
  if _vault_can_seed && _env_true "${VAULT_SEED_FROM_LOCAL:-true}"; then
    _seed_vault_from_file "$ROOT/deploy/production.env"
  fi
  if _env_true "${VAULT_ENABLED:-}" && [ -x "$ROOT/scripts/vault/render-env.sh" ] && [ -f "$ROOT/deploy/vault-approle.env" ]; then
    bash "$ROOT/scripts/vault/render-env.sh" "$OUT"
  else
    write_env "$ROOT/deploy/production.env"
  fi
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

# Container runtime overrides (host-side Vault CLI uses 127.0.0.1)
if grep -q '^VAULT_ENABLED=true' "$OUT" 2>/dev/null; then
  if grep -q '^VAULT_ADDR=' "$OUT"; then
    sed -i.bak 's|^VAULT_ADDR=.*|VAULT_ADDR=http://vault:8200|' "$OUT" && rm -f "${OUT}.bak"
  else
    echo "VAULT_ADDR=http://vault:8200" >> "$OUT"
  fi
  # AppRole creds are deploy-time secrets — inject for backend/celery Vault loader
  for key in VAULT_ROLE_ID VAULT_SECRET_ID; do
    val="${!key:-}"
    if [ -n "$val" ]; then
      if grep -q "^${key}=" "$OUT"; then
        sed -i.bak "s|^${key}=.*|${key}=${val}|" "$OUT" && rm -f "${OUT}.bak"
      else
        echo "${key}=${val}" >> "$OUT"
      fi
    fi
  done
fi
# Django migrations need a direct Postgres session — not pgBouncer transaction pool
if grep -q '^POSTGRES_HOST=pgbouncer' "$OUT" 2>/dev/null; then
  sed -i.bak 's|^POSTGRES_HOST=pgbouncer|POSTGRES_HOST=database|' "$OUT" && rm -f "${OUT}.bak"
fi

# Docker Compose interpolates ${VAR} from .env in project root (not .env.production).
# Keep both in sync so redis/rabbitmq passwords match backend env_file.
COMPOSE_ENV="$ROOT/.env"
cp "$OUT" "$COMPOSE_ENV"
chmod 600 "$COMPOSE_ENV"
echo "[env] Synced $COMPOSE_ENV for docker compose variable substitution"
