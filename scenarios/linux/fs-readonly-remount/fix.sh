#!/bin/bash
set -e
if ! mountpoint -q /data 2>/dev/null; then
  DEV=$(cat /etc/fixitlab-ro-data-dev 2>/dev/null || true)
  if [ -z "$DEV" ] || [ ! -b "$DEV" ]; then
    if [ -f /opt/fixitlab/backing/data-ro.img ]; then
      DEV=$(losetup -j /opt/fixitlab/backing/data-ro.img 2>/dev/null | cut -d: -f1 | head -1)
      [ -n "$DEV" ] || DEV=$(losetup -f --show /opt/fixitlab/backing/data-ro.img)
      echo "$DEV" > /etc/fixitlab-ro-data-dev
    fi
  fi
  [ -n "$DEV" ] && [ -b "$DEV" ] && mount "$DEV" /data
fi
mount -o remount,rw /data
test -w /data/file.txt 2>/dev/null || chmod u+w /data /data/file.txt 2>/dev/null || true
