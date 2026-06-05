#!/bin/bash
if redis-cli ping 2>/dev/null | grep -q PONG; then
  echo "OK: Redis responding"
  exit 0
fi
if grep -q 'bind 10.255.255.1' /etc/redis/redis.conf; then
  echo "FAIL: Redis bound to invalid IP — set bind 127.0.0.1"
  exit 1
fi
echo "FAIL: start redis with service redis-server start"
exit 1
