#!/bin/bash
DEV=$(cat /etc/fixitlab-xfs-dev 2>/dev/null)
[ -z "$DEV" ] && DEV=$(losetup -j /var/xfs.img 2>/dev/null | cut -d: -f1 | head -1)
mount /data 2>/dev/null || true
mountpoint -q /data && [ -f /data/app.conf ] && echo PASS && exit 0
[ -n "$DEV" ] && xfs_repair -n "$DEV" 2>/dev/null | grep -qi clean && mount "$DEV" /data && [ -f /data/app.conf ] && echo PASS && exit 0
echo FAIL: umount /data; xfs_repair on loop device; mount /data and verify /data/app.conf
exit 1
