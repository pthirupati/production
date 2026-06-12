#!/bin/bash
# Mount a small loop filesystem on /data and remount read-only.
set -e
. /opt/fixitlab/lab-loop.sh
if mountpoint -q /data 2>/dev/null && [ -f /data/file.txt ]; then
  exit 0
fi
fixitlab_loop_init
DEV=$(fixitlab_loop_attach /opt/fixitlab/backing/data-ro.img 32M)
echo "$DEV" > /etc/fixitlab-ro-data-dev
mkfs.ext4 -F "$DEV"
mkdir -p /data
mount "$DEV" /data
echo test > /data/file.txt
mount -o remount,ro /data
