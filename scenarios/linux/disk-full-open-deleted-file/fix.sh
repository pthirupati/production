#!/bin/bash
set -e
if [ -f /var/run/logholder.pid ]; then
  kill "$(cat /var/run/logholder.pid)" 2>/dev/null || true
fi
pkill -f 'tail -f /var/log/app.log' 2>/dev/null || true
