#!/bin/bash
set -e
sed -i 's/^bind .*/bind 127.0.0.1/' /etc/redis/redis.conf
service redis-server restart 2>/dev/null || systemctl restart redis-server 2>/dev/null || redis-server /etc/redis/redis.conf --daemonize yes || true
