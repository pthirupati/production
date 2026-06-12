#!/bin/bash
set -e
SPARE=$(cat /etc/fixitlab-raid-spare 2>/dev/null || true)
if [ -z "$SPARE" ] || [ ! -b "$SPARE" ]; then
  SPARE=$(cat /etc/fixitlab-raid2-loop 2>/dev/null || true)
fi
if [ -z "$SPARE" ] || [ ! -b "$SPARE" ]; then
  if [ -f /opt/fixitlab/backing/raid2.img ]; then
    SPARE=$(losetup -j /opt/fixitlab/backing/raid2.img 2>/dev/null | cut -d: -f1 | head -1)
    [ -n "$SPARE" ] || SPARE=$(losetup -f --show /opt/fixitlab/backing/raid2.img)
  fi
fi
[ -n "$SPARE" ] && [ -b "$SPARE" ] || exit 1
mdadm --zero-superblock "$SPARE" 2>/dev/null || true
wipefs -a "$SPARE" 2>/dev/null || true
mdadm --manage /dev/md0 --add "$SPARE" --assume-clean --force 2>/dev/null || \
  mdadm --manage /dev/md0 --add "$SPARE" --force 2>/dev/null || true
for _ in $(seq 1 60); do
  if grep -qE 'md0.*\[UU\]' /proc/mdstat 2>/dev/null; then
    exit 0
  fi
  sleep 1
done
exit 1
