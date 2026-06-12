#!/bin/bash
set -e
. /opt/fixitlab/lab-loop.sh
DEV=$(cat /etc/fixitlab-data-dev 2>/dev/null || true)
if [ -z "$DEV" ] || [ ! -b "$DEV" ]; then
  DEV=$(fixitlab_loop_attach /opt/fixitlab/backing/data.img 80M)
  echo "$DEV" > /etc/fixitlab-data-dev
fi
[ -n "$DEV" ] && [ -b "$DEV" ] || { echo "data volume loop device not found" >&2; exit 1; }
UUID=$(blkid -s UUID -o value "$DEV" 2>/dev/null || true)
[ -n "$UUID" ] || exit 1
mkdir -p /mnt/data
sed -i "/[[:space:]]\\/mnt\\/data[[:space:]]/d" /etc/fstab
echo "UUID=$UUID /mnt/data ext4 defaults 0 2" >> /etc/fstab
mount -a 2>/dev/null || mount "$DEV" /mnt/data 2>/dev/null || true
