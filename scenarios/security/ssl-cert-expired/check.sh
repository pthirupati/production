#!/bin/bash
DAYS=$(openssl x509 -in /etc/nginx/ssl/cert.pem -noout -enddate 2>/dev/null | sed 's/notAfter=//')
if [ -z "$DAYS" ]; then
  echo "FAIL: no cert found"
  exit 1
fi
# Renew if valid more than 7 days from now
END_EPOCH=$(date -d "$DAYS" +%s 2>/dev/null || echo 0)
NOW=$(date +%s)
if [ "$END_EPOCH" -gt $((NOW + 86400 * 7)) ]; then
  echo "OK: certificate renewed (valid > 7 days)"
  if nginx -t 2>/dev/null; then
    echo "OK: nginx config valid"
    exit 0
  fi
fi
echo "FAIL: regenerate certificate with openssl (days >= 365) and reload nginx"
exit 1
