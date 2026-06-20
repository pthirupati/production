#!/bin/sh
set -e

DOMAIN="${SSL_DOMAIN:-fixitlab.in}"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
CERT_FILE="${CERT_DIR}/fullchain.pem"
KEY_FILE="${CERT_DIR}/privkey.pem"
BOOTSTRAP_DIR="/var/lib/nginx/bootstrap"

# /etc/letsencrypt is read-only — never mkdir there
if [ -w /var/www/certbot ] 2>/dev/null; then
  mkdir -p /var/www/certbot
fi

# Four-droplet topology: when APP_PRIVATE_IP is set, render the cluster template
# so the backend upstream points at the App droplet (D2) over the private VPC.
PROD_CONF_SRC="/etc/nginx/templates/nginx.prod.conf"
if [ -n "${APP_PRIVATE_IP:-}" ] && [ -f /etc/nginx/templates/nginx.cluster.conf.template ]; then
  echo "[gateway] Cluster mode — backend upstream -> ${APP_PRIVATE_IP}:8000"
  sed "s/{{APP_PRIVATE_IP}}/${APP_PRIVATE_IP}/g" \
    /etc/nginx/templates/nginx.cluster.conf.template > /etc/nginx/templates/nginx.cluster.conf
  PROD_CONF_SRC="/etc/nginx/templates/nginx.cluster.conf"
fi

if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
  echo "[gateway] Let's Encrypt certificates found — enabling production HTTPS"
  cp "$PROD_CONF_SRC" /etc/nginx/conf.d/default.conf
else
  echo "[gateway] No Let's Encrypt certs — bootstrap mode (HTTP :80 + self-signed HTTPS :443)"
  mkdir -p "$BOOTSTRAP_DIR"
  if [ ! -f "$BOOTSTRAP_DIR/fullchain.pem" ]; then
    echo "[gateway] Generating temporary self-signed certificate for ${DOMAIN}"
    openssl req -x509 -nodes -days 90 -newkey rsa:2048 \
      -keyout "$BOOTSTRAP_DIR/privkey.pem" \
      -out "$BOOTSTRAP_DIR/fullchain.pem" \
      -subj "/CN=${DOMAIN}" \
      -addext "subjectAltName=DNS:${DOMAIN},DNS:www.${DOMAIN}" 2>/dev/null \
      || openssl req -x509 -nodes -days 90 -newkey rsa:2048 \
        -keyout "$BOOTSTRAP_DIR/privkey.pem" \
        -out "$BOOTSTRAP_DIR/fullchain.pem" \
        -subj "/CN=${DOMAIN}"
  fi
  cp /etc/nginx/templates/nginx.bootstrap.conf /etc/nginx/conf.d/default.conf
fi

exec nginx -g 'daemon off;'
