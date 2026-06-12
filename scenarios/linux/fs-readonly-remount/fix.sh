#!/bin/bash
set -e
. /opt/fixitlab/lab-loop.sh
if ! mountpoint -q /data 2>/dev/null; then
  DEV=$(cat /etc/fixitlab-ro-data-dev 2>/dev/null || true)
  if [ -z "$DEV" ] || [ ! -b "$DEV" ]; then
    DEV=$(fixitlab_loop_attach /opt/fixitlab/backing/data-ro.img 32M)
    echo "$DEV" > /etc/fixitlab-ro-data-dev
  fi
  [ -n "$DEV" ] && [ -b "$DEV" ] && mount "$DEV" /data
fi
mount -o remount,rw /data
test -w /data/file.txt 2>/dev/null || chmod u+w /data /data/file.txt 2>/dev/null || true
