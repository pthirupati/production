#!/bin/bash
# Check that the installed certificate is not expired
CERT="/etc/nginx/ssl/server.crt"
if [ ! -f "$CERT" ]; then
  echo "FAIL: Certificate file $CERT not found"
  exit 1
fi
# Check expiry date
EXPIRY=$(openssl x509 -in "$CERT" -noout -enddate 2>/dev/null | cut -d= -f2)
EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$EXPIRY" +%s 2>/dev/null)
NOW_EPOCH=$(date +%s)
if [ -z "$EXPIRY_EPOCH" ] || [ "$EXPIRY_EPOCH" -le "$NOW_EPOCH" ]; then
  echo "FAIL: Certificate at $CERT is expired (expired: $EXPIRY) — replace with new certificate"
  exit 1
fi
# Check nginx is running and serving HTTPS
if systemctl is-active --quiet nginx 2>/dev/null; then
  echo "OK: nginx is running with a valid certificate (expires: $EXPIRY)"
  exit 0
fi
echo "FAIL: Certificate is valid but nginx is not running — reload with: systemctl reload nginx"
exit 1
