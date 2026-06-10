#!/bin/bash
set -e
DEV=$(cat /etc/fixitlab-xfs-dev 2>/dev/null || true)
[ -z "$DEV" ] && DEV=$(losetup -j /var/xfs.img 2>/dev/null | cut -d: -f1 | head -1)
[ -n "$DEV" ] || exit 0
umount /data 2>/dev/null || true
xfs_repair "$DEV" >/dev/null 2>&1 || true
mkdir -p /data
mount "$DEV" /data 2>/dev/null || true
