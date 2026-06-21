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

# Resolve the TLS cert: real Let's Encrypt if present, else a self-signed cert.
# Self-signed keeps nginx STARTING (the ssl_certificate directive needs a file) so
# the gateway serves HTTP + ACME + /health immediately; LE upgrades it on a later
# run once DNS points at this edge.
if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
  echo "[gateway] Let's Encrypt certificates found — production HTTPS"
  SSL_CERT="$CERT_FILE"; SSL_KEY="$KEY_FILE"
else
  echo "[gateway] No Let's Encrypt certs yet — self-signed HTTPS (HTTP + ACME still served)"
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
  SSL_CERT="$BOOTSTRAP_DIR/fullchain.pem"; SSL_KEY="$BOOTSTRAP_DIR/privkey.pem"
fi

if [ -n "${APP_PRIVATE_IP:-}" ] && [ -f /etc/nginx/templates/nginx.cluster.conf.template ]; then
  # Four-droplet: backend upstream -> the App droplet (D2) over the private VPC,
  # cert -> LE or self-signed. ALWAYS use the cluster config (even without LE):
  # the single-host nginx.bootstrap.conf points at "backend:8000", which does not
  # resolve on the edge and would crash nginx, so /health + the app are unreachable.
  echo "[gateway] Cluster mode — backend upstream -> ${APP_PRIVATE_IP}:8000 (cert: ${SSL_CERT})"
  sed -e "s/{{APP_PRIVATE_IP}}/${APP_PRIVATE_IP}/g" \
      -e "s#{{SSL_CERT}}#${SSL_CERT}#g" \
      -e "s#{{SSL_KEY}}#${SSL_KEY}#g" \
    /etc/nginx/templates/nginx.cluster.conf.template > /etc/nginx/conf.d/default.conf
elif [ "$SSL_CERT" = "$CERT_FILE" ]; then
  # Single-host with real certs.
  cp /etc/nginx/templates/nginx.prod.conf /etc/nginx/conf.d/default.conf
else
  # Single-host bootstrap (self-signed; "backend" resolves locally on a single host).
  cp /etc/nginx/templates/nginx.bootstrap.conf /etc/nginx/conf.d/default.conf
fi

exec nginx -g 'daemon off;'
