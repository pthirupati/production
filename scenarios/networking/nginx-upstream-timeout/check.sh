#!/bin/bash
# Check that proxy_read_timeout is set to at least 60 seconds
TIMEOUT_VAL=$(grep -r 'proxy_read_timeout' /etc/nginx/ 2>/dev/null | grep -oE '[0-9]+' | sort -n | tail -1)
if [ -z "$TIMEOUT_VAL" ]; then
  echo "FAIL: proxy_read_timeout not configured in nginx — add: proxy_read_timeout 120s;"
  exit 1
fi
if [ "$TIMEOUT_VAL" -lt 60 ]; then
  echo "FAIL: proxy_read_timeout is ${TIMEOUT_VAL}s — too low for long-running requests. Set to at least 120s."
  exit 1
fi
# Check nginx config is valid
if nginx -t 2>/dev/null; then
  if systemctl is-active --quiet nginx 2>/dev/null; then
    echo "OK: proxy_read_timeout is ${TIMEOUT_VAL}s and nginx is running"
    exit 0
  else
    echo "FAIL: timeout configured correctly but nginx is not running — reload with: systemctl reload nginx"
    exit 1
  fi
fi
echo "FAIL: nginx configuration has syntax errors — run: nginx -t"
exit 1
