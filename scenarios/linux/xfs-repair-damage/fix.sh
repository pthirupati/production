#!/bin/bash
set -e
DEV=$(cat /etc/fixitlab-xfs-dev 2>/dev/null || true)
if [ -z "$DEV" ] || [ ! -b "$DEV" ]; then
  if [ -f /var/xfs.img ]; then
    DEV=$(losetup -j /var/xfs.img 2>/dev/null | cut -d: -f1 | head -1)
    [ -n "$DEV" ] || DEV=$(losetup -f --show /var/xfs.img)
    echo "$DEV" > /etc/fixitlab-xfs-dev
  fi
fi
[ -n "$DEV" ] && [ -b "$DEV" ] || exit 1
umount /data 2>/dev/null || umount -l /data 2>/dev/null || true
xfs_repair -f "$DEV" || xfs_repair -L -f "$DEV"
mkdir -p /data
mount "$DEV" /data
