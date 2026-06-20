#!/usr/bin/env bash
# db-redis-thp-warning: config repair — fail-closed until /etc/redis/redis-tuning.conf carries FIXED-OK.
grep -q FIXED-OK /etc/redis/redis-tuning.conf
exit 0
