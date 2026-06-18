#!/bin/bash
# Check that Redis has requirepass configured
REDIS_CONF="/etc/redis/redis.conf"
if [ ! -f "$REDIS_CONF" ]; then
  REDIS_CONF="/etc/redis.conf"
fi
# Check requirepass is set
REQUIREPASS=$(grep -E '^\s*requirepass\s+\S' "$REDIS_CONF" 2>/dev/null | awk '{print $2}')
if [ -z "$REQUIREPASS" ]; then
  echo "FAIL: Redis has no requirepass configured in $REDIS_CONF — add: requirepass <strong-password>"
  exit 1
fi
# Check bind is restricted to localhost
BIND_ADDR=$(grep -E '^\s*bind\s+' "$REDIS_CONF" 2>/dev/null | awk '{print $2}')
if [ "$BIND_ADDR" = "0.0.0.0" ]; then
  echo "FAIL: Redis is still binding to 0.0.0.0 — change to: bind 127.0.0.1"
  exit 1
fi
# Verify unauthenticated access is rejected
ANON_RESP=$(redis-cli -h 127.0.0.1 ping 2>/dev/null)
if echo "$ANON_RESP" | grep -qi '^PONG$'; then
  echo "FAIL: Redis still responds to unauthenticated PING — restart after fixing requirepass"
  exit 1
fi
echo "OK: Redis requires authentication and is bound to ${BIND_ADDR:-127.0.0.1}"
exit 0
