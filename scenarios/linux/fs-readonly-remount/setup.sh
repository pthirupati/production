#!/bin/bash
# Mount a small loop filesystem on /data and remount read-only.
set -e
if mountpoint -q /data 2>/dev/null && [ -f /data/file.txt ]; then
  exit 0
fi
mkdir -p /opt/fixitlab/backing
dd if=/dev/zero of=/opt/fixitlab/backing/data-ro.img bs=1M count=32 status=none
DEV=$(losetup -f --show /opt/fixitlab/backing/data-ro.img)
echo "$DEV" > /etc/fixitlab-ro-data-dev
mkfs.ext4 -F "$DEV"
mkdir -p /data
mount "$DEV" /data
echo test > /data/file.txt
mount -o remount,ro /data
