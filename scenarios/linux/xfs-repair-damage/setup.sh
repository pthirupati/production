#!/bin/bash
set -e
if [ -f /etc/fixitlab-xfs-dev ] && [ -b "$(cat /etc/fixitlab-xfs-dev)" ]; then
  exit 0
fi
dd if=/dev/zero of=/var/xfs.img bs=1M count=120 status=none
DEV=$(losetup -f --show /var/xfs.img)
echo "$DEV" > /etc/fixitlab-xfs-dev
mkfs.xfs -f "$DEV"
mkdir -p /data && mount "$DEV" /data
echo "enabled=true" > /data/app.conf
sync
umount /data
# Corrupt primary superblock copy (offset 0) — repair restores from secondary
dd if=/dev/zero of="$DEV" bs=512 count=8 conv=notrunc status=none
echo "XFS on $DEV needs xfs_repair before mount"
