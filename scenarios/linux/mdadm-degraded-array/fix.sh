#!/bin/bash
set -e
SPARE=$(cat /etc/fixitlab-raid-spare 2>/dev/null || true)
if [ -n "$SPARE" ]; then
  wipefs -a "$SPARE" 2>/dev/null || true
  mdadm --manage /dev/md0 --add "$SPARE" 2>/dev/null || \
    mdadm --manage /dev/md0 --re-add "$SPARE" 2>/dev/null || true
fi
for _ in $(seq 1 90); do
  if grep -qE 'md0.*\[UU\]' /proc/mdstat 2>/dev/null; then
    exit 0
  fi
  sleep 2
done
