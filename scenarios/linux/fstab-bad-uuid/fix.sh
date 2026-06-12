#!/bin/bash
set -e
DEV=$(cat /etc/fixitlab-data-dev 2>/dev/null || true)
if [ -z "$DEV" ] || [ ! -b "$DEV" ]; then
  DEV=$(losetup -j /opt/fixitlab/backing/data.img 2>/dev/null | cut -d: -f1 | head -1)
fi
if [ -z "$DEV" ] && [ -f /opt/fixitlab/backing/data.img ]; then
  DEV=$(losetup -f --show /opt/fixitlab/backing/data.img)
  echo "$DEV" > /etc/fixitlab-data-dev
fi
[ -n "$DEV" ] && [ -b "$DEV" ] || { echo "data volume loop device not found" >&2; exit 1; }
UUID=$(blkid -s UUID -o value "$DEV" 2>/dev/null || true)
[ -n "$UUID" ] || exit 1
mkdir -p /mnt/data
sed -i "/[[:space:]]\\/mnt\\/data[[:space:]]/d" /etc/fstab
echo "UUID=$UUID /mnt/data ext4 defaults 0 2" >> /etc/fstab
mount -a 2>/dev/null || mount "$DEV" /mnt/data 2>/dev/null || true
