#!/bin/bash
FAIL=0
MESSAGES=""
# Check Redis is not listening on 0.0.0.0
if ss -tlnp 2>/dev/null | grep ':6379 ' | grep -q '0.0.0.0\|\*:'; then
  MESSAGES="${MESSAGES}FAIL: Redis is still bound to 0.0.0.0:6379 — set bind 127.0.0.1 in /etc/redis/redis.conf\n"
  FAIL=1
fi
# Check MySQL is not listening on 0.0.0.0
if ss -tlnp 2>/dev/null | grep ':3306 ' | grep -q '0.0.0.0\|\*:'; then
  MESSAGES="${MESSAGES}FAIL: MySQL is still bound to 0.0.0.0:3306 — set bind-address=127.0.0.1 in mysqld.cnf\n"
  FAIL=1
fi
# Check that port 8080 dev server is not running
if ss -tlnp 2>/dev/null | grep -q ':8080 '; then
  MESSAGES="${MESSAGES}FAIL: service still running on port 8080 — stop it with pkill or systemctl\n"
  FAIL=1
fi
if [ "$FAIL" -eq 1 ]; then
  printf "%b" "$MESSAGES"
  exit 1
fi
echo "OK: Redis, MySQL, and dev server ports are no longer publicly accessible"
exit 0
