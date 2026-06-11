#!/bin/bash
set -e
[ -x /opt/fixitlab/setup.sh ] && bash /opt/fixitlab/setup.sh 2>/dev/null || true
DEV=$(cat /etc/fixitlab-xfs-dev 2>/dev/null || true)
[ -z "$DEV" ] && DEV=$(losetup -j /var/xfs.img 2>/dev/null | cut -d: -f1 | head -1)
if [ -z "$DEV" ] && [ -f /var/xfs.img ]; then
  DEV=$(losetup -f --show /var/xfs.img)
  echo "$DEV" > /etc/fixitlab-xfs-dev
fi
[ -n "$DEV" ] || exit 1
umount /data 2>/dev/null || umount -l /data 2>/dev/null || true
xfs_repair -f "$DEV" || xfs_repair -L "$DEV"
mkdir -p /data
mount "$DEV" /data
