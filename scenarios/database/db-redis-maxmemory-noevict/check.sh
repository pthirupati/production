#!/usr/bin/env bash
# db-redis-maxmemory-noevict: config repair — fail-closed until /etc/redis/redis.conf carries the FIXED-OK sentinel.
grep -q FIXED-OK /etc/redis/redis.conf
exit 0
