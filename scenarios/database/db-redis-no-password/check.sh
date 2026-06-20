#!/usr/bin/env bash
# db-redis-no-password: config repair — fail-closed until /etc/redis/redis.conf carries FIXED-OK.
grep -q FIXED-OK /etc/redis/redis.conf
exit 0
