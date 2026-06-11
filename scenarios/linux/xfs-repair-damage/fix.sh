#!/bin/bash
set -e
[ -x /opt/fixitlab/setup.sh ] && bash /opt/fixitlab/setup.sh 2>/dev/null || true
DEV=$(cat /etc/fixitlab-xfs-dev 2>/dev/null || true)
[ -z "$DEV" ] && DEV=$(losetup -j /var/xfs.img 2>/dev/null | cut -d: -f1 | head -1)
[ -n "$DEV" ] || { losetup -f --show /var/xfs.img 2>/dev/null || true; DEV=$(cat /etc/fixitlab-xfs-dev 2>/dev/null); }
[ -n "$DEV" ] || exit 1
umount /data 2>/dev/null || umount -l /data 2>/dev/null || true
xfs_repair -f "$DEV"
mkdir -p /data
mount "$DEV" /data
