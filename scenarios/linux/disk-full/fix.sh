#!/bin/bash
set -e
pkill -f log_generator.sh 2>/dev/null || true
truncate -s 0 /var/log/webapp/application.log 2>/dev/null || rm -f /var/log/webapp/application.log
rm -f /tmp/.hidden_cache/cache.dat
