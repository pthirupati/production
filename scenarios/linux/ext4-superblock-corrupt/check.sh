#!/bin/bash
mount /data 2>/dev/null
[ -f /data/.marker ] && echo PASS && exit 0
echo FAIL: umount /data; fsck.ext4 -y /data.img; mount /data.img /data
exit 1
