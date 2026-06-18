#!/bin/bash
# Check that server_tokens is disabled
if ! grep -r 'server_tokens\s*off' /etc/nginx/ 2>/dev/null | grep -qv '^#'; then
  echo "FAIL: server_tokens is not set to 'off' in nginx config — add 'server_tokens off;' to the http block"
  exit 1
fi
# Check nginx is running
if ! systemctl is-active --quiet nginx 2>/dev/null; then
  echo "FAIL: nginx is not running — reload with: systemctl reload nginx"
  exit 1
fi
# Functional check: Server header should not include version number
SERVER_HEADER=$(curl -sI --max-time 5 http://127.0.0.1/ 2>/dev/null | grep -i '^Server:' | tr -d '\r')
if echo "$SERVER_HEADER" | grep -qE 'nginx/[0-9]+\.[0-9]+'; then
  echo "FAIL: nginx is still exposing version in Server header: $SERVER_HEADER — reload nginx after fixing"
  exit 1
fi
echo "OK: server_tokens disabled — Server header: '${SERVER_HEADER:-nginx (no version)}'"
exit 0
