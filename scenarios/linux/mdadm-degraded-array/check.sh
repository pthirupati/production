#!/bin/bash
cat /proc/mdstat 2>/dev/null | grep -qE 'md0.*active.*raid1.*\[UU\]' && echo PASS && exit 0
cat /proc/mdstat 2>/dev/null | grep -qE '\[U_\]|\[_U\]' && echo "FAIL: RAID still degraded — add missing device to md0" && exit 1
echo FAIL: rebuild RAID1 — mdadm --manage /dev/md0 --add /dev/loopXp2 then wait for [UU]
exit 1
