#!/bin/bash
set -e
[ -x /opt/fixitlab/setup.sh ] && bash /opt/fixitlab/setup.sh
SPARE=$(cat /etc/fixitlab-raid-spare 2>/dev/null || true)
if [ -n "$SPARE" ] && [ -b "$SPARE" ]; then
  mdadm --zero-superblock "$SPARE" 2>/dev/null || true
  wipefs -a "$SPARE" 2>/dev/null || true
  mdadm --manage /dev/md0 --add "$SPARE" --assume-clean --force 2>/dev/null || \
    mdadm --manage /dev/md0 --add "$SPARE" --force 2>/dev/null || true
fi
for _ in $(seq 1 60); do
  if grep -qE 'md0.*\[UU\]' /proc/mdstat 2>/dev/null; then
    exit 0
  fi
  sleep 1
done
exit 1
