#!/bin/sh
set -e

DOMAIN="${SSL_DOMAIN:-fixitlab.in}"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
CERT_FILE="${CERT_DIR}/fullchain.pem"
KEY_FILE="${CERT_DIR}/privkey.pem"

# /etc/letsencrypt is a read-only volume mount — never mkdir there
if [ -w /var/www/certbot ] 2>/dev/null; then
  mkdir -p /var/www/certbot
fi

if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
  echo "[gateway] TLS certificates found — enabling HTTPS"
  cp /etc/nginx/templates/nginx.prod.conf /etc/nginx/conf.d/default.conf
else
  echo "[gateway] No TLS certificates yet — HTTP bootstrap mode (ACME + site on :80)"
  cp /etc/nginx/templates/nginx.http.conf /etc/nginx/conf.d/default.conf
fi

exec nginx -g 'daemon off;'
