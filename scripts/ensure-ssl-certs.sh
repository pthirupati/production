#!/usr/bin/env bash
# Obtain Let's Encrypt certificates using webroot (gateway must be running on :80).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
[ -f "$ENV_FILE" ] || ENV_FILE=".env"

# shellcheck source=env-helpers.sh
source "$(dirname "$0")/env-helpers.sh"

DOMAIN="$(env_val SSL_DOMAIN "$ENV_FILE")"
DOMAIN="${DOMAIN:-fixitlab.in}"
SITE_URL="$(env_val SITE_URL "$ENV_FILE")"
if [ -n "$SITE_URL" ]; then
  DOMAIN="${SITE_URL#https://}"
  DOMAIN="${DOMAIN#http://}"
  DOMAIN="${DOMAIN%%/*}"
fi

EMAIL="$(env_val LETSENCRYPT_EMAIL "$ENV_FILE")"
[ -n "$EMAIL" ] || EMAIL="$(env_val PRIMARY_EMAIL "$ENV_FILE")"
CERT_FILE="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"

cert_exists() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm --entrypoint sh certbot \
    -c "test -f '${CERT_FILE}'" 2>/dev/null
}

if cert_exists; then
  echo "[ssl] Let's Encrypt certificate already present for ${DOMAIN}"
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart gateway || true
  exit 0
fi

echo "[ssl] DNS check: ${DOMAIN} should resolve to this server"
echo "[ssl] Requesting Let's Encrypt certificate for ${DOMAIN} and www.${DOMAIN}..."

CERTBOT_ARGS=(
  certonly
  --webroot -w /var/www/certbot
  -d "$DOMAIN"
  -d "www.${DOMAIN}"
  --agree-tos
  --non-interactive
  --preferred-challenges http
)

if [ -n "$EMAIL" ]; then
  CERTBOT_ARGS+=(--email "$EMAIL")
else
  CERTBOT_ARGS+=(--register-unsafely-without-email)
fi

if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm --entrypoint certbot certbot \
  "${CERTBOT_ARGS[@]}"; then
  echo "[ssl] Certificate obtained — restarting gateway with trusted HTTPS"
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart gateway
  exit 0
fi

echo "[ssl] WARNING: Let's Encrypt failed (site still works on http://${DOMAIN} and https with self-signed cert)"
echo "  Verify GoDaddy DNS: A @ → server IP only, CNAME www → fixitlab.in"
echo "  Ensure port 80 is open: ufw allow 80 && ufw allow 443"
exit 0
