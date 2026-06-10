#!/bin/bash
set -e
SPARE=$(cat /etc/fixitlab-raid-spare 2>/dev/null || true)
[ -n "$SPARE" ] && mdadm --manage /dev/md0 --add "$SPARE" 2>/dev/null || true
for _ in $(seq 1 60); do
  if grep -qE 'md0.*\[UU\]' /proc/mdstat 2>/dev/null; then
    exit 0
  fi
  sleep 2
done
