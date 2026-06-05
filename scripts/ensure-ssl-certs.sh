#!/usr/bin/env bash
# Obtain or renew Let's Encrypt certificates using webroot (gateway must be running).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.production}"
[ -f "$ENV_FILE" ] || ENV_FILE=".env"

# shellcheck disable=SC1090
set -a
source "$ENV_FILE"
set +a

DOMAIN="${SSL_DOMAIN:-fixitlab.in}"
if [ -n "${SITE_URL:-}" ]; then
  DOMAIN="${SITE_URL#https://}"
  DOMAIN="${DOMAIN#http://}"
  DOMAIN="${DOMAIN%%/*}"
fi

EMAIL="${LETSENCRYPT_EMAIL:-${PRIMARY_EMAIL:-}}"
CERT_FILE="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"

cert_exists() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm --entrypoint sh certbot \
    -c "test -f '${CERT_FILE}'" 2>/dev/null
}

if cert_exists; then
  echo "[ssl] Certificate already present for ${DOMAIN}"
  exit 0
fi

echo "[ssl] Requesting Let's Encrypt certificate for ${DOMAIN} (webroot)..."

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

if ! docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm --entrypoint certbot certbot \
  "${CERTBOT_ARGS[@]}"; then
  echo "[ssl] WARNING: Certificate request failed."
  echo "  Check: DNS A record for ${DOMAIN} → this server, port 80 open, gateway running HTTP mode."
  exit 1
fi

echo "[ssl] Certificate obtained — restarting gateway for HTTPS"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart gateway
