#!/bin/sh
set -e

# Prepare directories used by certbot and cert mounts
mkdir -p /var/www/certbot
mkdir -p /etc/letsencrypt/live

# Ensure nginx user owns writable dirs where applicable
if id nginx >/dev/null 2>&1; then
  chown -R nginx:nginx /var/www/certbot || true
fi

# Warn if certificates are missing; continue to start nginx so container healthchecks can fail fast
if [ ! -f "/etc/letsencrypt/live/fixitlab.in/fullchain.pem" ] || [ ! -f "/etc/letsencrypt/live/fixitlab.in/privkey.pem" ]; then
  echo "[WARNING] TLS certificates not found at /etc/letsencrypt/live/fixitlab.in/. Ensure certs are mounted." >&2
fi

# Start nginx in foreground
exec nginx -g 'daemon off;'
