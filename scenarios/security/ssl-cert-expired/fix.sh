#!/bin/bash
set -e
mkdir -p /etc/nginx/ssl
openssl req -x509 -nodes -newkey rsa:2048 -keyout /etc/nginx/ssl/key.pem -out /etc/nginx/ssl/cert.pem -days 365 -subj '/CN=localhost' >/dev/null 2>&1
nginx -t >/dev/null 2>&1 && (service nginx reload 2>/dev/null || systemctl reload nginx 2>/dev/null || true)
